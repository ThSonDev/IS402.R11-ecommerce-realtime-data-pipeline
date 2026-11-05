param(
    [string]$InputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'LocalRunOutputs\events_sample_local.json'),
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

$inputFile = (Resolve-Path -LiteralPath $InputPath).Path
if (-not $OutputPath) {
    $outputDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'LocalRunOutputs'
    $runDirectory = Get-ChildItem -LiteralPath $outputDirectory -Directory |
        Where-Object { $_.Name -match '^\d{14}$' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $runDirectory) {
        throw "No ASA local run found under $outputDirectory"
    }
    $candidate = Get-ChildItem -LiteralPath $runDirectory.FullName -Recurse -Filter 'kpi_1min.json' |
        Select-Object -First 1
    if (-not $candidate) {
        throw "No kpi_1min.json found in $($runDirectory.FullName)"
    }
    $outputFile = $candidate.FullName
} else {
    $outputFile = (Resolve-Path -LiteralPath $OutputPath).Path
}

$events = @([System.IO.File]::ReadAllLines($inputFile) | ForEach-Object { $_ | ConvertFrom-Json })
$rows = @([System.IO.File]::ReadAllLines($outputFile) | ForEach-Object { $_ | ConvertFrom-Json })
if ($events.Count -eq 0 -or $rows.Count -eq 0) {
    throw 'Input and output must both contain rows.'
}

$firstEventTime = [datetimeoffset]$events[0].event_time
$utcOrigin = [datetimeoffset]::new(
    $firstEventTime.UtcDateTime.Date.AddHours($firstEventTime.UtcDateTime.Hour).AddMinutes($firstEventTime.UtcDateTime.Minute),
    [timespan]::Zero
)
$minuteTicks = [timespan]::FromMinutes(1).Ticks
$expected = @{}

foreach ($event in $events) {
    $eventTime = [datetimeoffset]$event.event_time
    $elapsedTicks = ($eventTime - $utcOrigin).Ticks
    # ASA tumbling windows are open at the start and inclusive at the end.
    # An event exactly on a minute boundary is labeled with that boundary.
    $windowIndex = [long][math]::Ceiling($elapsedTicks / $minuteTicks)
    $key = "$windowIndex|$($event.channel)|$($event.province_code)"
    if (-not $expected.ContainsKey($key)) {
        $expected[$key] = @{
            view_count = [long]0
            cart_count = [long]0
            purchase_count = [long]0
            orders = [System.Collections.Generic.HashSet[string]]::new()
            gmv_vnd = [long]0
        }
    }

    $aggregate = $expected[$key]
    switch ($event.event_type) {
        'view' { $aggregate.view_count++ }
        'cart' { $aggregate.cart_count++ }
        'purchase' {
            $aggregate.purchase_count++
            if ($event.order_id) {
                [void]$aggregate.orders.Add([string]$event.order_id)
            }
            $aggregate.gmv_vnd += [long]$event.price_vnd
        }
        default { throw "Unexpected event_type '$($event.event_type)'" }
    }
}

$actual = @{}
foreach ($row in $rows) {
    $windowEnd = [datetimeoffset]$row.window_end
    $elapsedTicks = ($windowEnd - $utcOrigin).Ticks
    if (($elapsedTicks % $minuteTicks) -ne 0) {
        throw "Output window_end is not aligned to a minute: $($row.window_end)"
    }
    $windowIndex = [long]($elapsedTicks / $minuteTicks)
    $key = "$windowIndex|$($row.channel)|$($row.province_code)"
    if ($actual.ContainsKey($key)) {
        throw "Duplicate output group: $key"
    }
    $actual[$key] = $row
}

$differences = [System.Collections.Generic.List[string]]::new()
foreach ($key in $expected.Keys) {
    if (-not $actual.ContainsKey($key)) {
        $differences.Add("Missing output group: $key")
        continue
    }

    $want = $expected[$key]
    $got = $actual[$key]
    if ([long]$got.view_count -ne $want.view_count -or
        [long]$got.cart_count -ne $want.cart_count -or
        [long]$got.purchase_count -ne $want.purchase_count -or
        [long]$got.order_count -ne $want.orders.Count -or
        [long]$got.gmv_vnd -ne $want.gmv_vnd) {
        $differences.Add("Incorrect KPI values: $key")
    }
}
foreach ($key in $actual.Keys) {
    if (-not $expected.ContainsKey($key)) {
        $differences.Add("Unexpected output group: $key")
    }
}

$summary = [pscustomobject]@{
    InputEvents = $events.Count
    OutputGroups = $rows.Count
    ExpectedGroups = $expected.Count
    Mismatches = $differences.Count
    Views = ($rows | Measure-Object -Property view_count -Sum).Sum
    Carts = ($rows | Measure-Object -Property cart_count -Sum).Sum
    Purchases = ($rows | Measure-Object -Property purchase_count -Sum).Sum
    GMV_VND = ($rows | Measure-Object -Property gmv_vnd -Sum).Sum
    OutputFile = $outputFile
}
$summary | Format-List
if ($differences.Count -gt 0) {
    $differences | Select-Object -First 20 | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Host 'All per-minute KPI groups match.'
