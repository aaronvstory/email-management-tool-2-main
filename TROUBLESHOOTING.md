# Troubleshooting Guide - Never Waste Time Again

## 🚀 Quick Start (The One That Always Works)

```powershell
# In PowerShell (NOT cmd.exe!)
.\start-clean.ps1
```

That's it. The script now:
- ✅ Auto-finds safe ports if defaults are blocked
- ✅ Kills zombie processes automatically
- ✅ Sets correct environment variables
- ✅ Validates everything before starting
- ✅ Creates `.last-ports.txt` with connection info

---

## 🔧 Common Issues & Instant Fixes

### 1. Port Already in Use / Permission Denied

**Symptoms:**
```
[WinError 10013] an attempt was made to access a socket in a way forbidden by its access permissions
```

**Why it happens:**
- Windows reserves certain port ranges (especially 8000-9000, 49152+)
- Firewall blocking
- Previous Python process still running

**Fix:**
The script now **automatically** finds a safe port. But if you want specific ports:

```powershell
# Let script auto-select (recommended):
.\start-clean.ps1

# Or specify safe ports manually:
.\start-clean.ps1 -SmtpPort 2525  # Try 2525, 1025, 2526, or 10025
```

**Check Windows reserved ranges:**
```powershell
# Run as Admin
netsh int ipv4 show excludedportrange protocol=tcp
```

Pick ports NOT in those ranges.

---

### 2. SECRET_KEY Error in Production Mode

**Symptoms:**
```
RuntimeError: SECURITY: A strong SECRET_KEY is required in production. Set FLASK_SECRET_KEY.
```

**Why it happens:**
- You used `-Production` flag without setting a real secret key

**Fix:**
```powershell
# Option 1: Don't use -Production for dev/testing (default is debug mode)
.\start-clean.ps1

# Option 2: Set real secret key for production
$env:FLASK_SECRET_KEY = "$(New-Guid)-$(New-Guid)"  # Generate random key
.\start-clean.ps1 -Production
```

---

### 3. Wrong Shell (cmd vs PowerShell)

**Symptoms:**
```
'Invoke-WebRequest' is not recognized as the name of a cmdlet...
```

**Why it happens:**
- You're in cmd.exe, not PowerShell

**Fix:**
```cmd
REM If you're in cmd, switch to PowerShell:
pwsh
```

Then run the script:
```powershell
.\start-clean.ps1
```

---

### 4. Conda/Anaconda Conflicts

**Symptoms:**
```
conda: The term 'conda' is not recognized...
```

**Why it happens:**
- Your shell auto-loads Anaconda, but this project uses `.venv`

**Fix:**
**Ignore the conda warnings.** The script uses `.venv` (correct). Conda is not needed.

If it bothers you:
```powershell
# Disable conda auto-activation in PowerShell profile
# Edit: $PROFILE
# Comment out conda initialization lines
```

---

### 5. Virtual Environment Not Found

**Symptoms:**
```
Virtual environment not found at .\.venv\
```

**Why it happens:**
- First time setup, or venv was deleted

**Fix:**
```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Now run the app
.\start-clean.ps1
```

---

### 6. IMAP Watcher Failures (DNS Errors)

**Symptoms:**
```
DNS lookup failed for imap.stateauditgroup.com
```

**Why it happens:**
- Invalid IMAP hostname in account configuration
- Watchers enabled with bad config

**Fix:**
```powershell
# Keep watchers OFF until you fix the account config:
.\start-clean.ps1  # Watchers are OFF by default

# Then:
# 1. Open http://127.0.0.1:5010/accounts
# 2. Edit account with bad hostname
# 3. Update to valid hostname (e.g., imap.hostinger.com:993)
# 4. Test connection
# 5. THEN enable watchers:
.\start-clean.ps1 -EnableWatchers
```

---

### 7. Database Locked Errors

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Why it happens:**
- Multiple Python processes accessing same DB
- DB file handle not closed properly

**Fix:**
```powershell
# Kill all Python processes and restart:
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
.\start-clean.ps1
```

---

