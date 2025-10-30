# Live Testing Validation Checklist - Gmail Duplicate Fix

**Version**: 2.8
**Test Date**: _________________
**Tester**: _________________
**Fix**: Prevent duplicate emails (original + edited) appearing in Gmail INBOX after release

---

## Pre-Test Setup

### 1. Restart Application
- [ ] Stop all running instances: `taskkill /F /IM python.exe` (or graceful shutdown)
- [ ] Clear any cached processes
- [ ] Start fresh: `python simple_app.py`
- [ ] Verify app running: `http://localhost:5000/healthz`

### 2. Enable Debug Logging
```bash
# In .env or environment
LOG_LEVEL=DEBUG
IMAP_LOG_VERBOSE=1
```
- [ ] Set debug logging
- [ ] Restart application
- [ ] Verify logs show `[DEBUG]` entries

### 3. Gmail IMAP Settings
- [ ] Login to Gmail → Settings → Forwarding and POP/IMAP
- [ ] Verify "Enable IMAP" is checked
- [ ] Verify "Auto-Expunge" is ON
- [ ] Check `[Gmail]/All Mail` is visible in IMAP client (optional)

### 4. Application Health Check
```bash
curl http://localhost:5000/healthz
```
Expected response:
- [ ] `"ok": true`
- [ ] `"held_count"` present
- [ ] `"smtp"` listening: true
- [ ] At least 1 active `"workers"`

---

## Test Path 1: Gmail Account (Primary Test)

### Account Details
- **Email**: `ndayijecika@gmail.com`
- **IMAP Host**: `imap.gmail.com:993`
- **Expected Behavior**: Only edited email in INBOX after release

### Steps

#### Step 1: Send Test Email
- [ ] Send email TO `ndayijecika@gmail.com` with trigger keyword (e.g., subject contains "HOLD")
- [ ] Subject example: "HOLD Test Email - [timestamp]"
- [ ] Body example: "Original body content for testing"
- [ ] Note the timestamp/unique identifier: _______________

#### Step 2: Verify Interception
- [ ] Check Gmail INBOX web interface → email should NOT appear
- [ ] Check app dashboard `http://localhost:5000/dashboard`
- [ ] Email shows in "Held" queue with status `HELD`
- [ ] Click on email → note the **original Message-ID**: _______________

#### Step 3: Edit Email
- [ ] Click "Edit" button on held email
- [ ] Change subject to: "EDITED: [original subject]"
- [ ] Change body to: "This email was edited and approved"
- [ ] Save edits
- [ ] Verify edits persisted in dashboard

#### Step 4: Release Email
- [ ] Click "Release" button
- [ ] Observe response (should be HTTP 200)
- [ ] Wait 5-10 seconds for IMAP sync

#### Step 5: Verify Results

**Gmail INBOX (Web Interface)**:
- [ ] Exactly ONE message appears
- [ ] Subject is the EDITED version: "EDITED: ..."
- [ ] Body is the EDITED version: "This email was edited..."
- [ ] NO duplicate/original email visible

**Gmail All Mail (Web Interface)**:
- [ ] Search for original Message-ID: `_______________`
- [ ] Original should be in Trash or not found
- [ ] Only edited version should be in All Mail

**Application Logs**:
- [ ] Search logs for: `[Gmail] Original purged from All Mail`
- [ ] Log includes: `email_id=X, uids=['...'], mbox='[Gmail]/All Mail'`
- [ ] NO warnings: `Could not remove original message from quarantine`

**Dashboard**:
- [ ] Email status changed to `RELEASED`
- [ ] Quarantine folder empty for this message

### Success Criteria
✅ **PASS** if:
- Only edited email in Gmail INBOX
- Original NOT in Gmail INBOX
- Original in Trash or purged from All Mail
- Logs show successful All Mail purge

❌ **FAIL** if:
- Both original AND edited appear in INBOX
- Original still in All Mail with Inbox label
- Missing log line for All Mail purge

---

## Test Path 2: Hostinger Account (Regression Test)

