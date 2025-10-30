# Troubleshooting Documentation

## Common Issues

### Gmail Authentication Failed
**Symptom**: "Authentication failed" when testing Gmail account

**Solutions**:
1. Use App Password (WITH spaces): `xxxx xxxx xxxx xxxx`
2. Verify 2FA is enabled on Gmail account
3. Ensure IMAP is enabled in Gmail settings
4. Check that App Password was generated (not regular password)
5. Username should be full email address

**Test**:
```bash
python scripts/test_permanent_accounts.py
```

### Port Already in Use
**Symptom**: "Address already in use" when starting application

**Solution**:
```bash
# Find process using port 8587
netstat -an | findstr :8587

# Kill the process
taskkill /F /PID <pid>

# Or use cleanup script
python cleanup_and_start.py
```

### Database Schema Mismatch
**Symptom**: SQLite column errors or missing fields

**Solution**:
```bash
# Run migration scripts
python scripts/migrations/20251001_add_interception_indices.py

# Verify schema
python -c "import sqlite3; conn = sqlite3.connect('email_manager.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(email_messages)'); print(cursor.fetchall())"
```

### Duplicate Emails After Release (Gmail Only)

**Symptom**: After editing and releasing an email on Gmail, BOTH the original and edited versions appear in INBOX

**Root Cause**: Gmail's label-based IMAP system keeps messages in `[Gmail]/All Mail` even after removal from Quarantine. If the original isn't purged from All Mail, Gmail may re-apply the `\Inbox` label.

**Solution**:

1. **Verify the fix is working** - Check logs for:
   ```
   [Gmail] Original purged from All Mail
   ```

2. **If log line is missing**, ensure:
   - IMAP is enabled in Gmail Settings → Forwarding and POP/IMAP
   - `[Gmail]/All Mail` folder is accessible over IMAP
   - Auto-Expunge is enabled in Gmail IMAP settings
   - Environment variable `GMAIL_ALL_MAIL_PURGE` is NOT set to `0`

3. **Manual cleanup** (if needed):
   - In Gmail web interface, go to All Mail
   - Search for the original email by Message-ID
   - Move to Trash manually

4. **Check application version**: This fix was added in v2.8. If running older version, update to latest.

**Prevention**: The system now automatically:
- Searches `[Gmail]/All Mail` for the original Message-ID
- Removes `\Inbox` and `Quarantine` labels
- Adds `\Trash` label to permanently purge the original

**Emergency Rollback**: If this causes issues:
```bash
# Temporarily disable Gmail All Mail purge
GMAIL_ALL_MAIL_PURGE=0
```
Restart the application. This keeps INBOX/Quarantine cleanup but skips All Mail purge.

---

### IMAP Authentication Failures (All Accounts)
**Symptoms**:
- All IMAP watchers fail to connect
- "Authentication failed" in logs for multiple accounts

**Diagnosis**:
```bash
# Check DB-stored credentials
python scripts/verify_accounts.py

# Test connections outside watchers
python scripts/test_permanent_accounts.py
```

**Solutions**:
1. Verify DB-stored password (Edit modal in Accounts page)
2. Check `imap_use_ssl` flag matches port (993=SSL, 143=STARTTLS)
3. Ensure `imap_username` = full email address
4. Verify provider hasn't locked account

### Hostinger Connection Issues
**Symptom**: Gmail works but Hostinger fails

**Solution**:
```bash
# Verify Hostinger settings
# SMTP: Port 465 with SSL (not 587)
# IMAP: Port 993 with SSL
# Username: Full email address (mcintyre@corrinbox.com)
```

**Test**:
```bash
python scripts/test_permanent_accounts.py
```

### Browser JavaScript Errors
**Symptom**: `$ is not defined` or jQuery errors

**Solution**:
- Remove jQuery dependencies from code
- Use Bootstrap 5 Modal API only
- Check `static/js/app.js` for conflicts

## Common Gotchas

### "Nothing Gets Held" - Complete Debugging Checklist

**Symptom**: Emails arrive in inbox normally, but none are intercepted

**Step-by-Step Diagnosis**:

1. **Is the watcher running?**
   ```bash
   # Check watchers page in dashboard
   # Status should be "IDLE" or "POLLING", not "STOPPED"

   # Or check via API
   curl -b cookie.txt http://localhost:5000/api/watchers/overview
   ```
   **Fix**: Go to Watchers page → Click "Start" button

