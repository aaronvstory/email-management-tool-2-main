# Gmail Release Flow - Smoke Test Guide

**Date**: 2025-10-19
**Purpose**: End-to-end validation of Gmail duplicate fix
**Duration**: ~10 minutes

---

## Pre-Test Checklist

✅ All protocol fixes applied (X-GM-LABELS, X-GM-RAW thread:, header: syntax)
✅ Hardening improvements implemented (label fetching, index backoff)
✅ Syntax verified - no compilation errors
✅ Documentation complete

---

## Test Environment Setup

### 1. Start Application

```bash
# Option A: Quick start
python simple_app.py

# Option B: Professional launcher
EmailManager.bat
```

**Verify startup**:
- Web dashboard accessible: http://localhost:5000
- SMTP proxy running: localhost:8587
- No startup errors in console

### 2. Setup Log Monitoring

**Open new terminal** and run:

```bash
tail -f logs/app.log | egrep "PRINT Phase|Phase [ACDE]|X-GM"
```

**Or use PowerShell**:

```powershell
Get-Content logs\app.log -Wait -Tail 50 | Select-String "PRINT Phase|Phase [ACDE]|X-GM"
```

**What to watch for**:
- `[PRINT Phase A]` - Quarantine cleanup
- `[PRINT Phase B]` - APPEND and index backoff
- `[PRINT Phase C]` - Gmail thread cleanup
- `[PRINT Phase E]` - Verification

---

## Smoke Test Procedure

### Test 1: Gmail Release with Edit (Primary Test)

**Account**: ndayijecika@gmail.com

**Step 1: Send Test Email**

Send email TO: `ndayijecika@gmail.com`
- **Subject**: `SMOKE TEST - Gmail Thread Cleanup [TIMESTAMP]`
- **Body**: `Original message for testing Gmail duplicate fix.`
- **From**: Any external email (or self)

**Step 2: Verify Interception**

1. Check logs for IMAP watcher detection
2. Navigate to: http://localhost:5000/dashboard
3. Confirm email appears in "Held Messages"
4. Status should be: `HELD`
5. Folder should be: `Quarantine`

**Step 3: Edit Message**

1. Click "Edit" on the held message
2. Change subject: `EDITED - Gmail Thread Cleanup Test`
3. Change body: `This is the edited version - should be ONLY message in INBOX`
4. Save edits

**Step 4: Release to INBOX**

1. Click "Release to INBOX"
2. Wait for confirmation
3. **Watch logs closely** - expect this sequence:

```
[PRINT Phase A] Starting Quarantine cleanup uid=<NUMBER>
[PRINT Phase A] ✓ Deleted original uid=<NUMBER> from Quarantine
[PRINT Phase B] Appending edited email_id=<ID> to INBOX
[PRINT Phase B] ✓ Append complete
[PRINT Phase B] Gmail index backoff (200ms)
[PRINT Phase C] Starting Gmail thread-level cleanup email_id=<ID>
[PRINT Phase C] Found edited uid=<NUMBER>
[PRINT Phase C] Got thread_id=<THREAD_ID>
[PRINT Phase C] Found <N> messages in thread: [<UIDS>]
[PRINT Phase C] Fetched labels for uid=<NUMBER>: X-GM-LABELS (...)
[PRINT Phase C] Preserving edited uid=<NUMBER>
[PRINT Phase C] Removed \Inbox from uid=<NUMBER>
[PRINT Phase C] ✓ Thread cleanup complete: processed <N> messages, removed <M> labels
[PRINT Phase E] Starting hardened verification email_id=<ID>
[PRINT Phase E] ✓ Edited message found in INBOX
[PRINT Phase E] Checking for Gmail duplicates via thread ID
[PRINT Phase E] Got thread_id=<THREAD_ID> for verification
[PRINT Phase E] Found 1 thread messages in INBOX: [<UID>]  ← KEY: Should be exactly 1!
[PRINT Phase E] ✓ SUCCESS - Only edited message in INBOX
[PRINT Phase E] ✓ Original not in INBOX (correct)
[PRINT Phase E] ✓ VERIFICATION COMPLETE - SUCCESS
```

