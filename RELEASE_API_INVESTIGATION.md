# Release API 500 Error - Investigation Summary

## Issue Description
User reported that the Release API (`/api/interception/release/<email_id>`) returns 500 errors with no error logging for certain email IDs (specifically email ID 120).

## Investigation Timeline

### Initial Discovery
From logs dated 2025-10-19 11:18:24:
```
2025-10-19 11:18:24,416 INFO HTTP POST /api/interception/release/120
2025-10-19 11:18:24,417 INFO [Release DEBUG] entered release handler
2025-10-19 11:18:24,417 INFO HTTP POST /api/interception/release/120 -> 500
```

**Key Observation**: Error occurs in the **same millisecond** after entering handler, with NO error logs captured.

### Root Cause Analysis

1. **Email ID 120 Status**: Email ID 120 no longer exists in the database (confirmed via database query)

2. **Code Flow Analysis**:
   - Line 1573-1582: Database query with JOIN to email_accounts table
   - Line 1582: `if not row: return jsonify({'ok': False, 'reason': 'not-found'}), 404`
   - Line 1584: `app_log.debug("Entered release handler")` ✅ This log appeared
   - Line 1586-1616: Multiple `row['field']` accesses **WITHOUT try/catch**
   - Line 1663+: IMAP connection code (has try/catch)

3. **Critical Finding**: The error happens between lines 1584-1663, in the early validation section that had **NO exception handling**.

### Enhanced Error Handling Implemented

#### Changes Made to `app/routes/interception.py`:

**1. Added try/catch around interception_status validation (lines 1586-1593)**:
```python
try:
    app_log.debug(f"[Release DEBUG] Checking interception_status for email {msg_id}")
    interception_status = str((row['interception_status'] or '')).upper()
    app_log.debug(f"[Release DEBUG] Interception status: {interception_status}")
except Exception as e:
    app_log.error(f"[Release ERROR] Failed to get interception_status: {e}", exc_info=True)
    return jsonify({'ok': False, 'error': f'Failed to read status: {str(e)}'}), 500
```

**2. Added try/catch around raw message loading (lines 1608-1616)**:
```python
try:
    app_log.debug(f"[Release DEBUG] Loading raw message for email {msg_id}")
    raw_path = row['raw_path']
    raw_content = row['raw_content']
    app_log.debug(f"[Release DEBUG] Raw path: {raw_path}, Raw content length: {len(raw_content) if raw_content else 0}")
except Exception as e:
    app_log.error(f"[Release ERROR] Failed to access raw message fields: {e}", exc_info=True)
    return jsonify({'ok': False, 'error': f'Failed to access raw message: {str(e)}'}), 500
```

### Benefits

1. **Detailed Error Logging**: Any exceptions in early validation now log:
   - Email ID
   - Exact operation that failed
   - Full exception details with stack trace
   - exc_info=True for complete traceback

2. **Proper Error Responses**: Instead of generic 500 errors, now returns:
   ```json
   {"ok": false, "error": "Failed to read status: <specific error>"}
   ```

3. **Debug Checkpoints**: Added debug logs at each major operation:
   - "Checking interception_status for email X"
   - "Interception status: HELD/RELEASED/etc"
   - "Loading raw message for email X"
   - "Raw path: ..., Raw content length: ..."

### Testing Recommendations

To reproduce and verify the fix:

1. **Create test email with corrupt data**:
   ```sql
   INSERT INTO email_messages (id, interception_status, account_id, direction, subject)
   VALUES (9999, 'HELD', NULL, 'inbound', 'Test Corrupt Email');
   ```
   Expected: 500 error with detailed log about missing account_id

2. **Test with missing raw content**:
   ```sql
   UPDATE email_messages SET raw_path=NULL, raw_content=NULL WHERE id=X;
   ```
   Expected: RuntimeError('raw-missing') with full traceback

3. **Monitor logs** for:
   - "[Release DEBUG] Checking interception_status"
   - "[Release ERROR] Failed to..." entries
   - Full Python tracebacks with file:line references

### Files Modified

- `app/routes/interception.py` (lines 1586-1593, 1608-1616)

### Status

✅ Enhanced error logging implemented
✅ Early validation wrapped in try/catch blocks
⏳ Awaiting production testing to verify error capture

### Next Steps

1. Monitor production logs for any "[Release ERROR]" entries
2. If errors occur, the detailed logs will show:
   - Exact line where error occurred
   - Email ID being processed
   - Full exception details
3. Apply similar defensive error handling to other early validation sections if needed