2. **Is the rule active?**
   ```bash
   # Check Rules page in dashboard
   # Rule should have green "Active" badge

   # Or check via database
   sqlite3 email_manager.db "SELECT name, status FROM moderation_rules WHERE status='ACTIVE';"
   ```
   **Fix**: Go to Rules page → Toggle rule to Active

3. **Does the pattern actually match?**
   - Check exact keyword spelling
   - Remember: matching is **case-insensitive** ("Invoice" matches "invoice")
   - Test with simple pattern first (e.g., "test")

   **Test**:
   ```bash
   # Create test rule with obvious keyword
   # Pattern: "TESTWORD123"
   # Field: BODY
   # Send email with subject "TESTWORD123"
   # Wait 5 seconds
   # Check Held page - should appear
   ```

4. **Is the rule checking the right field?**
   - If pattern is in **subject**: Field must be SUBJECT or BODY
   - If pattern is in **sender**: Field must be SENDER or SENDER_DOMAIN
   - Default BODY field checks **both subject AND body text**

   **Common Mistake**:
   ```
   Rule: Pattern="invoice", Field=SENDER
   Email: Subject="Invoice #123"
   → WON'T MATCH (checking sender, not subject)

   Fix: Change Field to BODY or SUBJECT
   ```

5. **Is the watcher monitoring the RIGHT inbox?**
   - For Gmail→Hostinger flow, watcher must be on **Hostinger** (destination)
   - **Common mistake**: Starting watcher on sender instead of receiver

   **Rule**: Watcher goes on the inbox where emails **arrive**, not where they're **sent from**

6. **Check watcher mode and heartbeat**:
   ```bash
   # Watchers page shows:
   # - Status: IDLE or POLLING
   # - Heartbeat: "3 seconds ago" (should update every ~30s)

   # Stale heartbeat (>60s ago) = connection issue
   ```
   **Fix**: Click "Restart" button on watcher card

### "Original Still Appears in INBOX" - Verification Steps

**Symptom**: Email is held, but original also visible in recipient's inbox (duplicate)

**Diagnosis**:

1. **Check interception latency**:
   ```bash
   curl http://localhost:5000/healthz
   # Look for "median_latency_ms"
   ```
   - **IDLE mode**: Should be <500ms (email disappears before client refreshes)
   - **Polling mode**: May be 30+ seconds (email briefly visible)

2. **Verify watcher mode**:
   - Go to Watchers page
   - Check if status is "IDLE" (green) or "POLLING" (yellow)
   - If polling, email MAY flash in inbox before interception

3. **Check email client refresh rate**:
   - Some clients refresh every 1-5 seconds
   - With polling mode (~30s), email will appear briefly
   - This is **expected behavior in polling mode**

4. **Verify Quarantine folder**:
   - Log into email account via webmail
   - Check Quarantine folder - original should be there
   - INBOX should have NO copy after interception

**Solutions**:
- Ensure watcher is in IDLE mode (check Watchers page)
- Restart watcher to force IDLE reconnect
- If stuck in polling, check logs for IDLE failures

### "Delayed Interception" - Mode & Timing Issues

**Symptom**: Email takes 30+ seconds to be intercepted

**Root Cause**: Watcher is in **polling mode** instead of IDLE

**Diagnosis**:
```bash
# Check watcher mode on Watchers page
# Status badge should say:
# - "IDLE" (green) = <1s detection
# - "POLLING" (yellow) = ~30s detection

# Or check logs
grep -i "IDLE mode started" app.log
grep -i "Polling mode active" app.log
```

**Why Polling Mode Activates**:
- 3 consecutive IDLE failures → automatic fallback to polling
- Server doesn't support IDLE command
- Network/firewall blocks IDLE connections
- IMAP_DISABLE_IDLE=1 in environment

**Solutions**:

1. **Force IDLE restart**:
   - Watchers page → Click "Restart" on affected account
   - System attempts IDLE first, falls back to polling only if fails

2. **Check environment variables**:
   ```bash
   # Verify IDLE is not disabled
   grep IMAP_DISABLE_IDLE .env
   # Should be absent or =0

   # Check polling interval
   grep IMAP_POLL_INTERVAL .env
   # Default: 30 seconds
   ```

3. **Review IDLE failure logs**:
   ```bash
   grep -i "IDLE.*fail" app.log
   # Look for patterns: timeout, unsupported, connection reset
   ```

