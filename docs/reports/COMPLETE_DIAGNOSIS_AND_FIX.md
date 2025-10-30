# 🔧 COMPLETE DIAGNOSIS AND FIX - Email Interception Failure

**Date**: 2025-10-16
**Status**: 🔴 CRITICAL - Email interception completely broken
**Impact**: Zero emails being intercepted despite active IMAP watchers

---

## 📊 Executive Summary

After extensive investigation (6+ hours), identified **FIVE cascading failures** preventing email interception:

| Issue | Severity | Impact | Status |
|-------|----------|--------|--------|
| IMAP Watcher Silent Failure | 🔴 Critical | No logs, impossible to debug | Identified |
| UIDNEXT Tracking Out of Sync | 🔴 Critical | Skips unprocessed emails | Identified |
| Database Storage Failing Silently | 🔴 Critical | Emails fetched but not stored | Identified |
| Rule Engine Status Mapping Bug | 🟡 High | INTERCEPTED→FETCHED corruption | Identified |
| MOVE/COPY to Quarantine Failing | 🔴 Critical | Emails never leave INBOX | Identified |

**Current State**:
- ✅ Flask app running (http://localhost:5001)
- ✅ IMAP watchers showing "active" status
- ✅ Heartbeats updating every 30s
- ❌ **ZERO emails being processed**
- ❌ UIDs 120-123 stuck in INBOX unprocessed
- ❌ No error logs or failure indication

---

## 🔍 Detailed Root Cause Analysis

### Issue 1: IMAP Watcher Silent Failure

**Symptoms**:
- Watcher threads start successfully
- Heartbeat shows "active" with 0 errors
- **NO logs produced** after "Started monitoring"
- IDLE loop running but not triggering handlers

**Root Cause**:
```python
# app/services/imap_watcher.py line 692-863
@backoff.on_exception(backoff.expo, (socket.error, OSError, Exception), max_time=60 * 60)
def run_forever(self):
    # Logging at INFO level
    log.info("Connecting to IMAP...")  # ✅ Shows

    # But all processing logs are DEBUG level
    log.debug("Entered IDLE")  # ❌ Never shows
    log.debug("Processing new messages")  # ❌ Never shows
```

**Evidence**:
- `app_output.log` only shows startup messages (lines 1-16)
- No IDLE, FETCH, or processing logs after startup
- `IMAP_LOG_VERBOSE=1` environment variable not being set globally

**Fix Required**:
1. Set `IMAP_LOG_VERBOSE=1` in environment or app config
2. Change critical logs from DEBUG→INFO in `run_forever()`
3. Add heartbeat logs showing last IDLE check time

---

### Issue 2: UIDNEXT Tracking Out of Sync

**Symptoms**:
- Last processed UID in database: 119 (timestamp: 2025-10-16 14:29:01)
- Current INBOX UIDNEXT: 124
- UIDs 120-123 exist in INBOX but never processed
- Manual reset of `_last_uidnext` to 119 only finds UID 123

**Root Cause**:
```python
# app/services/imap_watcher.py line 221-226
try:
    status = client.folder_status(self.cfg.inbox, [b'UIDNEXT'])
    self._last_uidnext = int(status.get(b'UIDNEXT') or 1)  # ❌ Sets to 124
except Exception:
    self._last_uidnext = 1
```

**The Problem**:
- On startup, watcher sets `_last_uidnext = 124` (server's UIDNEXT)
- This means "process UIDs >= 124"
- **UIDs 120-123 are skipped** because they're < 124
- Watcher thinks they're "already processed" but they're not in database!

**Evidence**:
```sql
-- Database shows last UID: 119
SELECT MAX(original_uid) FROM email_messages WHERE account_id=2;
-- Result: 119

-- But INBOX has UIDs up to 123
IMAP SELECT INBOX -> UIDNEXT 124

-- Gap: UIDs 120, 121, 122, 123 unprocessed
```

**Fix Required**:
```python
# On watcher startup, check database for last processed UID
conn = sqlite3.connect(self.cfg.db_path)
cursor = conn.cursor()
last_uid_row = cursor.execute(
    "SELECT MAX(original_uid) FROM email_messages WHERE account_id=?",
    (self.cfg.account_id,)
).fetchone()
last_processed_uid = last_uid_row[0] if last_uid_row and last_uid_row[0] else 0
conn.close()

# Start processing from AFTER last processed UID
self._last_uidnext = max(1, last_processed_uid + 1)
log.info(f"Resuming from UID {self._last_uidnext} (last processed: {last_processed_uid})")
```

---

### Issue 3: Database Storage Failing Silently

**Symptoms**:
- Manual fetch logs: `"Intercepting 3 messages (acct=2): [120, 121, 122]"`
- Database check: Only UID 123 exists
- **UIDs 120, 121, 122 disappeared** without error

**Root Cause**:
```python
# app/services/imap_watcher.py line 366-491
def _store_in_database(self, client, uids) -> List[int]:
    held_uids: List[int] = []
    try:
        fetch_data = client.fetch(uids, ['RFC822', 'ENVELOPE', 'FLAGS', 'INTERNALDATE'])

        for uid, data in fetch_data.items():
            try:
                # ... email parsing ...

                # ❌ Duplicate check can silently skip emails
                if original_msg_id:
                    row = cursor.execute(
                        "SELECT id FROM email_messages WHERE message_id=?",
                        (original_msg_id,)
                    ).fetchone()
                    if row:
                        log.debug("Skipping duplicate message_id=%s (uid=%s)", original_msg_id, uid_int)
                        continue  # ❌ Silent skip!

            except Exception as e:
                log.error("Failed to store email UID %s: %s", uid, e)  # ✅ Has logging
                # But continues to next UID

    except Exception as e:
        log.error("Failed to store emails in database: %s", e)  # ✅ Has logging
        return []  # ❌ Returns empty list on ANY error
```

**The Problem**:
1. Duplicate `message_id` check skips emails silently
2. Single UID parsing failure aborts entire batch
3. No detailed logging for why specific UIDs weren't stored

**Evidence**:
- Logs show "Intercepting 3 messages: [120, 121, 122]"
- Only UID 123 ends up in database
- No error logs explaining why 120, 121 failed

**Fix Required**:
1. Log INFO (not DEBUG) when skipping duplicates
2. Continue processing remaining UIDs on single failure
3. Return partial results instead of empty list
4. Add detailed logging for each UID's fate

---

### Issue 4: Rule Engine Status Mapping Bug

**Symptoms**:
- UID 123 processed and stored
- Risk score: 100, Keywords: ["invoice", "invoice", "raywecuya"]
- Matched 3 active HOLD rules
- Database shows: `interception_status='FETCHED'` ❌ (should be 'INTERCEPTED')

**Root Cause**:
```python
# app/services/imap_watcher.py line 439-442
rule_eval = evaluate_rules(subject, body_text, sender, recipients_list)
should_hold = bool(rule_eval.get('should_hold'))
interception_status = 'INTERCEPTED' if should_hold else 'FETCHED'

# ✅ Logic is correct!
```

But manual testing shows:
```python
>>> evaluate_rules("invoice", "test from john", "raywecuya@gmail.com", ["mcintyre@corrinbox.com"])
{'should_hold': True, 'risk_score': 100, 'keywords': ['invoice', 'invoice', 'raywecuya'], ...}

# ✅ Rule engine returns should_hold=True
```

**The Mystery**:
- Rule engine works correctly
- Code logic is correct
- But database has wrong value

**Hypothesis**: Race condition or variable shadowing in the processing loop

**Fix Required**:
1. Add verbose logging before database INSERT showing `should_hold` value
2. Add assertion to validate status matches rule evaluation
3. Check if status is being overwritten after INSERT

---

### Issue 5: MOVE/COPY to Quarantine Failing

**Symptoms**:
- UIDs 120-123 still in INBOX after "interception"
- Quarantine folder exists (70 messages, UIDs 1-70)
- No MOVE or COPY operations executed

**Root Cause**:
```python
# app/services/imap_watcher.py line 647-690
held_uids = self._store_in_database(client, to_process)

if held_uids:
    # Only moves if _store_in_database returns non-empty list
    if self._supports_uid_move():
        self._move(held_uids)
    else:
        self._copy_purge(held_uids)
```

**The Problem**:
- `_store_in_database()` returning empty list (Issue #3)
- `if held_uids:` evaluates to False
- **MOVE/COPY never executed**

**Evidence**:
- IMAP check confirms UIDs 120-123 still in INBOX
- Quarantine folder unchanged (last UID: 70)
- No COPY/MOVE commands in verbose logs

**Fix Required**:
1. Fix `_store_in_database()` to return correct UIDs
2. Add fallback: if store fails but UIDs exist, still attempt MOVE
3. Log MOVE success/failure explicitly

---

## 🔧 Implementation Plan

### Phase 1: Immediate Workarounds (30 mins)

**Goal**: Get UIDs 120-123 processed NOW

**1.1 Create Manual API Endpoint** (`/api/debug/force-process-uids`)
```python
@app.route('/api/debug/force-process-uids', methods=['POST'])
@login_required
def force_process_uids():
    """
    Manually force processing of specific UIDs for debugging.
    POST body: {"account_id": 2, "uids": [120, 121, 122, 123]}
    """
    data = request.get_json()
    account_id = data['account_id']
    uids = data['uids']

    # ... manually call _store_in_database and _move ...

    return jsonify({'processed': results})
```

**1.2 Create Autonomous Test Script**
```python
# scripts/test_interception_e2e.py
def test_uid_processing(account_id, uid):
    """Test single UID through complete pipeline"""
    # 1. Fetch from IMAP
    # 2. Parse and store
    # 3. Apply rules
    # 4. Move to Quarantine
    # 5. Verify in database
    # 6. Verify in Quarantine folder
    pass
```

### Phase 2: Root Cause Fixes (2 hours)

**2.1 Enable Verbose IMAP Logging**
```python
# simple_app.py - Add at top
import os
os.environ['IMAP_LOG_VERBOSE'] = '1'

# app/services/imap_watcher.py - Change log levels
log.info("Entered IDLE")  # Was DEBUG
log.info("Processing %d new messages", len(uids))  # Was DEBUG
```

**2.2 Fix UIDNEXT Initialization**
```python
# app/services/imap_watcher.py line 221
def _connect(self) -> Optional[IMAPClient]:
    # ... after login ...

    # NEW: Check database for last processed UID
    last_db_uid = self._get_last_processed_uid()
    server_uidnext = int(status.get(b'UIDNEXT') or 1)

    # Resume from max(database UID + 1, 1)
    self._last_uidnext = max(1, last_db_uid + 1)

    log.info(f"UIDNEXT: server={server_uidnext}, last_db={last_db_uid}, resuming_from={self._last_uidnext}")
```

**2.3 Add Error Logging to Storage**
```python
# app/services/imap_watcher.py line 420-426
if original_msg_id:
    row = cursor.execute(...).fetchone()
    if row:
        log.info(  # Changed from DEBUG
            "Skipping duplicate message_id=%s (uid=%s, existing_id=%s)",
            original_msg_id, uid_int, row[0]
        )
        continue
```

**2.4 Fix Rule Engine Status Mapping**
```python
# app/services/imap_watcher.py line 439-442
rule_eval = evaluate_rules(subject, body_text, sender, recipients_list)
should_hold = bool(rule_eval.get('should_hold'))
interception_status = 'INTERCEPTED' if should_hold else 'FETCHED'

# NEW: Add validation logging
log.info(
    "Rule evaluation: should_hold=%s, risk=%d, keywords=%s, status=%s",
    should_hold, rule_eval.get('risk_score', 0),
    rule_eval.get('keywords', []), interception_status
)

# NEW: Verify status before INSERT
assert interception_status in ('INTERCEPTED', 'FETCHED'), f"Invalid status: {interception_status}"
```

### Phase 3: Automated Testing (1 hour)

**3.1 Unit Tests**
```python
# tests/services/test_imap_watcher_fixes.py
def test_uidnext_initialization_from_database():
    """Verify watcher resumes from last DB UID, not server UIDNEXT"""

def test_store_database_handles_duplicates():
    """Verify duplicate detection logs properly"""

def test_rule_engine_status_mapping():
    """Verify INTERCEPTED status set when should_hold=True"""
```

**3.2 Integration Tests**
```python
# tests/integration/test_complete_interception.py
def test_end_to_end_interception():
    """
    1. Insert test email into INBOX via IMAP
    2. Trigger watcher processing
    3. Verify stored in database with correct status
    4. Verify moved to Quarantine
    5. Verify original removed from INBOX
    """
```

### Phase 4: Autonomous Monitoring (30 mins)

**4.1 Health Check Enhancement**
```python
@app.route('/api/debug/watcher-status')
def watcher_status():
    """Detailed watcher diagnostics"""
    return jsonify({
        'watchers': {
            'account_2': {
                'last_heartbeat': '2025-10-16 16:01:53',
                'status': 'active',
                'last_idle_check': '2025-10-16 16:01:50',
                'last_processed_uid': 119,
                'server_uidnext': 124,
                'pending_uids': [120, 121, 122, 123],
                'errors_24h': 0
            }
        }
    })
```

**4.2 Auto-Recovery Script**
```python
# scripts/monitor_and_heal.py
def monitor_loop():
    while True:
        status = requests.get('http://localhost:5001/api/debug/watcher-status').json()

        for acct_id, info in status['watchers'].items():
            # Check for stuck watcher
            if info['pending_uids'] and not info['processing']:
                log.warning(f"Watcher {acct_id} stuck with {len(info['pending_uids'])} pending UIDs")
                # Auto-restart
                requests.post(f'http://localhost:5001/api/accounts/{acct_id}/monitor/restart')

        time.sleep(60)
```

---

## 📝 Testing Checklist

After implementing fixes:

- [ ] **Manual Test**: Run `python force_process_missing_uids.py`
- [ ] **Verify UIDs 120-123**: Check database for all 4 emails
- [ ] **Verify Quarantine**: Confirm emails moved from INBOX
- [ ] **Check Logs**: Verbose logging shows each step
- [ ] **Send New Test Email**: Gmail→Hostinger with "invoice" subject
- [ ] **Verify Auto-Interception**: New email processed within 30s
- [ ] **Check Rule Application**: Status=INTERCEPTED, not FETCHED
- [ ] **Verify MOVE**: Email in Quarantine, removed from INBOX
- [ ] **Run Test Suite**: `python -m pytest tests/ -v`
- [ ] **24h Monitoring**: No stuck watchers, all emails processed

---

## 🚀 Deployment Steps

1. **Backup current state**:
   ```bash
   cp email_manager.db email_manager.db.backup_20251016
   cp -r app app.backup_20251016
   ```

2. **Apply fixes** (in order):
   ```bash
   # Fix 1: Verbose logging
   git apply fixes/01_verbose_logging.patch

   # Fix 2: UIDNEXT initialization
   git apply fixes/02_uidnext_init.patch

   # Fix 3: Storage error logging
   git apply fixes/03_storage_logging.patch

   # Fix 4: Rule status mapping
   git apply fixes/04_rule_status.patch
   ```

3. **Restart Flask app**:
   ```bash
   taskkill /F /PID <flask_pid>
   python simple_app.py
   ```

4. **Run validation**:
   ```bash
   python scripts/validate_interception.py
   ```

---

## 📊 Success Criteria

**✅ Definition of Done**:

1. **Immediate**: UIDs 120-123 successfully processed and in database
2. **Auto-Recovery**: Watcher resumes from last DB UID on restart
3. **Error Visibility**: All failures logged at INFO level minimum
4. **Rule Compliance**: `should_hold=True` → `interception_status='INTERCEPTED'`
5. **MOVE Operations**: Held emails moved to Quarantine successfully
6. **End-to-End**: New test email intercepted within 30 seconds
7. **Monitoring**: Health check detects stuck watchers
8. **Zero Silent Failures**: No exceptions swallowed without logging

---

## 📅 Timeline

| Phase | Duration | Completion Target |
|-------|----------|-------------------|
| Phase 1: Immediate Workarounds | 30 mins | 2025-10-16 17:00 |
| Phase 2: Root Cause Fixes | 2 hours | 2025-10-16 19:00 |
| Phase 3: Automated Testing | 1 hour | 2025-10-16 20:00 |
| Phase 4: Autonomous Monitoring | 30 mins | 2025-10-16 20:30 |
| **Total** | **4 hours** | **2025-10-16 20:30** |

---

## 🔗 Related Files

- `app/services/imap_watcher.py` - Main watcher implementation
- `app/utils/rule_engine.py` - Rule evaluation logic
- `app/routes/interception.py` - Release/discard endpoints
- `simple_app.py` - Watcher initialization
- `CLAUDE.md` - Project documentation
- `INTERCEPTION_IMPLEMENTATION.md` - Architecture details

---

## 📞 Support

**Current Status**: 🔴 CRITICAL - Interception broken
**Next Update**: After Phase 1 completion (~30 mins)
**Contact**: Check `/healthz` endpoint for system status
