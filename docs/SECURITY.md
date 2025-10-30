# Security Hardening & Validation Guide

**Status**: ✅ **PRODUCTION-READY SECURITY** (as of Phase 2+3 completion)

The Email Management Tool includes comprehensive security hardening with CSRF protection, rate limiting, and strong SECRET_KEY generation. All security features are validated through automated tests.

## Security Features

| Feature | Implementation | Status |
|---------|----------------|--------|
| **CSRF Protection** | Flask-WTF with bidirectional validation | ✅ Enabled |
| **Rate Limiting** | Flask-Limiter on authentication endpoints | ✅ Enabled (5 attempts) |
| **Strong SECRET_KEY** | 64-char hex token via cryptographic RNG | ✅ Validated |
| **Session Security** | Flask-Login with secure cookies | ✅ Enabled |
| **Credential Encryption** | Fernet symmetric encryption | ✅ Enabled |
| **Audit Logging** | All security events logged | ✅ Enabled |

## Initial Security Setup (Windows)

### Option 1: PowerShell Setup (Recommended)

```powershell
# Run from project root
.\setup_security.ps1
```

**What it does**:
- Creates `.env` from `.env.example` if missing
- Generates strong 64-character hex SECRET_KEY using cryptographic RNG
- Detects weak/placeholder secrets and regenerates automatically
- Compatible with PowerShell 5.1+ and PowerShell Core

**Weak Secret Detection**:
The script automatically detects and replaces these placeholder values:
- `dev-secret-change-in-production`
- `change-this-to-a-random-secret-key`
- `your-secret-here`
- Any secret shorter than 32 characters

### Option 2: Bash Setup (Git Bash/WSL)

```bash
# Run from project root
./setup_security.sh
```

## Security Validation

After setup, validate all security features are working:

```bash
# Run validation script (preferred method)
python -m scripts.validate_security

# Alternative: Run from scripts directory
cd scripts && python validate_security.py
```

### What it validates (4 comprehensive tests):

1. **SECRET_KEY Strength** - Verifies:
   - Length ≥ 32 characters
   - Entropy ≥ 4.0 bits/char (or 64+ hex chars)
   - Not in weak secret blacklist
   - **Does not expose secret value**

2. **CSRF Negative Test** - Blocks login without token:
   - Submits valid credentials WITHOUT csrf_token
   - Expects 400 status or redirect back to /login
   - Ensures dashboard is not accessible

3. **CSRF Positive Test** - Allows login with valid token:
   - Extracts CSRF token from /login page
   - Submits credentials WITH valid token
   - Expects redirect to /dashboard

4. **Rate Limiting** - Triggers 429 after threshold:
   - Sends 6 failed login attempts with valid CSRF
   - Uses JSON requests to force 429 response
   - Checks for rate limit headers (Retry-After, X-RateLimit-Remaining)

### Expected Output (All Passing)

```
Test 0 (SECRET_KEY strength: len>=32, entropy>=4.0, not blacklisted): PASS  [len=64, blacklisted=False, entropy=4.00 bits/char]
Test 1 (missing CSRF blocks login): PASS  [status=400, location='']
Test 2 (valid CSRF allows login): PASS  [status=302, location='/dashboard']
Test 3 (rate limit triggers 429/headers): PASS  [codes=[401, 401, 401, 401, 401, 429], headers_subset={'Retry-After': '60', 'X-RateLimit-Remaining': '0'}]

Summary:
  SECRET_KEY: OK (len=64, entropy=4.00 bpc)
  CSRF missing-token block: OK
  CSRF valid-token success: OK
  Rate limit: OK
```

## Security Configuration Details

### CSRF Configuration (`simple_app.py`)
- **Token Expiry**: None (tokens valid for session lifetime)
- **Cookie Settings**: SameSite=Lax, Secure in production
- **Exempt Routes**: SSE streams (`/stream/stats`, `/api/events`)
- **Error Handling**: User-friendly 400 handler with instructions
- **AJAX Support**: Automatic CSRF header injection via `static/js/app.js`

### Rate Limiting Configuration
- **Login Endpoint**: 5 attempts per minute per IP
- **Storage**: In-memory (single instance) or Redis (distributed)
- **Error Handling**: User-friendly 429 handler with retry guidance
- **JSON Support**: Returns 429 with Retry-After header

