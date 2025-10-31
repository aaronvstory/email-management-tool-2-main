# Quick Fix Guide - Port Conflicts & Startup Issues

## Problem Summary
Multiple issues causing startup failures:
1. ❌ **PowerShell commands run in cmd.exe** → "not recognized" errors
2. ❌ **Zombie processes holding ports 5001/8587** → "already in use" errors
3. ❌ **App ignoring `--port` argument** → always binds to 5001
4. ❌ **SECRET_KEY enforcement with watchers** → runtime crash
5. ❌ **Invalid IMAP hosts in config** → watcher failures

---

## ✅ Fast Fix (Copy & Paste)

### Option 1: Use the Helper Script (Easiest) ⭐ RECOMMENDED

```powershell
# In PowerShell (not cmd!)

# Start the app
.\scripts\et.ps1 start

# In a NEW PowerShell tab, login once
.\scripts\et.ps1 login

# Test it works
(.\scripts\et.ps1 get -path /healthz).Content

# Make API calls
.\scripts\et.ps1 post -path /api/accounts/1/test | Select -Expand Content

# Stop when done
.\scripts\et.ps1 stop
```

**What `et.ps1` does for you:**
- ✅ Kills zombie processes automatically
- ✅ Uses safe ports (5010 Flask, 2525 SMTP)
- ✅ Handles CSRF tokens automatically
- ✅ No `$home` variable collision
- ✅ Session management built-in
- ✅ Clean error messages

**Custom options:**
```powershell
# Start with watchers (only after configuring accounts!)
.\scripts\et.ps1 start -watchers 1

# Custom ports
.\scripts\et.ps1 start -port 8080 -smtp 1025

# Get help
.\scripts\et.ps1 help
```

---

### Option 2: Use start-clean.ps1

```powershell
# In PowerShell (not cmd!)
.\start-clean.ps1
```

---

### Option 2: Use start-clean.ps1

```powershell
# In PowerShell (not cmd!)
.\start-clean.ps1
```

**With custom ports:**
```powershell
.\start-clean.ps1 -FlaskPort 5010 -SmtpPort 2525
```

**With watchers enabled (only after fixing IMAP hosts):**
```powershell
.\start-clean.ps1 -EnableWatchers
```

Then use the PowerShell helper module for API calls:
```powershell
Import-Module .\EmailToolHelpers.psm1
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
Invoke-EmailToolApi "/api/stats"
```

---

### Option 3: Manual Startup (Not Recommended)

**Run in PowerShell:**

```powershell
# 1) Kill zombie processes
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in 5001,5010,8587,8599 } |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# 2) Activate venv
Set-Location C:\claude\email-management-tool-2-main
.\.venv\Scripts\Activate.ps1

# 3) Set environment
$env:FLASK_HOST       = "127.0.0.1"
$env:FLASK_PORT       = "5010"
$env:SMTP_PROXY_PORT  = "8599"
$env:FLASK_SECRET_KEY = "dev-secret-change-me-0123456789abcdef0123456789abcdef"
$env:ENABLE_WATCHERS  = "0"  # Keep OFF until IMAP hosts are fixed
$env:FLASK_DEBUG      = "0"

# 4) Start app
python .\simple_app.py
```

---

## Health Check

```powershell
# Test the app is running on the configured port
Invoke-WebRequest -Uri "http://127.0.0.1:5010/healthz" -UseBasicParsing
```

Should return: `{"status":"healthy"}`

---

## Authenticated API Testing

### Manual Method (Copy-Paste)

**⚠️ Important:** Don't use `$home` as a variable name - it's a PowerShell reserved variable!

```powershell
$base = "http://127.0.0.1:5010"

# Get login page and extract CSRF token
$loginPage = Invoke-WebRequest -Uri "$base/login" -UseBasicParsing -SessionVariable sess
$formCsrf = ($loginPage.Content | Select-String 'name="csrf_token" value="([^"]+)"').Matches[0].Groups[1].Value

# Login and capture session
$body = "username=admin&password=admin123&csrf_token=$formCsrf"
Invoke-WebRequest -Uri "$base/login" -Method POST -ContentType "application/x-www-form-urlencoded" -Body $body -UseBasicParsing -WebSession $sess | Out-Null

# Access protected routes
Invoke-WebRequest -Uri "$base/" -WebSession $sess -UseBasicParsing

# Test account (with CSRF header for API calls)
$dashResp = Invoke-WebRequest -Uri "$base/dashboard" -WebSession $sess -UseBasicParsing
$metaCsrf = ($dashResp.Content | Select-String 'meta name="csrf-token" content="([^"]+)"').Matches[0].Groups[1].Value

Invoke-WebRequest -Uri "$base/api/accounts/1/test" -Method POST -WebSession $sess -Headers @{ "X-CSRFToken" = $metaCsrf } -UseBasicParsing
```

### Easy Method (Helper Module) ⭐ Recommended

```powershell
# One-time: Import the helper module
Import-Module .\EmailToolHelpers.psm1

# Login once
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"

# Now make API calls - session + CSRF handled automatically!
Invoke-EmailToolApi "/api/stats"
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"
Invoke-EmailToolApi -Method GET -Path "/api/accounts"

# Start watcher
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/monitor/start"

# Logout when done
Disconnect-EmailTool
```

