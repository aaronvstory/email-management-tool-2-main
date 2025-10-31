# 👋 Start Here - Email Management Tool

## Two Ways to Start (Both Work Great)

### Option 1: `et.ps1` Helper (Recommended for API Testing)

```powershell
# Start app
.\scripts\et.ps1 start

# In NEW terminal - login once
.\scripts\et.ps1 login

# Make API calls
(.\scripts\et.ps1 get -path /healthz).Content
```

**Why?** Auto-handles CSRF, sessions, port cleanup - perfect for scripting/testing.

---

### Option 2: `start-clean.ps1` (Recommended for Development)

```powershell
.\start-clean.ps1
```

**Why?** Auto-finds ports, starts app, gives you the dashboard URL - perfect for interactive work.

---

## Pick Your Style

| If You Want To... | Use This |
|-------------------|----------|
| **Test APIs / write scripts** | `.\scripts\et.ps1 start` then `.\scripts\et.ps1 login` |
| **Use the web dashboard** | `.\start-clean.ps1` |
| **Do both** | Either one works! |

Both handle port cleanup, zombie processes, and environment setup automatically.

---

## What Just Happened?

The script:
1. ✅ Killed any zombie Python processes
2. ✅ Found safe ports (auto-avoids Windows reserved ranges)
3. ✅ Activated your virtual environment
4. ✅ Set correct environment variables
5. ✅ Started the app on ports that actually work

---

## Where to Go

**Dashboard:** Open the URL shown in the output (usually `http://127.0.0.1:5010`)
**Login:** `admin` / `admin123`
**Port Info:** Check `.last-ports.txt` if you forgot the URL

---

## Something Broke?

**→ [TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Instant fixes for every common issue

Common issues (all solved in troubleshooting doc):
- Port conflicts → Auto-handled now
- Wrong shell → Use PowerShell, not cmd
- SECRET_KEY errors → Debug mode is default now
- Permission denied → Script finds allowed ports

---

## Next Steps

1. **Add your email accounts:**
   Dashboard → Accounts → Add Account

2. **Configure rules:**
   Dashboard → Moderation Rules

3. **Start intercepting:**
   Configure your email client to use the SMTP proxy port (shown in startup output)

---

## Advanced Usage

```powershell
# Enable IMAP watchers (after configuring accounts!)
.\start-clean.ps1 -EnableWatchers

# Use specific ports
.\start-clean.ps1 -FlaskPort 8080 -SmtpPort 2525

# Skip SMTP proxy (IMAP only)
.\start-clean.ps1 -NoSmtp

# Production mode (requires strong SECRET_KEY)
$env:FLASK_SECRET_KEY = "your-64-char-random-string"
.\start-clean.ps1 -Production
```

---

## API Testing Made Easy

### Option A: `et.ps1` Helper Script ⭐ RECOMMENDED

```powershell
# Start app (terminal 1)
.\scripts\et.ps1 start

# Login and test (terminal 2)
.\scripts\et.ps1 login
(.\scripts\et.ps1 get -path /healthz).Content
.\scripts\et.ps1 post -path /api/accounts/1/test | Select -Expand Content

# Stop when done
.\scripts\et.ps1 stop
```

**Benefits:**
- ✅ CSRF tokens handled automatically
- ✅ Session management built-in
- ✅ No `$home` variable collision
- ✅ Clean one-line commands

---

### Option B: PowerShell Helper Module

```powershell
# Import once
Import-Module .\EmailToolHelpers.psm1

# Login once
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"

# Make API calls
Invoke-EmailToolApi "/api/stats"
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"

# See full example:
.\example-api-usage.ps1
```

---

## Documentation

- **[scripts/README.md](scripts/README.md)** - Complete `et.ps1` documentation and examples
- **[QUICK_FIX_GUIDE.md](QUICK_FIX_GUIDE.md)** - Fast fixes for common issues
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Never waste time on errors again
- **[POWERSHELL_HELPERS.md](POWERSHELL_HELPERS.md)** - PowerShell module documentation
- **[README.md](README.md)** - Full documentation, features, architecture
- **[docs/](docs/)** - Complete guides (API, security, development)

---

## Support

**Still stuck?** Run this to collect diagnostic info:

```powershell
@"
OS: $(Get-ComputerInfo | Select -Expand OsName)
PowerShell: $($PSVersionTable.PSVersion)
Python: $(python --version)
Ports: $(cat .last-ports.txt -EA SilentlyContinue)
"@ | clip
```

Info is now in clipboard - paste it when asking for help.

---

**TL;DR:**
- **Web dashboard:** `.\start-clean.ps1`
- **API testing:** `.\scripts\et.ps1 start` then `.\scripts\et.ps1 login`
- **Everything else is automatic** ✨