### Account Details
- **Email**: `mcintyre@corrinbox.com`
- **IMAP Host**: `imap.hostinger.com:993`
- **Expected Behavior**: Only edited email in INBOX (no Gmail-specific code runs)

### Steps

#### Step 1: Send Test Email
- [ ] Send email TO `mcintyre@corrinbox.com` with trigger keyword
- [ ] Subject: "HOLD Hostinger Test - [timestamp]"
- [ ] Note timestamp: _______________

#### Step 2: Verify Interception
- [ ] Check Hostinger webmail → email NOT in INBOX
- [ ] App dashboard shows email as `HELD`

#### Step 3: Edit & Release
- [ ] Edit subject: "EDITED: [original subject]"
- [ ] Edit body: "Hostinger edited content"
- [ ] Release email

#### Step 4: Verify Results

**Hostinger INBOX**:
- [ ] Exactly ONE message appears
- [ ] Subject is EDITED version
- [ ] NO duplicate email

**Application Logs**:
- [ ] NO Gmail-specific log lines (`[Gmail]`)
- [ ] Standard cleanup logs present
- [ ] NO errors or warnings

### Success Criteria
✅ **PASS** if:
- Only edited email in INBOX
- No Gmail-specific code executed
- Clean logs without errors

---

## Code Verification Checklist

### Safety Checks
- [ ] Cleanup uses **only** `original_message_id` (not `message_id_hdr`)
- [ ] Gmail block runs **only if** `'gmail' in imap_host.lower()`
- [ ] All Mail purge wrapped in `if gmail_purge_enabled:` check
- [ ] Default `GMAIL_ALL_MAIL_PURGE=1` (enabled)

### Gmail Purge Logic
- [ ] Selects `[Gmail]/All Mail` or `[Google Mail]/All Mail`
- [ ] UID SEARCH by `HEADER "Message-ID" <original>`
- [ ] Three STORE operations with parentheses:
  - `imap.uid('STORE', uid, '-X-GM-LABELS', r'(\Inbox)')`
  - `imap.uid('STORE', uid, '-X-GM-LABELS', r'(Quarantine)')`
  - `imap.uid('STORE', uid, '+X-GM-LABELS', r'(\Trash)')`
- [ ] INBOX and Quarantine cleanup run BEFORE All Mail cleanup

---

## Edge Cases to Test (Optional)

### Threaded Conversations
- [ ] Send 2 emails with same subject, different Message-IDs
- [ ] Hold and release one
- [ ] Verify only the specific original is purged (not the entire thread)

### Multiple Recipients
- [ ] Send email TO and CC same Gmail account
- [ ] Verify both are handled correctly

### Important/Starred Labels
- [ ] Star an email before interception
- [ ] Verify purge still works despite extra labels

---

## Emergency Rollback Test

### Disable Gmail Purge
```bash
# Set environment variable
GMAIL_ALL_MAIL_PURGE=0
```
- [ ] Restart application
- [ ] Repeat Gmail test
- [ ] Verify INBOX/Quarantine cleanup still works
- [ ] Verify All Mail purge SKIPPED (no log line)

---

## Final Sign-Off

### Test Results Summary
- **Gmail Test**: ☐ PASS ☐ FAIL
- **Hostinger Test**: ☐ PASS ☐ FAIL
- **Code Verification**: ☐ PASS ☐ FAIL
- **Edge Cases** (if tested): ☐ PASS ☐ FAIL ☐ N/A

### Issues Found
(List any problems discovered during testing)
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________

### Recommendations
- [ ] Ready for production deployment
- [ ] Needs additional testing
- [ ] Requires code changes

---

**Tester Signature**: _____________________ **Date**: _______

**Reviewer Signature**: ___________________ **Date**: _______

---

## Quick Reference: Log Commands

**Tail logs in real-time**:
```bash
tail -f logs/app.log | grep -i "gmail\|release\|purge"
```

**Search for specific email ID**:
```bash
grep "email_id=123" logs/app.log
```

**Check All Mail purge success**:
```bash
grep "Original purged from All Mail" logs/app.log
```

**Verify no duplicates warnings**:
```bash
grep -i "duplicate\|both.*inbox" logs/app.log
```