**Why use the helper?**
- No CSRF token juggling
- No `$home` variable collision
- Session cookies automatic
- Clean, readable code

---

## Fixing IMAP Watcher Failures

**Current Issue:** Account 1 uses `imap.stateauditgroup.com` (doesn't resolve)

**Fix:**
1. Navigate to **http://127.0.0.1:5010/accounts**
2. Edit Account 1
3. Update IMAP settings:
   - **IMAP Host:** `imap.hostinger.com`
   - **IMAP Port:** `993`
   - **Use SSL:** ✅ Enabled
   - **SMTP Host:** `smtp.hostinger.com`
   - **SMTP Port:** `587`
   - **Use SSL:** ✅ Enabled (STARTTLS)

4. Save and test connection

5. **Then** enable watchers:
   ```powershell
   $env:ENABLE_WATCHERS = "1"
   # Restart app
   ```

---

## Command-Line Arguments Now Work

The app now properly honors `--port` and environment variables:

```powershell
# All these work now:
python .\simple_app.py --port 5010
python .\simple_app.py --host 127.0.0.1 --port 5010 --smtp-port 8599
python .\simple_app.py --enable-watchers  # Only after fixing IMAP hosts!
```

---

## Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLASK_HOST` | `127.0.0.1` | Flask bind address |
| `FLASK_PORT` | `5001` | Flask HTTP port |
| `SMTP_PROXY_HOST` | `127.0.0.1` | SMTP proxy bind address |
| `SMTP_PROXY_PORT` | `8587` | SMTP proxy port |
| `FLASK_SECRET_KEY` | *(required with watchers)* | Session encryption key |
| `ENABLE_WATCHERS` | `0` | Enable IMAP watchers (0=off, 1=on) |
| `FLASK_DEBUG` | `1` | Debug mode (0=off, 1=on) |
| `IMAP_ONLY` | `0` | Disable SMTP proxy (0=run both, 1=IMAP only) |

---

## CI/Test Environment Setup

Add to your test job:

```yaml
env:
  FLASK_SECRET_KEY: "dev-secret-change-me-0123456789abcdef0123456789abcdef"
  FLASK_DEBUG: "1"
  ENABLE_WATCHERS: "0"
  FLASK_PORT: "5555"  # Avoid conflicts
```

---

## Troubleshooting

### "Port already in use"
- **Cause:** Zombie process from previous run
- **Fix:** Use `start-clean.ps1` or manually kill processes (see Option 2)

### "CSRF token expired"
- **Cause:** Missing or stale session cookie
- **Fix:** Follow the authenticated API testing script above

### "SECRET_KEY required"
- **Cause:** `ENABLE_WATCHERS=1` without valid SECRET_KEY
- **Fix:** Set `FLASK_SECRET_KEY` env var OR disable watchers

### "DNS lookup failed" (IMAP watcher)
- **Cause:** Invalid IMAP hostname in account config
- **Fix:** Update account to use valid hostname (see IMAP fix section)

### App still binds to 5001 despite --port
- **Cause:** Old version of simple_app.py
- **Fix:** Git pull latest changes (fixes applied in this session)

---

## What Changed

✅ **App now respects `--port` and environment variables**
✅ **Automatic port cleanup on startup**
✅ **SECRET_KEY validation only enforced when needed**
✅ **Watchers default to OFF (safer)**
✅ **Clear boot diagnostics showing actual config**
✅ **Helper script for one-command startup**

---

## Example Output (Success)

```
[BOOT] Configuration: Host=127.0.0.1 Port=5010 SMTP=127.0.0.1:8599 ENABLE_WATCHERS=0
[BOOT] Port 5010 is free
[BOOT] Port 8599 is free
[BOOT] IMAP watchers disabled (ENABLE_WATCHERS=0). Set ENABLE_WATCHERS=1 to enable.

============================================================
   EMAIL MANAGEMENT TOOL - MODERN DASHBOARD
============================================================

   🚀 Services Started:
   📧 SMTP Proxy: 127.0.0.1:8599
   🌐 Web Dashboard: http://127.0.0.1:5010
   👤 Login: admin / admin123

   📊 Runtime Configuration:
   • Flask Host: 127.0.0.1
   • Flask Port: 5010
   • SMTP Host: 127.0.0.1
   • SMTP Port: 8599
   • ENABLE_WATCHERS: 0
   • FLASK_DEBUG: 0
   • IMAP_ONLY: False
   • Watchers Running: 0

   ✨ Features:
   • IMAP/SMTP email interception
   • Multi-account monitoring
   • Real-time email moderation
   • Risk scoring system
   • Complete audit trail
   • Encrypted credential storage
   • Modern responsive UI

============================================================

[BOOT] Starting Flask on http://127.0.0.1:5010 (debug=False)
 * Running on http://127.0.0.1:5010
```

---

## Need Help?

Paste any error line for specific guidance. The key fixes were:

1. **Use PowerShell** (not cmd)
2. **Kill stale ports** (automated in start-clean.ps1)
3. **Set SECRET_KEY** (automated in start-clean.ps1)
4. **Keep watchers OFF** until IMAP hosts are valid
5. **Use new --port argument** or environment variables