4. **Test IDLE support manually**:
   ```python
   import imaplib
   conn = imaplib.IMAP4_SSL('imap.gmail.com', 993)
   conn.login('user@gmail.com', 'app_password')
   conn.select('INBOX')
   conn.send(b'A001 IDLE\r\n')  # Should get "+ idling" response
   ```

### Gmail Labels vs Folders - Provider Quirks

**Understanding the Difference**:

**Gmail**:
- "Folders" are actually **labels**
- An email can have multiple labels simultaneously
- "Moving" to Quarantine = removing INBOX label + adding Quarantine label
- Original email stays in "All Mail" with different labels

**Hostinger/Outlook/Yahoo**:
- True **folder structure**
- Email exists in ONE folder at a time
- "Moving" to Quarantine = physical move between folders
- Email removed from INBOX, exists only in Quarantine

**Impact on Interception**:

1. **Gmail Behavior**:
   ```
   Email arrives → has labels: [INBOX, UNREAD]
   Intercept → labels become: [Quarantine, UNREAD]
   Release → labels become: [INBOX, UNREAD]

   Note: "All Mail" always has the email
   ```

2. **Hostinger Behavior**:
   ```
   Email arrives → folder: INBOX
   Intercept → folder: Quarantine
   Release → folder: INBOX

   Note: Email physically moves between folders
   ```

**Common Issues**:

- **Gmail**: Search in "All Mail" shows intercepted emails (they're just labeled differently)
- **Gmail**: Deleting from Quarantine doesn't remove from All Mail (only removes label)
- **Hostinger**: Email truly disappears from INBOX when intercepted

**Verification**:
```bash
# Gmail: Check labels via IMAP
# Quarantined email has "Quarantine" label, not "INBOX" label

# Hostinger: Check folders via IMAP
# Quarantined email exists ONLY in Quarantine folder
```

## Error Taxonomy & Recovery

### IMAP Errors

**AUTHENTICATIONFAILED**:
- **Cause**: Invalid credentials or disabled IMAP
- **Recovery**: Update credentials via Edit modal
- **Prevention**: Use App Passwords, verify IMAP enabled

**TIMEOUT / Connection Reset**:
- **Cause**: Network issues, server timeout
- **Recovery**: Automatic reconnection with exponential backoff
- **Prevention**: Check network connectivity, firewall rules

**MOVE Unsupported**:
- **Cause**: Provider doesn't support MOVE command
- **Recovery**: Automatic fallback to COPY+DELETE
- **Prevention**: None - automatic handling

### SMTP Errors

**SMTPAuthenticationError**:
- **Cause**: Invalid SMTP credentials
- **Recovery**: Update password, verify App Password
- **Prevention**: Use correct SMTP port and encryption

**SMTPServerDisconnected / Timeout**:
- **Cause**: Network interruption or server timeout
- **Recovery**: Automatic retry after reconnect
- **Prevention**: Check network stability

**STARTTLS Failure on Port 587**:
- **Cause**: SSL wrapper used instead of STARTTLS
- **Recovery**: Ensure `smtp_use_ssl=0` for port 587
- **Prevention**: Use smart detection API

### Database Errors

**Database is Locked**:
- **Cause**: Concurrent write operations
- **Recovery**: WAL mode + busy_timeout automatically retry
- **Prevention**: Already mitigated by WAL mode

**Foreign Key Constraint Failed**:
- **Cause**: Referential integrity violation
- **Recovery**: Check parent records exist before insert
- **Prevention**: Enable foreign keys in all connections

## IMAP Watcher Lifecycle & Debugging

### Connection Process

1. Load account config from DB → prefer `imap_username` else `email_address`
2. Establish connection:
   - SSL: `imaplib.IMAP4_SSL(host, port=993)`
   - STARTTLS: `IMAP4(host, port=143)` → `starttls()`
3. LOGIN with username/password
4. SELECT INBOX
5. IDLE loop (or noop polling fallback)
6. On new message: FETCH metadata, MOVE to Quarantine
7. Heartbeat every N minutes
8. On errors: exponential backoff (1s→2s→4s→... cap 5 min)
9. Graceful close on thread stop

### Common Auth Failures

**Wrong imap_username**:
- **Fix**: Edit modal → set to full email address
- **Test**: `python scripts/verify_accounts.py`

**STARTTLS vs SSL Mismatch**:
- **Fix**: Ensure `imap_use_ssl` matches port
  - Port 993 → `imap_use_ssl=1` (SSL)
  - Port 143 → `imap_use_ssl=0` (STARTTLS)

**Provider Lockouts**:
- **Fix**: Enable App Passwords, verify IMAP enabled
- **Test**: Log in via webmail to check for security notices

## IDLE vs Polling Debugging

### How to Check Current Mode

**Via Dashboard**:
1. Go to **Watchers** page
2. Look at status badge next to each account:
   - **"IDLE"** (green badge) = Real-time detection active (<1s latency)
   - **"POLLING"** (yellow badge) = Polling mode active (~30s latency)

**Via Logs**:
```bash
# Check recent mode transitions
grep -i "IDLE mode" app.log | tail -n 5
grep -i "Polling mode" app.log | tail -n 5

# Check IDLE failures
grep -i "IDLE.*fail" app.log
```

**Via API**:
```bash
curl -b cookie.txt http://localhost:5000/api/watchers/overview | jq '.watchers[] | {account_id, status, mode}'
```

### Environment Variables

**IMAP_DISABLE_IDLE** - Force polling mode (disable IDLE)
```bash
# In .env file
IMAP_DISABLE_IDLE=1  # Forces polling for all accounts

# Or at runtime
IMAP_DISABLE_IDLE=1 python simple_app.py
```

**IMAP_POLL_INTERVAL** - Polling frequency in seconds
```bash
# Default: 30 seconds
IMAP_POLL_INTERVAL=10   # Poll every 10 seconds (faster, more load)
IMAP_POLL_INTERVAL=60   # Poll every 60 seconds (slower, less load)

# Valid range: 5-300 seconds (clamped automatically)
```

**IMAP_IDLE_TIMEOUT** - How long to wait for IDLE response
```bash
# Default: 29 minutes (Gmail timeout is ~29 min)
IMAP_IDLE_TIMEOUT=1740  # Seconds (29 minutes)

# Note: System auto-restarts IDLE before timeout
```

**IMAP_CIRCUIT_THRESHOLD** - Failures before disabling account
```bash
# Default: 5 consecutive failures
IMAP_CIRCUIT_THRESHOLD=5

# If account fails 5 times, circuit opens → watcher stops
# "Fix": Restart watcher manually after fixing issue
```

### Connection Health Check Failures

**Symptom**: Watcher shows "Circuit Open" error

**Meaning**: Account exceeded error threshold (default: 5 consecutive failures)

**Diagnosis**:
```bash
# Check circuit breaker status
sqlite3 email_manager.db "SELECT id, email_address, circuit_open, circuit_fail_count FROM accounts WHERE circuit_open=1;"

# Check recent errors
grep -i "circuit" app.log | tail -n 10
```

**Common Causes**:
1. **Wrong credentials** - Update password via Edit modal
2. **IMAP disabled** - Enable IMAP in email provider settings
3. **Network issues** - Check firewall, VPN, proxy settings
4. **Provider lockout** - Check webmail for security notices
5. **Port blocked** - Verify port 993 (IMAP SSL) is accessible

**Recovery**:
1. Fix underlying issue (credentials, network, etc.)
2. Go to Watchers page
3. Click **"Start"** button on affected account
4. Circuit breaker resets on successful connection

### Manual IDLE Reconnection

**When to Use**: Watcher stuck in polling mode, want to force IDLE retry

**Method 1: Via Dashboard**:
```
1. Go to Watchers page
2. Find account card
3. Click "Restart" button
4. System attempts IDLE first
5. Falls back to polling only if IDLE fails 3 times
```

**Method 2: Via API**:
```bash
# Stop watcher
curl -b cookie.txt -X POST http://localhost:5000/api/accounts/1/monitor/stop

# Start watcher (attempts IDLE)
curl -b cookie.txt -X POST http://localhost:5000/api/accounts/1/monitor/start
```

**Method 3: Restart application**:
```bash
# Kill and restart
taskkill /F /IM python.exe
python simple_app.py

# All watchers restart in IDLE mode
```

### Verifying IDLE Support

**Test if provider supports IDLE**:
```python
import imaplib

# Connect to provider
conn = imaplib.IMAP4_SSL('imap.gmail.com', 993)
conn.login('your@email.com', 'app_password')
conn.select('INBOX')

# Test IDLE command
tag = 'A001'
conn.send(f'{tag} IDLE\r\n'.encode())
response = conn.readline()

if b'idling' in response.lower():
    print("✓ IDLE supported")
else:
    print("✗ IDLE not supported - will use polling")

# Exit IDLE
conn.send(b'DONE\r\n')
conn.logout()
```

**Known Support**:
- ✅ Gmail - Full IDLE support (preferred)
- ✅ Hostinger - Full IDLE support
- ✅ Outlook/Office365 - Full IDLE support
- ✅ Yahoo - Full IDLE support
- ⚠️ Some custom servers - May not support IDLE (auto-fallback to polling)

## Rule Matching Issues

### Case Sensitivity

**Default Behavior**: Matching is **case-insensitive**

**Examples**:
```
Rule pattern: "invoice"
Matches:
- "Invoice #123"
- "INVOICE DUE"
- "Please send invoice"
- "InVoIcE"

Does NOT match:
- "invoi ce" (space in middle)
- "invoce" (typo)
```

**Custom Regex** (advanced):
```
Rule Type: REGEX
Pattern: (?i)invoice  # Case-insensitive flag
Pattern: INVOICE      # Case-sensitive (no flag)
```

### Field Selection

**SUBJECT** - Subject line only
```
Rule: Pattern="payment", Field=SUBJECT

Matches:
✓ Subject: "Payment required"
✗ Subject: "Hello", Body: "Please make payment"
```

**BODY** - Subject **AND** body text combined (default for keywords)
```
Rule: Pattern="payment", Field=BODY

Matches:
✓ Subject: "Payment required", Body: "..."
✓ Subject: "Hello", Body: "Please make payment"
✓ Subject: "Payment", Body: "Payment due"
```

**SENDER** - From email address
```
Rule: Pattern="spam@bad.com", Field=SENDER

Matches:
✓ From: spam@bad.com
✗ From: john@good.com (even if body mentions spam@bad.com)
```

**RECIPIENT** - To email address
```
Rule: Pattern="alerts@", Field=RECIPIENT

Matches:
✓ To: alerts@company.com
✓ Cc: alerts@department.org
```

**SENDER_DOMAIN** - Sender's domain only
```
Rule: Pattern="@spam.com", Field=SENDER_DOMAIN

Matches:
✓ From: user@spam.com
✓ From: admin@spam.com
✗ From: user@spam.com.fake.com (exact domain match)
```

### Operator Differences

**CONTAINS** (default) - Pattern appears anywhere
```
Rule: Pattern="test", Operator=CONTAINS

Matches:
✓ "This is a test"
✓ "testing 123"
✓ "contest winner"
```

**EQUALS** - Exact match only
```
Rule: Pattern="test", Operator=EQUALS

Matches:
✓ "test"
✗ "This is a test"
✗ "testing"
```

**STARTS_WITH** - Field begins with pattern
```
Rule: Pattern="RE:", Operator=STARTS_WITH

Matches:
✓ "RE: Your inquiry"
✗ "Your inquiry RE: meeting"
```

**ENDS_WITH** - Field ends with pattern
```
Rule: Pattern=".pdf", Operator=ENDS_WITH, Field=SUBJECT

Matches:
✓ "Invoice.pdf"
✗ "Invoice.pdf (see attachment)"
```

**REGEX** - Regular expression matching
```
Rule: Pattern="invoice-\d{4}", Operator=REGEX

Matches:
✓ "invoice-1234"
✓ "Ref: invoice-5678"
✗ "invoice-ABC"
```

### Multiple Keywords

**Comma-separated** (applies to KEYWORD rules only):
```
Rule: Pattern="invoice,payment,billing", Operator=CONTAINS

Matches if ANY keyword found:
✓ "Invoice #123" (matches "invoice")
✓ "Payment due" (matches "payment")
✓ "Billing statement" (matches "billing")
✓ "Invoice and payment" (matches both)
```

**Advanced Multi-Pattern** (use REGEX):
```
Rule: Pattern="(invoice|payment|billing)", Operator=REGEX

Same as comma-separated but with regex control
```

### Debugging Non-Matching Rules

**Step 1: Simplify the pattern**
```
Original rule: Pattern="urgent payment required", Field=BODY
Test rule: Pattern="urgent", Field=BODY

If test rule matches → problem is multi-word pattern
If test rule doesn't match → check field selection
```

**Step 2: Check actual email content**
```bash
# View raw email from database
sqlite3 email_manager.db "SELECT subject, sender, body_text FROM email_messages WHERE id=42;"

# Compare with rule pattern
sqlite3 email_manager.db "SELECT name, pattern, condition_field FROM moderation_rules WHERE status='ACTIVE';"
```

**Step 3: Test pattern matching manually**
```python
import re

# Email content
subject = "Invoice #123"
body = "Please find attached"
combined = f"{subject} {body}"

# Rule pattern
pattern = "invoice"

# Test CONTAINS (case-insensitive)
if pattern.lower() in combined.lower():
    print(f"✓ Would match with CONTAINS")

# Test REGEX
if re.search(pattern, combined, re.IGNORECASE):
    print(f"✓ Would match with REGEX")
```

## SMTP Send Pipeline Debugging

### Send Process

1. Resolve settings (`smtp_host`/`port`/`use_ssl`/`username`)
2. Connect:
   - Port 465: `smtplib.SMTP_SSL`
   - Port 587: `smtplib.SMTP` → `ehlo` → `starttls` → `ehlo`
3. AUTH (LOGIN/PLAIN via `smtplib.login`)
4. `sendmail(from, to_list, data)`
5. On success: INSERT SENT record, log audit SEND
6. On failure: Map exceptions to user-friendly messages

### Common SMTP Issues

**Authentication Error**:
- **Fix**: Update password, use App Password
- **Test**: `python scripts/test_permanent_accounts.py`

**Server Disconnected**:
- **Fix**: Automatic retry after reconnect
- **Verify**: Check SMTP host/port are correct

**STARTTLS Failure**:
- **Fix**: Ensure port 587 uses `smtp_use_ssl=0`
- **Verify**: Use smart detection API for settings

## Observability & Health

### Log Files

**Application Log** (`app.log`):
- Text format with timestamps
- SMTP/IMAP events, auth failures, actions
- Rotation: 10MB max, 5 backups

**JSON Log** (`logs/app.json.log`):
- Structured format for parsing
- Sample record:
  ```json
  {"timestamp":"2025-10-15T02:55:14.512Z","level":"INFO","logger":"app.routes.interception","message":"[interception::release] success","email_id":123}
  ```

### Useful Log Filters

```bash
# IMAP release failures
jq 'select(.message|test("interception::release") and .level=="ERROR")' logs/app.json.log

# SMTP connection issues grouped by host
jq -r 'select(.message|test("smtp")) | .host' logs/app.json.log | sort | uniq -c

# Failed login attempts
grep -i "authentication failed" app.log

# Rate limit triggers
grep -i "rate limit" app.log
```

### Health Endpoint

```bash
# Check application health
curl http://localhost:5000/healthz
```

**Response Fields**:
- `ok` - Overall health (true/false)
- `db` - Database connectivity ("ok" or null)
- `held_count` - Messages currently held
- `released_24h` - Messages released in last 24 hours
- `median_latency_ms` - Median processing latency
- `workers` - IMAP watcher heartbeats
- `timestamp` - ISO 8601 UTC timestamp

### Rate Limit Monitoring

**Default Limits**:
- Login: 5 attempts per minute
- Release API: 30 per minute
- Edit API: 30 per minute
- Fetch emails: 30 per minute

**429 Response Handling**:
```javascript
if (response.status === 429) {
  const retryAfter = Number(response.headers.get('Retry-After') || 1);
  toast.warning(`Too many requests – retry in ${retryAfter}s`);
  setTimeout(retryCall, retryAfter * 1000);
}
```

## Nothing Works Troubleshooting

### Symptom: Nothing works, /healthz returns 500

**Diagnosis**:
```bash
# Check if app is running
tasklist | findstr python.exe

# Check SMTP proxy thread
netstat -an | findstr :8587

# Check logs
tail -f app.log
```

**Solutions**:
1. Restart application: `python simple_app.py`
2. Verify port 8587 not blocked by firewall
3. Check database file exists: `ls email_manager.db`
4. Verify `key.txt` exists (encryption key)

### Symptom: Web UI loads but no emails appear

**Diagnosis**:
```bash
# Check database
sqlite3 email_manager.db "SELECT COUNT(*) FROM email_messages;"

# Check IMAP watchers
python scripts/verify_accounts.py

# Check logs for IMAP errors
grep -i "imap" app.log
```

**Solutions**:
1. Verify accounts are active: Check Accounts page
2. Start IMAP watchers: Click "Start Monitoring" on Accounts page
3. Check IMAP credentials: Use Edit modal to update passwords

### Symptom: Emails stuck in HELD status

**Diagnosis**:
```bash
# Check held messages
sqlite3 email_manager.db "SELECT COUNT(*) FROM email_messages WHERE interception_status='HELD';"

# Check release endpoint
curl -X POST http://localhost:5000/api/interception/release/1
```

**Solutions**:
1. Verify original_uid is set (should not be 0 or null)
2. Check Quarantine folder exists in email account
3. Review logs for IMAP release errors
4. Manually release via dashboard

## Provider Matrix & Connection Strategy

**Gmail**:
- SMTP: 587 STARTTLS (`smtp_use_ssl=0`)
- IMAP: 993 SSL (`imap_use_ssl=1`)
- Requires: App Password
- Username: Full email address

**Hostinger**:
- SMTP: 465 SSL (`smtp_use_ssl=1`)
- IMAP: 993 SSL (`imap_use_ssl=1`)
- Username: Full email address

**Outlook**:
- SMTP: 587 STARTTLS (`smtp_use_ssl=0`)
- IMAP: 993 SSL (`imap_use_ssl=1`)
- Requires: App Password for 2FA accounts

**Yahoo**:
- SMTP: 465 SSL (`smtp_use_ssl=1`)
- IMAP: 993 SSL (`imap_use_ssl=1`)

**Rules of Thumb**:
- Port 587 → STARTTLS (`smtp_use_ssl=0`, `starttls=True`)
- Port 465 → SSL (`smtp_use_ssl=1`, no STARTTLS)
- Port 993 → SSL (`imap_use_ssl=1`)

## Performance Issues

### Slow Dashboard Loading

**Diagnosis**:
```bash
# Check database size
ls -lh email_manager.db

# Check indices
python scripts/verify_indices.py

# Check query plans
sqlite3 email_manager.db "EXPLAIN QUERY PLAN SELECT * FROM email_messages WHERE status='PENDING';"
```

**Solutions**:
1. Verify indices exist (run migration if needed)
2. Vacuum database: `sqlite3 email_manager.db "VACUUM;"`
3. Clear old emails: Archive and delete old messages

### High Memory Usage

**Diagnosis**:
```bash
# Check IMAP watcher threads
# Each watcher maintains persistent connection
ps aux | grep python
```

**Solutions**:
1. Disable unused accounts (set `is_active=0`)
2. Restart application to clear memory
3. Review IMAP watcher count (one per active account)

### IDLE Timeout Symptoms

**Common Symptoms**:
- Watcher switches from IDLE to POLLING mode unexpectedly
- Log messages: "IDLE timeout", "Connection reset by peer"
- Interception latency increases from <1s to ~30s
- Heartbeat stops updating for extended periods

**Root Causes**:
1. **Provider Timeout** - Gmail/Hostinger close IDLE after ~29 minutes
2. **Firewall/NAT Timeout** - Network equipment closes idle connections
3. **Client-Side Timeout** - Application IDLE timeout too short

**Diagnosis**:
```bash
# Check IDLE timeout events
grep -i "IDLE.*timeout\|IDLE.*failed" app.log | tail -n 20

# Check heartbeat gaps (large time differences indicate timeouts)
grep -i "heartbeat" app.log | tail -n 10

# Check mode transitions
grep -E "IDLE mode|Polling mode" app.log | tail -n 10
```

**Solutions**:

1. **Adjust IDLE Timeout** (if too short):
   ```bash
   # In .env file
   IMAP_IDLE_TIMEOUT=1740  # 29 minutes (default)

   # For providers with shorter timeouts
   IMAP_IDLE_TIMEOUT=600   # 10 minutes
   ```

2. **Enable Automatic Restart** (already built-in):
   - System auto-restarts IDLE before timeout
   - Graceful exit → reconnect → resume monitoring
   - No manual intervention required

3. **Check Network Equipment**:
   ```bash
   # Test connection stability
   # Keep connection open for 30 minutes
   python scripts/test_idle_stability.py --duration 1800
   ```

4. **Fallback to Polling** (if persistent issues):
   ```bash
   # Force polling mode for problematic account
   IMAP_DISABLE_IDLE=1 python simple_app.py
   ```

### Circuit Breaker Behavior

**How It Works**:
- Tracks consecutive connection failures per account
- Default threshold: **5 failures**
- Failures reset on successful connection
- "Circuit open" = watcher automatically disabled

**Failure Counter Examples**:
```
Connection 1: ❌ Auth failed → counter=1
Connection 2: ❌ Timeout → counter=2
Connection 3: ❌ Auth failed → counter=3
Connection 4: ❌ Network error → counter=4
Connection 5: ❌ Auth failed → counter=5 → CIRCUIT OPEN (watcher stops)

After fixing credentials:
Connection 6: ✅ Success → counter=0, circuit closes
```

**Why Circuit Breakers Matter**:
- Prevent infinite retry loops
- Protect provider from rate limiting
- Alert operator to persistent issues
- Reduce log spam from repeated failures

**Checking Circuit Breaker Status**:
```bash
# Via database
sqlite3 email_manager.db "SELECT id, email_address, circuit_open, circuit_fail_count FROM accounts;"

# Via logs
grep -i "circuit" app.log

# Via dashboard
# Accounts page shows "Circuit Open" badge for affected accounts
```

**Adjusting Threshold**:
```bash
# In .env file
IMAP_CIRCUIT_THRESHOLD=3   # More aggressive (fail faster)
IMAP_CIRCUIT_THRESHOLD=10  # More lenient (more retries)

# Default: 5 (balanced)
```

**Manual Circuit Reset**:
```bash
# Method 1: Via database (direct)
sqlite3 email_manager.db "UPDATE accounts SET circuit_open=0, circuit_fail_count=0 WHERE id=1;"

# Method 2: Via dashboard (recommended)
# 1. Fix underlying issue (credentials, network, etc.)
# 2. Go to Watchers page
# 3. Click "Start" button → circuit resets automatically on success
```

### Connection Pool Exhaustion

**Symptom**: New watchers fail to start with "Too many connections" error

**Diagnosis**:
```bash
# Check active connections
sqlite3 email_manager.db "SELECT COUNT(*) FROM accounts WHERE is_active=1;"

# Check system connection limits
ulimit -n  # Linux/Mac: max file descriptors
```

**Solutions**:

1. **Disable Unused Accounts**:
   ```bash
   # Via database
   sqlite3 email_manager.db "UPDATE accounts SET is_active=0 WHERE email_address='old@account.com';"

   # Via dashboard
   # Accounts page → Toggle "Active" switch to OFF
   ```

2. **Increase System Limits** (Linux/Mac):
   ```bash
   # Temporary
   ulimit -n 4096

   # Permanent (add to /etc/security/limits.conf)
   * soft nofile 4096
   * hard nofile 8192
   ```

3. **Reduce Watchers Per Application Instance**:
   - Run multiple application instances (different ports)
   - Distribute accounts across instances
   - Use load balancer for web interface

### Manual Reconnection Procedures

**When to Use**:
- Watcher stuck in failed state
- Changed email credentials
- Network configuration changed
- Provider reports "too many connections"

**Procedure 1: Graceful Restart (Recommended)**:
```bash
# Via dashboard
1. Go to Watchers page
2. Click "Stop" button on affected account
3. Wait 5 seconds
4. Click "Start" button
5. Verify status changes to "IDLE" or "POLLING"

# Via API
curl -b cookie.txt -X POST http://localhost:5000/api/accounts/1/monitor/stop
sleep 5
curl -b cookie.txt -X POST http://localhost:5000/api/accounts/1/monitor/start
```

**Procedure 2: Force Restart (If Graceful Fails)**:
```bash
# Stop application
taskkill /F /IM python.exe  # Windows
# or
pkill -f "python.*simple_app.py"  # Linux/Mac

# Wait for connections to close
sleep 10

# Restart application
python simple_app.py

# Watchers auto-start for all active accounts
```

**Procedure 3: Emergency Reset (Nuclear Option)**:
```bash
# 1. Stop application
taskkill /F /IM python.exe

# 2. Reset circuit breakers
sqlite3 email_manager.db "UPDATE accounts SET circuit_open=0, circuit_fail_count=0;"

# 3. Clear any stuck locks (if using file-based locks)
rm -f data/*.lock

# 4. Restart application
python simple_app.py

# 5. Verify all watchers started
curl http://localhost:5000/api/watchers/overview
```

**Verification After Reconnection**:
```bash
# Check watcher status
curl http://localhost:5000/api/watchers/overview | jq '.watchers[] | {account_id, status, mode, last_heartbeat}'

# Check logs for errors
tail -f app.log | grep -i "error\|fail"

# Test interception
# Send test email with keyword → verify appears in Held queue
```

## Related Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment guide
- **[SECURITY.md](SECURITY.md)** - Security configuration
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture
- **[TESTING.md](TESTING.md)** - Testing strategy