### SECRET_KEY Management
- **Source**: Environment variable `FLASK_SECRET_KEY` from `.env`
- **Generation**: PowerShell uses `[System.Security.Cryptography.RandomNumberGenerator]`
- **Fallback**: Hardcoded dev secret (triggers validation warning)
- **Rotation**: Change `FLASK_SECRET_KEY` in `.env` and restart app

## Troubleshooting Security Issues

### Validation Fails on SECRET_KEY
```bash
# Regenerate SECRET_KEY
.\setup_security.ps1  # Will detect weak secret and regenerate
```

### CSRF Token Missing in Forms
- Check template includes `<meta name="csrf-token" content="{{ csrf_token() }}">`
- For forms: Include `{{ form.hidden_tag() }}` or `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
- For AJAX: Use `X-CSRFToken` header (auto-injected by `static/js/app.js`)

### Rate Limit Not Working
- Verify Flask-Limiter installed: `pip install Flask-Limiter`
- Check logs for rate limit warnings
- Test with JSON requests to force 429 response

### CSRF Errors in Development
```bash
# Disable SSL requirement for CSRF cookies (dev only)
# In simple_app.py:
app.config['WTF_CSRF_SSL_STRICT'] = False  # Already set for localhost
```

## Security Health Endpoint

Check security configuration status (without exposing secrets):

```bash
# Query health endpoint
curl http://localhost:5001/healthz
```

### Enhanced Response (v2.7+)
```json
{
  "ok": true,
  "db": "ok",
  "held_count": 0,
  "released_24h": 0,
  "median_latency_ms": null,
  "workers": [],
  "timestamp": "2025-10-10T12:00:00Z",
  "security": {
    "secret_key_configured": true,
    "secret_key_prefix": "a1b2c3d4",
    "csrf_enabled": true,
    "csrf_time_limit": null,
    "session_cookie_secure": false,
    "session_cookie_httponly": true
  }
}
```

**Response Fields**:
- `ok` - Overall health status (true/false)
- `db` - Database connectivity ("ok" or null if error)
- `held_count` - Number of currently held messages
- `released_24h` - Messages released in last 24 hours
- `median_latency_ms` - Median interception latency (milliseconds)
- `workers` - IMAP worker heartbeat status
- `timestamp` - ISO 8601 UTC timestamp
- `security` - Security configuration status (NEW in v2.7):
  - `secret_key_configured` - Is SECRET_KEY strong (≥32 chars)?
  - `secret_key_prefix` - First 8 chars of SECRET_KEY for verification (not full secret)
  - `csrf_enabled` - CSRF protection status
  - `csrf_time_limit` - Token expiry (null = no expiry)
  - `session_cookie_secure` - Secure flag status
  - `session_cookie_httponly` - HttpOnly flag status

**Security Note**: Only the first 8 characters of SECRET_KEY are exposed for verification purposes. Full secret is never transmitted.

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
  3) Run validation: .\validate_security.sh (Git Bash) or python -m scripts.validate_security
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

## Security Monitoring & Maintenance

### Daily Checks
- Monitor `app.log` for CSRF violations and rate limit triggers
- Check `/healthz` endpoint for database connectivity
- Verify IMAP worker heartbeats are active

### Weekly Checks
- Review audit_log table for suspicious activity
- Check for failed login patterns (brute force attempts)
- Verify backup integrity (`.env`, `key.txt`, `email_manager.db`)

### Monthly Tasks
- Consider rotating `FLASK_SECRET_KEY` (invalidates all sessions)
- Review and update dependencies: `pip list --outdated`
- Test disaster recovery (restore from backups)

### Monitoring & Logs
- Application log: `app.log` (Flask + SMTP/IMAP events)
- Audit trail: `audit_log` table in database
- Live stats: SSE stream at `/stream/stats`
- Health check: `GET /healthz`

## Security Core Components

### Password Encryption
- **Passwords**: Encrypted with Fernet symmetric encryption (`key.txt`)
- **Sessions**: Flask-Login with secure cookies
- **Authentication**: Bcrypt password hashing for user accounts
- **Audit Trail**: All modifications logged with timestamp and user

### Security Notes
- `key.txt` is CRITICAL - backup securely, never commit to version control
- `.env` contains credentials - add to `.gitignore`, never commit
- Default admin account (`admin`/`admin123`) should be changed in production
- SMTP proxy (port 8587) should only be accessible locally