### 8. Can't Access Dashboard / 404 Errors

**Symptoms:**
- Browser shows "Can't connect" or 404

**Fix:**
```powershell
# Check what port was actually used:
cat .last-ports.txt

# Use the URL shown there, e.g.:
# http://127.0.0.1:5010
```

The script saves the actual ports to `.last-ports.txt` after startup.

---

### 9. PowerShell CSRF Token Errors / Null Array

**Symptoms:**
```
Cannot index into a null array
```

**Why it happens:**
- Used `$home` as a variable name (PowerShell reserved variable, read-only)
- CSRF token extraction failed

**Fix:**
```powershell
# ❌ DON'T use $home (reserved variable)
$home = Invoke-WebRequest "http://127.0.0.1:5010/" ...

# ✅ DO use descriptive names
$dashResp = Invoke-WebRequest "http://127.0.0.1:5010/dashboard" ...
$metaCsrf = ($dashResp.Content | Select-String 'meta name="csrf-token"...')...

# OR use the helper module (recommended):
Import-Module .\EmailToolHelpers.psm1
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
Invoke-EmailToolApi "/api/stats"
```

**PowerShell reserved variables to avoid:**
- `$home`, `$host`, `$profile`, `$pshome`, `$pid`, `$error`, `$true`, `$false`, `$null`

---

## 🎯 Script Flags Reference

### Basic Usage
```powershell
.\start-clean.ps1                    # Default: debug mode, auto-select ports
.\start-clean.ps1 -FlaskPort 5000    # Use specific Flask port
.\start-clean.ps1 -SmtpPort 2525     # Use specific SMTP port
.\start-clean.ps1 -NoSmtp            # Skip SMTP proxy entirely
```

### Advanced Usage
```powershell
# Enable IMAP watchers (only after fixing account configs!)
.\start-clean.ps1 -EnableWatchers

# Production mode (requires strong SECRET_KEY)
$env:FLASK_SECRET_KEY = "your-64-char-random-string"
.\start-clean.ps1 -Production

# Combined
.\start-clean.ps1 -EnableWatchers -Production -FlaskPort 8080
```

---

## 🧪 Health Checks

### Quick Test (PowerShell)
```powershell
# Check if app is running
Invoke-WebRequest "http://127.0.0.1:5010/healthz" -UseBasicParsing
# Should return: {"status":"healthy"}
```

### Full Login Test (Manual)
```powershell
$base = "http://127.0.0.1:5010"

# Get login page + CSRF token (NOTE: Don't use $home - it's a PowerShell reserved variable!)
$loginPage = Invoke-WebRequest "$base/login" -UseBasicParsing -SessionVariable sess
$formCsrf = ($loginPage.Content | Select-String 'name="csrf_token" value="([^"]+)"').Matches[0].Groups[1].Value

# Login
$body = "username=admin&password=admin123&csrf_token=$formCsrf"
Invoke-WebRequest "$base/login" -Method POST -ContentType "application/x-www-form-urlencoded" -Body $body -WebSession $sess -UseBasicParsing | Out-Null

# Access dashboard and get meta CSRF token for API calls
$dashResp = Invoke-WebRequest "$base/dashboard" -WebSession $sess -UseBasicParsing
$metaCsrf = ($dashResp.Content | Select-String 'meta name="csrf-token" content="([^"]+)"').Matches[0].Groups[1].Value

# Test an API endpoint
Invoke-WebRequest "$base/api/accounts/1/test" -Method POST -WebSession $sess -Headers @{ "X-CSRFToken" = $metaCsrf } -UseBasicParsing | Select-Object -ExpandProperty Content
```

### Easy Way (Using Helper Module) ⭐ Recommended

```powershell
# Import helpers
Import-Module .\EmailToolHelpers.psm1

# Login once
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"

# Now make API calls easily (session + CSRF handled automatically!)
Invoke-EmailToolApi "/api/stats"
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"
Invoke-EmailToolApi -Method GET -Path "/api/accounts"

# Logout when done
Disconnect-EmailTool
```

