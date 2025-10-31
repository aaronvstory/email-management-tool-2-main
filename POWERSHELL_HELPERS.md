# PowerShell API Helper Module

## Quick Start

```powershell
# Import the module
Import-Module .\EmailToolHelpers.psm1

# Login once
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"

# Make API calls
Invoke-EmailToolApi "/api/stats"
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"

# Logout
Disconnect-EmailTool
```

## Why Use This?

**Before (Manual - Error Prone):**
```powershell
# ❌ Easy to mess up CSRF tokens, session cookies, and use reserved variables
$home = Invoke-WebRequest ... # OOPS! $home is reserved in PowerShell
$csrf = ($home.Content | Select-String ...)... # This fails!
```

**After (Helper Module - Bulletproof):**
```powershell
# ✅ Clean, simple, no gotchas
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
Invoke-EmailToolApi "/api/stats"
```

### Benefits
- ✅ **No CSRF token juggling** - handled automatically
- ✅ **No session cookie management** - built-in
- ✅ **No PowerShell reserved variable conflicts** - safe variable names
- ✅ **Auto JSON parsing** - get objects, not raw strings
- ✅ **Clean error messages** - know exactly what failed
- ✅ **Type safety** - IntelliSense support in VS Code

## Available Functions

### `Connect-EmailTool`
Login and establish session.

```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010" -Username "admin" -Password "admin123"
```

**Aliases:** `Login-EmailTool`

### `Disconnect-EmailTool`
Logout and clear session.

```powershell
Disconnect-EmailTool
```

**Aliases:** `Logout-EmailTool`

### `Invoke-EmailToolApi`
Call any API endpoint with automatic session/CSRF handling.

```powershell
# GET requests (default)
Invoke-EmailToolApi "/api/stats"
Invoke-EmailToolApi "/api/accounts"

# POST requests
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/monitor/start"

# POST with JSON body (hashtable auto-converted)
$newAccount = @{
    account_name = "Gmail"
    email_address = "user@gmail.com"
    imap_host = "imap.gmail.com"
    imap_port = 993
    smtp_host = "smtp.gmail.com"
    smtp_port = 587
}
Invoke-EmailToolApi -Method POST -Path "/api/accounts" -Body $newAccount

# PUT, DELETE, PATCH also supported
Invoke-EmailToolApi -Method DELETE -Path "/api/accounts/1"
```

**Aliases:** `Call-EmailToolApi`

### `Get-EmailToolHealth`
Quick health check (no authentication required).

```powershell
Get-EmailToolHealth -BaseUrl "http://127.0.0.1:5010"
# If already connected:
Get-EmailToolHealth
```

## Examples

### Check System Health
```powershell
Get-EmailToolHealth -BaseUrl "http://127.0.0.1:5010"
```

### Get Statistics
```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
$stats = Invoke-EmailToolApi "/api/stats"
Write-Host "Total Emails: $($stats.total_emails)"
Write-Host "Pending: $($stats.pending)"
```

### Test Account Connection
```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
$result = Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"
if ($result.success) {
    Write-Host "✓ Connection successful"
    Write-Host "IMAP: $($result.imap_status)"
    Write-Host "SMTP: $($result.smtp_status)"
}
```

### Start IMAP Watcher
```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/monitor/start"
```

### List All Accounts
```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
$accounts = Invoke-EmailToolApi "/api/accounts"
$accounts.accounts | ForEach-Object {
    Write-Host "$($_.account_name) - $($_.email_address)"
}
```

### Create New Account
```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"

$account = @{
    account_name = "Hostinger"
    email_address = "user@domain.com"
    imap_host = "imap.hostinger.com"
    imap_port = 993
    imap_use_ssl = $true
    imap_username = "user@domain.com"
    imap_password = "password123"
    smtp_host = "smtp.hostinger.com"
    smtp_port = 587
    smtp_use_ssl = $true
    smtp_username = "user@domain.com"
    smtp_password = "password123"
}

$result = Invoke-EmailToolApi -Method POST -Path "/api/accounts" -Body $account
Write-Host "Created account ID: $($result.id)"
```

## Full Example Script

See **[example-api-usage.ps1](example-api-usage.ps1)** for a complete working example.

```powershell
# Run the example
.\example-api-usage.ps1
```

## Common PowerShell Gotchas Avoided

### ❌ Reserved Variable Names
```powershell
# DON'T use these as variable names:
$home = ...   # Reserved: user's home directory
$host = ...   # Reserved: PowerShell host object
$error = ...  # Reserved: error collection
$true = ...   # Reserved: boolean
$false = ...  # Reserved: boolean
$null = ...   # Reserved: null value
```

### ✅ Safe Alternatives
```powershell
# Use descriptive names instead:
$dashResp = Invoke-WebRequest ...
$homePageResp = Invoke-WebRequest ...
$lastError = ...
$isSuccess = ...
```

The helper module uses safe variable names internally, so you don't have to worry about this!

## Troubleshooting

### "Cannot index into a null array"
**Cause:** CSRF token extraction failed (often because you used a reserved variable like `$home`)

**Fix:** Use the helper module! It handles this automatically.

### "Not connected. Run Connect-EmailTool first."
**Cause:** Trying to call API without logging in

**Fix:**
```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
```

### "Login failed - check credentials"
**Cause:** Wrong username/password

**Fix:** Default is `admin`/`admin123`. Use:
```powershell
Connect-EmailTool -BaseUrl "http://127.0.0.1:5010" -Username "admin" -Password "admin123"
```

## See Also

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - General app troubleshooting
- **[QUICK_FIX_GUIDE.md](QUICK_FIX_GUIDE.md)** - Quick fixes for common issues
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** - Complete API documentation

## License

Same as main project.
