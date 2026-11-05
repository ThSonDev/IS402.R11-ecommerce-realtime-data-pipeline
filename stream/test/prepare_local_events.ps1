param(
    [string]$SourcePath = (Join-Path $PSScriptRoot 'events_sample.json'),
    [string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'LocalRunOutputs\events_sample_local.json')
)

$ErrorActionPreference = 'Stop'

$source = (Resolve-Path -LiteralPath $SourcePath).Path
$lines = [System.IO.File]::ReadAllLines($source)
if ($lines.Count -eq 0) {
    throw "Input file is empty: $source"
}

$firstEvent = $lines[0] | ConvertFrom-Json
$firstTime = [datetimeoffset]$firstEvent.event_time
$now = [datetimeoffset]::UtcNow
$utc = $now.UtcDateTime
$targetStart = [datetimeoffset]::new(
    $utc.Date.AddHours($utc.Hour).AddMinutes($utc.Minute - 29),
    [timespan]::Zero
)
$shift = $targetStart - $firstTime
if (($shift.TotalSeconds % 60) -ne 0) {
    throw 'The replay shift must be a whole number of minutes to preserve minute buckets.'
}

$shiftedLines = foreach ($line in $lines) {
    $updated = [regex]::Replace(
        $line,
        '"event_time"\s*:\s*"([^"]+)"',
        {
            param($match)
            $eventTime = ([datetimeoffset]$match.Groups[1].Value).Add($shift)
            '"event_time":"' + $eventTime.ToString('yyyy-MM-ddTHH:mm:ss.fffZ') + '"'
        }
    )
    if ($updated -eq $line -and $line -notmatch '"event_time"\s*:\s*"') {
        throw 'An input row does not contain an event_time field.'
    }
    $updated
}

$outputDirectory = Split-Path -Parent $OutputPath
[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
[System.IO.File]::WriteAllLines($OutputPath, [string[]]$shiftedLines, [System.Text.UTF8Encoding]::new($false))

$lastEvent = $shiftedLines[-1] | ConvertFrom-Json
Write-Host "Prepared $($lines.Count) events: $OutputPath"
Write-Host "event_time range: $(([datetimeoffset]$firstEvent.event_time).Add($shift).ToString('o')) .. $(([datetimeoffset]$lastEvent.event_time).ToString('o'))"
