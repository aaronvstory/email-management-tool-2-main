# Deployment & Production Documentation

## Prerequisites

- **Python**: 3.9+ (tested with 3.13)
- **Operating System**: Windows (batch scripts, path conventions)
- **Network**: Local SMTP/IMAP access (ports 465, 587, 993, 8587)
- **Email Accounts**: Gmail App Passwords or provider-specific app passwords
- **Optional**: Modern browser (Chrome/Firefox/Edge) for dashboard

## Deployment Checklist

1. ✅ Clone repository to `C:\claude\Email-Management-Tool`
2. ✅ Install dependencies: `pip install -r requirements.txt`
3. ✅ Generate encryption key (automatic on first run → `key.txt`)
4. ✅ **Run security setup**: `.\setup_security.ps1`
5. ✅ **Validate security**: `python -m scripts.validate_security`
6. ✅ Configure accounts via web dashboard
7. ✅ Optional: Create `.env` file with overrides
8. ✅ Start application: `EmailManager.bat` or `python simple_app.py`

## Security Notes

**Critical Files**:
- `key.txt` is CRITICAL - backup securely, never commit
- `.env` contains credentials - add to `.gitignore`
- Default admin account (`admin`/`admin123`) must be changed in production
- SMTP proxy (8587) should only be accessible locally

## Pre-Deployment Security Verification

**CRITICAL**: Complete this checklist before deploying to production or exposing to network access.

### Step 1: Initial Security Setup

```powershell
# Run from project root (Windows PowerShell)
.\setup_security.ps1
```

**Expected Output**:
```
🔐 Email Management Tool - Security Setup (PowerShell)
✓ .env file exists
✓ SECRET_KEY already configured (looks strong)

✅ Security setup complete!

Next steps:
  1) Review .env and adjust values if needed
  2) Start app: python simple_app.py
  3) Run validation: python -m scripts.validate_security
```

**If weak secret detected**:
```
Weak or placeholder FLASK_SECRET_KEY detected – regenerating...
✓ SECRET_KEY generated
```

### Step 2: Validate Security Configuration

```bash
# From project root
python -m scripts.validate_security
```

**Required Result**: All 4 tests must pass

| Test | What It Checks | Pass Criteria |
|------|----------------|---------------|
| **Test 0** | SECRET_KEY strength | len≥32, entropy≥4.0, not blacklisted |
| **Test 1** | CSRF blocks invalid requests | Returns 400 or redirects to /login |
| **Test 2** | CSRF allows valid requests | Redirects to /dashboard with token |
| **Test 3** | Rate limiting active | 429 status after 5 attempts |

**Failure Actions**:

| Failed Test | Fix |
|-------------|-----|
| **Test 0 (SECRET_KEY)** | Run `.\setup_security.ps1` again |
| **Test 1 (CSRF block)** | Check Flask-WTF installed: `pip install Flask-WTF` |
| **Test 2 (CSRF allow)** | Verify CSRF meta tag in login template |
| **Test 3 (Rate limit)** | Check Flask-Limiter: `pip install Flask-Limiter` |

### Step 3: Verify Environment Configuration

```bash
# Check .env file exists and has required values
cat .env | grep FLASK_SECRET_KEY
```

**Required Variables**:
- `FLASK_SECRET_KEY` - Must be 64-char hex (not placeholder)
- `DB_PATH` - Optional, defaults to `email_manager.db`
- `ENABLE_WATCHERS` - Optional, defaults to 1

**Security Red Flags** (Never use these values):
```
FLASK_SECRET_KEY=dev-secret-change-in-production  ❌ WEAK
FLASK_SECRET_KEY=change-this-to-a-random-secret-key  ❌ WEAK
FLASK_SECRET_KEY=your-secret-here  ❌ WEAK
FLASK_SECRET_KEY=secret  ❌ WEAK
```

### Step 4: Test Application Security

```bash
# Start application
python simple_app.py

# In another terminal, check health endpoint
curl http://localhost:5001/healthz
```

**Expected Health Response**:
```json
{
  "ok": true,
  "db": "ok",
  "held_count": 0,
  "released_24h": 0,
  "median_latency_ms": null,
  "workers": [],
  "timestamp": "2025-10-10T12:00:00Z"
}
```

**Manual Security Tests**:
1. **CSRF Protection**:
   - Try logging in without opening /login first → Should fail
   - Open /login, inspect page source → Should see `<meta name="csrf-token">`

2. **Rate Limiting**:
   - Try 6 failed logins rapidly → Should see rate limit error after 5th attempt
   - Wait 60 seconds → Should be able to try again

3. **Session Security**:
   - Log in successfully → Should redirect to /dashboard
   - Close browser, reopen → Should still be logged in (session cookie)
   - Check browser cookies → Should see `session` cookie with HttpOnly flag

### Step 5: Production Configuration Review

**Before Production Deployment**:

```bash
# Change default admin password
# 1. Log in to dashboard as admin/admin123
# 2. Navigate to user management (if available) or update database directly:
sqlite3 email_manager.db
sqlite> UPDATE users SET password_hash = '<new_bcrypt_hash>' WHERE username = 'admin';
```

