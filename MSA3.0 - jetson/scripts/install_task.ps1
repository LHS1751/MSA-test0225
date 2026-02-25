param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
  [string]$TaskName = "MSA3-FlyTime-Service"
)

$ErrorActionPreference = "Stop"

$runScript = Join-Path $ProjectRoot "scripts\run_service.ps1"
if (-not (Test-Path $runScript)) {
  throw "run_service.ps1 not found: $runScript"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runScript`" -ProjectRoot `"$ProjectRoot`""
$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet \
  -AllowStartIfOnBatteries \
  -DontStopIfGoingOnBatteries \
  -StartWhenAvailable \
  -RestartCount 999 \
  -RestartInterval (New-TimeSpan -Minutes 1)

# Run as LocalSystem (no password required). Ensure your MQTT broker is reachable from this account.
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force

Write-Host "Installed scheduled task: $TaskName"
Write-Host "You can open UI after start: http://<server-ip>:$env:HTTP_PORT/ (default 8000)"