**Step 5: Verify Gmail Inbox**

1. Open Gmail web interface: https://mail.google.com
2. Check INBOX - should see **EXACTLY 1 MESSAGE**:
   - Subject: `EDITED - Gmail Thread Cleanup Test`
   - Body: `This is the edited version...`
   - **NO DUPLICATE** with original subject/body

3. Check All Mail:
   - Search for original subject
   - Original should exist in All Mail but have **no "Inbox" label**
   - Only edited message should have "Inbox" label

4. Check Quarantine folder:
   - Should be **EMPTY** (original deleted)

**Step 6: Verify Watcher Behavior**

Check logs for watcher skip messages:
```
[IMAP Watcher] Skipping UID=<NUMBER> - has release bypass header
```

The watcher should NOT re-quarantine the edited message.

---

## Success Criteria

### ✅ PASS if:

1. **Phase A logs**: Original deleted from Quarantine by UID
2. **Phase B logs**: APPEND complete + Gmail index backoff (200ms)
3. **Phase C logs**:
   - Got thread ID
   - Found thread messages
   - Fetched labels for each UID
   - Removed `\Inbox` from original
   - Thread cleanup complete
4. **Phase E logs**:
   - Found exactly **1 message** in INBOX thread
   - Verification SUCCESS
5. **Gmail INBOX**: Only 1 message (edited version)
6. **Gmail All Mail**: Original has no Inbox label
7. **Quarantine**: Empty
8. **Watcher**: Skips edited message (release bypass header)

### ❌ FAIL if:

1. **Multiple messages in INBOX** - Thread cleanup didn't work
2. **Phase E reports >1 message** - Duplicate detected
3. **Original still has Inbox label** - Label removal failed
4. **Watcher re-quarantines edited** - Bypass header missing
5. **Protocol errors in logs** - X-GM-LABELS or X-GM-RAW syntax wrong

---

## Test 2: Hostinger Compatibility (Non-Gmail Path)

**Account**: mcintyre@corrinbox.com

**Purpose**: Verify Gmail-specific code doesn't break non-Gmail servers

**Procedure**:

1. Send test email to Hostinger account
2. Intercept → Edit → Release
3. **Watch logs** - expect:

```
[PRINT Phase A] Starting Quarantine cleanup...
[PRINT Phase A] ✓ Deleted original uid=<NUMBER>
[PRINT Phase B] Appending edited email_id=<ID>
[PRINT Phase B] ✓ Append complete
← NO PHASE B BACKOFF (not Gmail)
[PRINT Phase C] Skipped - not Gmail server
← NO PHASE C (not Gmail)
[PRINT Phase E] Thread verification skipped (not Gmail)
← NO PHASE E THREAD CHECK (not Gmail)
[PRINT Phase E] ✓ Edited message found in INBOX
[PRINT Phase E] ✓ VERIFICATION COMPLETE - SUCCESS
```

**Success**: Release works, Gmail phases cleanly skipped

---

## Troubleshooting

### Issue: Phase C reports "Could not find edited UID"

**Cause**: Index lag despite 200ms backoff
**Fix**: Increase backoff to 300ms in line 755:
```python
time.sleep(0.3)  # 300ms instead of 200ms
```

### Issue: Phase C fails with "protocol error"

**Cause**: X-GM-RAW syntax error or X-GM-EXT-1 not supported
**Check**:
1. Verify `X-GM-EXT-1` in Gmail capabilities
2. Check logs for exact error message
3. Verify thread_id format (should be numeric string)

### Issue: Phase E reports >1 message in INBOX