**Environment Variable Checklist**:
- [ ] `FLASK_SECRET_KEY` is strong (64 chars, high entropy)
- [ ] `.env` is in `.gitignore` and never committed
- [ ] `key.txt` (Fernet encryption key) is backed up securely
- [ ] SMTP proxy port 8587 is firewalled (localhost only)
- [ ] Flask port 5001 is behind reverse proxy (nginx/Apache) if exposed
- [ ] HTTPS enabled if accessible over network (not just localhost)
- [ ] Default admin password changed from `admin123`

### Step 6: Post-Deployment Verification

After deployment, verify all security features:

```bash
# Run validation against deployed instance
python -m scripts.validate_security

# Check logs for security events
tail -f app.log | grep -i "security\|csrf\|rate"

# Monitor health endpoint
watch -n 30 curl http://localhost:5001/healthz
```

**Common Deployment Issues**:

| Issue | Symptom | Fix |
|-------|---------|-----|
| **CSRF token errors** | "The CSRF token is missing" | Add `<meta name="csrf-token">` to templates |
| **Rate limit not working** | No 429 errors after spam | Install Flask-Limiter, restart app |
| **Session expires immediately** | Logged out on refresh | Check SECRET_KEY is stable (not regenerating) |
| **HTTPS CSRF errors** | CSRF fails on HTTPS only | Set `WTF_CSRF_SSL_STRICT = True` for HTTPS |

## Configuration & Settings

### Environment Variables

**`.env` file** (not committed):
```bash
# Database
DB_PATH=email_manager.db

# Security
FLASK_SECRET_KEY=<64-char-hex-generated-by-setup-script>

# IMAP monitoring
ENABLE_WATCHERS=1  # 0 to disable IMAP threads (dev mode)

# Testing
ENABLE_LIVE_EMAIL_TESTS=0  # 1 to enable live tests
LIVE_EMAIL_ACCOUNT=gmail   # or 'hostinger'

# Credentials (for testing only)
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_PASSWORD=your_app_password
HOSTINGER_ADDRESS=your_email@corrinbox.com
HOSTINGER_PASSWORD=your_password
```

### Monitoring & Logs

- **Application log**: `app.log` (Flask + SMTP/IMAP events)
- **JSON log**: `logs/app.json.log` (structured logging)
- **Audit trail**: `audit_log` table in database
- **Live stats**: SSE stream at `/stream/stats`
- **Health check**: `GET /healthz`

### Security Monitoring

**Daily Checks**:
- Monitor `app.log` for CSRF violations and rate limit triggers
- Check `/healthz` endpoint for database connectivity
- Verify IMAP worker heartbeats are active

**Weekly Checks**:
- Review audit_log table for suspicious activity
- Check for failed login patterns (brute force attempts)
- Verify backup integrity (`.env`, `key.txt`, `email_manager.db`)

**Monthly Tasks**:
- Consider rotating `FLASK_SECRET_KEY` (invalidates all sessions)
- Review and update dependencies: `pip list --outdated`
- Test disaster recovery (restore from backups)

## Provider-Specific Setup

### Gmail Setup

1. Enable 2-Factor Authentication
2. Generate App Password: https://myaccount.google.com/apppasswords
3. **Use password WITH spaces**: `xxxx xxxx xxxx xxxx`
4. Enable IMAP in Gmail settings
5. SMTP: `smtp.gmail.com:587` (STARTTLS)
6. IMAP: `imap.gmail.com:993` (SSL)

### Hostinger Setup

1. Verify email account exists in cPanel
2. Use full email address as username
3. SMTP: `smtp.hostinger.com:465` (SSL)
4. IMAP: `imap.hostinger.com:993` (SSL)

### General SMTP/IMAP Rules

- Port 587 → Always use STARTTLS (smtp_use_ssl=0)
- Port 465 → Always use direct SSL (smtp_use_ssl=1)
- Port 993 (IMAP) → Always SSL
- Username = Email address for most providers

## Performance Tuning

### Database Optimization

**WAL Mode** (already enabled):
- Allows concurrent reads during writes
- Improves multi-threaded performance

**Indices** (already created):
- Run `python scripts/verify_indices.py` to verify query plans
- Dashboard queries should use covering indices (no table scan)

**Vacuum**:
```bash
# Periodic database optimization
sqlite3 email_manager.db "VACUUM;"
```

### Resource Limits

**IMAP Watchers**:
- One thread per active account
- Each thread maintains persistent connection
- Automatic reconnection with exponential backoff

**SMTP Proxy**:
- Async I/O via aiosmtpd
- Handles concurrent connections
- Port 8587 (configurable)

## Backup & Recovery

### Critical Files to Backup

1. `key.txt` - Fernet encryption key (CRITICAL)
2. `.env` - Environment configuration
3. `email_manager.db` - SQLite database
4. `logs/` - Application logs (optional)

### Backup Strategy

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup critical files
cp key.txt backups/$(date +%Y%m%d)/
cp .env backups/$(date +%Y%m%d)/
cp email_manager.db backups/$(date +%Y%m%d)/

# Compress backup
tar -czf backups/backup-$(date +%Y%m%d).tar.gz backups/$(date +%Y%m%d)/
```

### Disaster Recovery

1. Restore `key.txt` to project root
2. Restore `.env` with credentials
3. Restore `email_manager.db`
4. Run `python simple_app.py` to verify
5. Check `/healthz` endpoint

## Related Documentation

- **[SECURITY.md](SECURITY.md)** - Comprehensive security guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
