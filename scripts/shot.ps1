param(
  [string]$Base = "http://127.0.0.1:5010",
  [string]$User = "admin",
  [string]$Pass = "admin123",
  [bool]$Headless = $false,
  [ValidateSet('desktop','mobile','both')] [string]$View = 'desktop',
  [int]$Max = 25,
  [string]$Include = "/,/dashboard,/emails,/compose,/diagnostics,/watchers,/rules,/accounts,/import",
  [string]$Exclude = "/logout,/static,/api"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $here "shot.py"

# ensure playwright in venv
$venvPy = Resolve-Path "..\.venv\Scripts\python.exe"
& $venvPy -m pip install "playwright>=1.45,<2" --quiet
& $venvPy -m playwright install --with-deps chromium  | Out-Null

$env:SHOT_BASE = $Base
$env:SHOT_USER = $User
$env:SHOT_PASS = $Pass
$env:SHOT_HEADLESS = if ($Headless) {"1"} else {"0"}
$env:SHOT_VIEW = $View
$env:SHOT_MAX = "$Max"
$env:SHOT_INCLUDE = $Include
$env:SHOT_EXCLUDE = $Exclude

& $venvPy $py
