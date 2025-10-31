param(
  [int]$Port = 5001
)

Write-Host "============================================================"
Write-Host "   EMAIL MANAGEMENT TOOL - QUICK LAUNCHER (PowerShell)"
Write-Host "============================================================"

# Kill anything listening on $Port (best effort)
$pn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($pn) {
  $pids = $pn.OwningProcess | Select-Object -Unique
  foreach ($pid in $pids) {
    try { Stop-Process -Id $pid -Force -ErrorAction Stop; Write-Host "Killed PID $pid" } catch {}
  }
}

# Pick python
$py = "py -3.11"
try { & py -3.11 -V *> $null } catch { $py = "python" }

Write-Host "Starting server on port $Port ..."
& $py "simple_app.py" "--port" $Port