**Why use the helper module?**
- ✅ No manual CSRF token management
- ✅ No `$home` variable collision (PowerShell reserved variable)
- ✅ Auto-handles session cookies
- ✅ Clean, readable code
- ✅ JSON auto-parsing

See **[EmailToolHelpers.psm1](EmailToolHelpers.psm1)** for full documentation.

### Test Port Availability
```powershell
Test-NetConnection 127.0.0.1 -Port 5010
# Should show: TcpTestSucceeded : True
```

---

## 📋 Pre-Flight Checklist

Before reporting an issue, verify:

- [ ] Using **PowerShell** (not cmd)
- [ ] Virtual environment exists: `.venv/Scripts/Activate.ps1`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] No zombie Python processes: `Get-Process python`
- [ ] Ports not in Windows reserved range (see `netsh` command above)
- [ ] `.last-ports.txt` shows what ports were actually used

---

## 🚨 Emergency Recovery

If everything is broken:

```powershell
# 1. Nuclear option - kill everything
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-NetTCPConnection -State Listen |
  Where-Object { $_.LocalPort -in 5000..5020, 8000..9000, 2525, 1025 } |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

# 2. Recreate venv
Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Start fresh
.\start-clean.ps1
```

---

## 🔐 Production Deployment

For actual production (not dev):

```powershell
# 1. Generate strong secret
$secret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 64 | ForEach-Object {[char]$_})
$env:FLASK_SECRET_KEY = $secret

# 2. Disable debug, enable watchers (if configured)
.\start-clean.ps1 -Production -EnableWatchers -FlaskPort 80 -SmtpPort 25

# 3. Save secret somewhere safe (password manager, Azure Key Vault, etc.)
# DO NOT commit $secret to git!
```

---

## 📞 Still Stuck?

Include this info when asking for help:

```powershell
# Collect diagnostic info
@"
OS: $(Get-ComputerInfo | Select-Object -ExpandProperty OsName)
PowerShell: $($PSVersionTable.PSVersion)
Python: $(python --version)
Port Info: $(cat .last-ports.txt -ErrorAction SilentlyContinue)
Reserved Ports: $(netsh int ipv4 show excludedportrange protocol=tcp)
"@ | clip

# Info is now in clipboard - paste it with your error message
```

---

## 📚 Related Files

- `start-clean.ps1` - Main startup script (auto-fixes everything)
- `QUICK_FIX_GUIDE.md` - Original fix documentation
- `.last-ports.txt` - Auto-generated file showing actual ports used (git-ignored)
- `simple_app.py` - Main application (respects --port and env vars)

---

## ✅ What Was Fixed (So It Never Happens Again)

### Before (Broken)
- ❌ App ignored `--port` argument
- ❌ No automatic port conflict resolution
- ❌ Manual port cleanup required
- ❌ Strict SECRET_KEY enforcement in dev mode
- ❌ Silent failures with watchers
- ❌ No validation of port availability

### After (Fixed)
- ✅ App honors `--port`, `--host`, env vars
- ✅ **Auto-selects safe ports** if defaults blocked
- ✅ **Auto-kills zombie processes**
- ✅ Validates ports before attempting bind
- ✅ Debug mode by default (dev-friendly)
- ✅ Clear error messages with fix suggestions
- ✅ Saves actual ports to `.last-ports.txt`
- ✅ Comprehensive pre-flight checks
- ✅ Watchers OFF by default (safer)

---

## 🎓 Learn From This

**Root causes of the 2-hour delay:**
1. Wrong shell (cmd vs PowerShell) → Use PowerShell
2. Windows port reservations → Script auto-finds safe ports now
3. Zombie processes → Script kills them now
4. App ignoring args → Fixed in `simple_app.py`
5. Unclear error messages → All improved

**Prevention:**
- Always use `start-clean.ps1` (it handles everything)
- Read `.last-ports.txt` to see actual config
- Keep watchers OFF until accounts are configured
- Use debug mode for dev (default now)

---

**Remember:** `.\start-clean.ps1` is your friend. It handles all of this automatically now.
