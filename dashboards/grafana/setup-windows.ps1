# One-time setup for the Grafana OSS Windows service. Run in an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File dashboards\grafana\setup-windows.ps1
param(
    [string]$GrafanaHome = "E:\Program Files\GrafanaLabs\grafana"
)
#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$dir = (Join-Path $repo "dashboards\grafana") -replace '\\', '/'
$nssm = (Get-ChildItem "$(Split-Path $GrafanaHome)\svc-*\nssm.exe" | Select-Object -First 1).FullName

# Azure auth for the MSSQL data source, provisioning read straight from the repo.
@"
[paths]
provisioning = $dir/provisioning

[azure]
azure_auth_enabled = true
"@ | Set-Content -Encoding ascii (Join-Path $GrafanaHome "conf\custom.ini")

# Secrets stay in .env; the service gets them as environment variables, never in Git.
$envLines = Get-Content (Join-Path $repo ".env")
$vars = foreach ($key in "GRAFANA_SQL_TENANT_ID", "GRAFANA_SQL_CLIENT_ID", "GRAFANA_SQL_CLIENT_SECRET",
                         "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID") {
    $line = $envLines | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    $value = if ($line) { ($line -split '=', 2)[1].Trim().Trim("'").Trim('"') }
    if (-not $value) { throw "$key is missing or empty in .env" }
    "$key=$value"
}
$vars += "MEGASALE_GRAFANA_DASHBOARDS=$dir/dashboards"
& $nssm set Grafana AppEnvironmentExtra @vars | Out-Null

# Manual start: a running Grafana keeps the free SQL DB awake and uses up its monthly vCore-seconds.
Set-Service Grafana -StartupType Manual
Restart-Service Grafana
Write-Host "Grafana restarted: http://localhost:3000"
