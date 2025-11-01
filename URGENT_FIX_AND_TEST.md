# URGENT: Interception Debugging Guide

## Current Status (as of 2:43 PM, Oct 31)

### ✅ What's Working:
- Rule engine: PERFECT (tested directly, matches "invoice")
- Invoice rule: ACTIVE (priority 75)
- App: RUNNING
- IMAP watcher: RUNNING (last check: 2:17 PM)

### ❌ What's NOT Working:
- Live emails with "invoice" NOT being intercepted
- Test suite shows FALSE POSITIVES (checks wrong DB column)

### 🎯 Root Causes Identified:

**Bug #1: Test Suite False Positive**
- File: `app/routes/diagnostics.py:167`
- Bug: Checks `status='PENDING'` instead of `interception_status='INTERCEPTED'`
- Impact: Test claims success even when interception failed

**Bug #2: Unknown Issue in Live IMAP Flow**
- Emails sent during tests are NOT appearing in database
- Latest email in DB: ID 121, UID 205 (from earlier)
- Need to verify: Did test emails actually arrive in inbox?

---

## Step-by-Step Debugging Protocol

### STEP 1: Verify Email Delivery

**Action:** Manually check the mcintyre@corrinbox.com inbox

1. Log into https://webmail.hostinger.com
2. Username: `mcintyre@corrinbox.com`
3. Check INBOX for emails with "invoice" in subject
4. Note the MESSAGE COUNT in inbox

**Expected:** If you sent test emails, they should be visible in webmail

**If NOT visible:** Problem is email sending, not interception

---

### STEP 2: Check Current Max UID

The database shows latest UID = 205. If there are new emails in the inbox, they'll have UID > 205.

**Run this script to check:**

```python
# check_real_inbox_uids.py
from imapclient import IMAPClient
import os

# Decrypt credentials
from app.utils.crypto import decrypt_credential
import sqlite3

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

account = cur.execute("""
    SELECT imap_host, imap_port, imap_username, imap_password
    FROM email_accounts
    WHERE email_address = 'mcintyre@corrinbox.com'
""").fetchone()

if not account:
    print("Account not found!")
    exit(1)

# Decrypt password
password = decrypt_credential(account['imap_password'])

# Connect to IMAP
client = IMAPClient(account['imap_host'], port=account['imap_port'], ssl=True)
client.login(account['imap_username'], password)
client.select_folder('INBOX')

# Get all UIDs
uids = client.search('ALL')
print(f"Total emails in INBOX: {len(uids)}")
print(f"UID range: {min(uids)} - {max(uids)}")
print(f"Latest UID in DB: 205")

if max(uids) > 205:
    print(f"\n✅ NEW EMAILS FOUND! UIDs 206-{max(uids)} not in database")
    print(f"   This means IMAP watcher failed to fetch them")
    
    # Get subjects of unfetched emails
    unfetched = [uid for uid in uids if uid > 205]
    fetch_data = client.fetch(unfetched, ['ENVELOPE'])
    
    print(f"\n📧 Unfetched emails:")
    for uid, data in fetch_data.items():
        envelope = data[b'ENVELOPE']
        subject = envelope.subject.decode() if envelope.subject else "(no subject)"
        print(f"   UID {uid}: {subject}")
else:
    print(f"\n❌ No new emails beyond UID 205")
    print(f"   Either:")
    print(f"   - Test emails never arrived")
    print(f"   - They went to a different folder")

client.logout()
conn.close()
```

---

### STEP 3: Fix Test Suite Bug

**File:** `app/routes/diagnostics.py`  
**Line:** 167  
**Current:**
```python
WHERE subject = ? AND status = 'PENDING'
```

**Fix to:**
```python
WHERE subject = ? AND interception_status = 'INTERCEPTED'
```

---

### STEP 4: If Emails ARE in Inbox But Not in DB

This means IMAP watcher has a bug. Check:

1. **Server logs for errors:**
   ```bash
   grep -i "error\|exception\|failed" server5001.log | tail -50
   ```

2. **IMAP watcher fetch logs:**
   ```bash
   grep -i "UID=\|PRE-INSERT\|INTERCEPTED" server5001.log | tail -50
   ```

3. **Database connection errors:**
   Check if there are sqlite locking issues

---

### STEP 5: Manual Trigger IMAP Fetch

Force the IMAP watcher to fetch NOW:

```python
# force_imap_fetch.py
import sqlite3
from app.services.imap_watcher import ImapWatcher, AccountConfig
from app.utils.crypto import decrypt_credential

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

account = cur.execute("""
    SELECT * FROM email_accounts
    WHERE email_address = 'mcintyre@corrinbox.com'
""").fetchone()

# Decrypt credentials
username = decrypt_credential(account['imap_username'])
password = decrypt_credential(account['imap_password'])

# Create watcher config
cfg = AccountConfig(
    account_id=account['id'],
    imap_host=account['imap_host'],
    imap_port=account['imap_port'],
    imap_username=username,
    imap_password=password,
    imap_use_ssl=account['imap_use_ssl'],
    db_path='email_manager.db'
)

# Create watcher and run ONE fetch cycle
watcher = ImapWatcher(cfg)
print("Starting manual IMAP fetch...")

try:
    # This will fetch new emails
    watcher.run()  # Runs one cycle
    print("✅ Fetch completed!")
except Exception as e:
    print(f"❌ Fetch failed: {e}")
    import traceback
    traceback.print_exc()

conn.close()

# Now check if new emails appeared
print("\nChecking for new emails...")
conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

latest = cur.execute("""
    SELECT id, subject, interception_status, risk_score, original_uid
    FROM email_messages
    ORDER BY id DESC LIMIT 5
""").fetchall()

print(f"\nLatest 5 emails:")
for e in latest:
    print(f"  ID {e['id']} (UID {e['original_uid']}): {e['subject']} | {e['interception_status']} | Risk={e['risk_score']}")

conn.close()
```

---

## Quick Fix Checklist

- [ ] Fix test suite bug (diagnostics.py:167)
- [ ] Verify emails in webmail inbox
- [ ] Check max UID vs DB UID 205
- [ ] Run manual IMAP fetch
- [ ] Verify new emails get intercepted properly
- [ ] Test with fresh "invoice" email
- [ ] Capture screenshots for evidence

---

## Expected Behavior After Fix

When you send:
```
From: ndayijecika@gmail.com
To: mcintyre@corrinbox.com
Subject: TEST INVOICE #123
```

You should see in DB:
```sql
interception_status = 'INTERCEPTED'
risk_score = 75
keywords_matched = ['invoice']
```

---

## Files Created for Debugging

1. `diagnose_interception_live.py` - Full system diagnostic
2. `check_imap_watcher_health.py` - IMAP watcher status
3. `check_recent_tests.py` - Find recent test emails
4. `simulate_imap_watcher.py` - Reproduce watcher logic
5. `INTERCEPTION_ANALYSIS.md` - Full investigation report
6. This file: `URGENT_FIX_AND_TEST.md`
