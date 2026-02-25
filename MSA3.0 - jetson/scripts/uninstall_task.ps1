param(
  [string]$TaskName = "MSA3-FlyTime-Service"
)

$ErrorActionPreference = "Stop"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Uninstalled scheduled task: $TaskName"