**Cause**: Thread cleanup didn't remove `\Inbox` from original
**Debug**:
1. Check Phase C logs for "Removed \Inbox" confirmation
2. Verify X-GM-LABELS syntax (should be `-X-GM-LABELS`, not `-FLAGS`)
3. Check if label removal returned OK status

### Issue: Original still appears in Gmail INBOX

**Cause**: Label removal silently failed or Gmail hasn't synced yet
**Debug**:
1. Wait 30 seconds and refresh Gmail
2. Check logs for Phase C "Removed \Inbox from uid=X" messages
3. Verify Gmail web UI shows original has no Inbox label (check All Mail)

### Issue: Watcher re-quarantines edited message

**Cause**: Release bypass header missing or not checked
**Debug**:
1. Check release code adds `X-EMT-Release-Bypass` header
2. Verify watcher checks for bypass header
3. Check logs for watcher decision on edited message UID

---

## Post-Test Validation

### Check Database

```sql
SELECT id, subject, interception_status, quarantine_folder, original_uid
FROM email_messages
WHERE subject LIKE '%SMOKE TEST%'
ORDER BY timestamp DESC
LIMIT 5;
```

**Expected**:
- Status: `RELEASED`
- Quarantine folder: `Quarantine` (or custom)
- Original UID: <number>

### Check IMAP Directly (Optional)

```python
import imaplib, ssl

# Connect to Gmail
imap = imaplib.IMAP4_SSL('imap.gmail.com')
imap.login('ndayijecika@gmail.com', '<app-password>')

# Check INBOX for thread
imap.select('INBOX')
typ, data = imap.uid('SEARCH', None, 'SUBJECT', '"SMOKE TEST"')
print(f"INBOX UIDs: {data[0].decode()}")  # Should show exactly 1 UID

# Check labels
for uid in data[0].split():
    typ2, data2 = imap.uid('FETCH', uid, '(X-GM-LABELS)')
    print(f"UID {uid} labels: {data2}")  # Edited should have \Inbox

imap.logout()
```

---

## Clean Up After Test

1. **Delete test emails** from Gmail INBOX and All Mail
2. **Clear database** test entries (optional):
   ```sql
   DELETE FROM email_messages WHERE subject LIKE '%SMOKE TEST%';
   ```
3. **Clear logs** (optional):
   ```bash
   # Backup first
   cp logs/app.log logs/app.log.backup
   # Clear
   > logs/app.log
   ```

---

## Test Results Template

```
SMOKE TEST RESULTS - [DATE]
==========================================

Test 1: Gmail Release with Edit
- [ ] Phase A: Quarantine cleanup OK
- [ ] Phase B: APPEND + index backoff OK
- [ ] Phase C: Thread cleanup OK (labels fetched & removed)
- [ ] Phase E: Verification OK (exactly 1 message)
- [ ] Gmail INBOX: Only edited message
- [ ] Gmail All Mail: Original has no Inbox label
- [ ] Watcher: Skipped edited message

Result: PASS / FAIL
Notes: ___________________________________

Test 2: Hostinger Compatibility
- [ ] Release works normally
- [ ] Gmail phases cleanly skipped
- [ ] No errors or warnings

Result: PASS / FAIL
Notes: ___________________________________

Overall: READY FOR PRODUCTION / NEEDS FIXES
```

---

## Next Steps After Successful Smoke Test

1. ✅ **Smoke Test Passed** - All phases working correctly
2. ⏳ **Unit Tests**: Add Gmail thread cleanup mocks
3. ⏳ **Integration Tests**: Test edge cases (large threads, custom labels)
4. ⏳ **Load Testing**: Multiple concurrent releases
5. ⏳ **Production Deployment**: Roll out with monitoring
6. ⏳ **Monitor**: Watch for Phase E duplicate warnings

---

**Ready to Test!** 🧪

Run the smoke test and paste the Phase C/E print lines here if anything fails. The fixes are solid, but Gmail can be quirky - these logs will help us zero in fast.
