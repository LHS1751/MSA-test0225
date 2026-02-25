param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)

$ErrorActionPreference = "Stop"

function Import-EnvFile([string]$Path) {
  if (-not (Test-Path $Path)) {
    throw "Env file not found: $Path"
  }
  foreach ($raw in Get-Content -LiteralPath $Path) {
    # Strip CR in case the file was edited/copied from Windows (CRLF)
    $line = (($raw -as [string]) -replace "`r$", "").Trim()
    if ($line.Length -eq 0) { continue }
    if ($line.StartsWith('#')) { continue }

    # Allow optional leading 'export ' (common when copied from Linux env files)
    if ($line.StartsWith('export ')) {
      $line = $line.Substring(7).Trim()
    }

    $idx = $line.IndexOf('=')
    if ($idx -le 0) { continue }

    $name = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1)

    # Strip optional surrounding quotes
    if ($value.Length -ge 2) {
      if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
    }

    if ($name.Length -gt 0) { Set-Item -Path ("Env:" + $name) -Value $value }
  }
}

$envFile = Join-Path (Join-Path $ProjectRoot "config") "app.env"
Import-EnvFile $envFile

$venvPythonWin = Join-Path (Join-Path $ProjectRoot ".venv") "Scripts\python.exe"
$venvPythonNix = Join-Path (Join-Path $ProjectRoot ".venv") "bin/python"

if ($IsWindows) {
  $python = if (Test-Path $venvPythonWin) { $venvPythonWin } else { "python" }
} else {
  $python = if (Test-Path $venvPythonNix) { $venvPythonNix } else { "python3" }
}

$logDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

Set-Location $ProjectRoot

# Run in foreground (Task Scheduler will keep it alive; logs are written by the app)
& $python -m msa3_flytime.main
