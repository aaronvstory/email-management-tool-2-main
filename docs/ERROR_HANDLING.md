# Error Handling Guide

This document describes the comprehensive error handling strategy implemented to ensure one bad thing never breaks the app.

## Overview

The application now has three layers of error protection:
1. **Backend Safety Net** - Global error handlers and specific exception catching
2. **Frontend Guards** - Safe fetch wrappers and error displays
3. **Data Isolation** - Safe row serialization that skips malformed data

## Backend Safety Net

### Global Exception Handler

All unhandled exceptions are caught and converted to user-friendly JSON responses:

```python
@app.errorhandler(Exception)
def handle_any_error(e):
    """Global safety net: catch all unhandled exceptions"""
    app.logger.exception("Unhandled error")
    try:
        error_type = e.__class__.__name__
        error_msg = str(e)
        if request.is_json:
            return jsonify(ok=False, success=False, error=error_msg, type=error_type), 500
        flash(f'An error occurred: {error_msg}', 'error')
        return render_template('error.html', error=error_msg, error_type=error_type), 500
    except Exception:
        return ('Internal Server Error', 500)
```

**Location:** `simple_app.py` line ~878

### Specific Error Handling for Account Testing

DNS, SSL, and authentication errors are caught separately and return clear messages:

```python
@app.post("/api/accounts/<int:aid>/test")
def test_account(aid):
    try:
        # ... do IMAP/SMTP checks ...
        return jsonify(success=True, imap=imap_result, smtp=smtp_result)
    except socket.gaierror as e:
        return jsonify(success=False, error=f"DNS lookup failed for IMAP/SMTP host: {e}")
    except ssl.SSLError as e:
        return jsonify(success=False, error=f"TLS error: {e}")
    except imaplib.IMAP4.error as e:
        return jsonify(success=False, error=f"IMAP auth failed: {e}")
    except smtplib.SMTPAuthenticationError as e:
        return jsonify(success=False, error=f"SMTP auth failed: {e}")
    except Exception as e:
        return jsonify(success=False, error=f"Unexpected: {e}")
```

**Location:** `app/routes/accounts.py` line ~383

### Safe Row Serialization

When building lists of database rows, malformed rows are skipped instead of crashing:

```python
# app/routes/accounts.py - Safe account list
safe_accounts = []
for raw in rows:
    try:
        safe_accounts.append(dict(raw))
    except Exception as e:
        log.warning(f"Skipping bad account row id={raw.get('id')}: {e}")
return jsonify({'success': True, 'accounts': safe_accounts})
```

**Location:** `app/routes/accounts.py` line ~162

```python
# app/routes/interception.py - Safe attachment serialization
def _serialize_attachment_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Safely serialize attachment row with defaults for missing fields."""
    try:
        return {
            'id': row.get('id') or 0,
            'filename': row.get('filename') or 'unknown',
            'mime_type': row.get('mime_type') or 'application/octet-stream',
            # ... other fields with defaults ...
        }
    except Exception as e:
        log.warning(f"Failed to serialize attachment row: {e}")
        return {
            'id': 0,
            'filename': 'error',
            # ... safe defaults ...
        }
```

**Location:** `app/routes/interception.py` line ~107

## Frontend Guards

### Safe Fetch Wrapper

The `safeFetch()` function wraps all network calls and returns a consistent error structure:

```javascript
async function safeFetch(url, options = {}) {
    try {
        const response = await fetch(url, options);

        if (!response.ok) {
            let errorMsg = `HTTP ${response.status}`;
            try {
                const json = await response.json();
                errorMsg = json.error || json.message || errorMsg;
            } catch (_) {
                errorMsg = await response.text() || errorMsg;
            }
            return { ok: false, data: null, error: errorMsg, status: response.status };
        }

        const data = await response.json();
        return { ok: true, data, error: null, status: response.status };

    } catch (error) {
        let errorMsg = 'Network error';
        if (error.message.includes('Failed to fetch')) {
            errorMsg = 'Cannot connect to server. Please check your connection.';
        }
        return { ok: false, data: null, error: errorMsg, status: 0 };
    }
}
```

**Location:** `static/js/app.js` line ~50

### Usage Example

```javascript
async function loadAccounts() {
    const result = await safeFetch('/api/accounts');

    if (!result.ok) {
        showPanelError('accountsPanel', result.error);
        return;
    }

    const accounts = result.data.accounts || [];
    renderAccounts(accounts);
}
```

### Safe Data Access Helpers

Global utilities prevent crashes from missing or malformed data:

```javascript
// Get nested property safely
const name = safeGet(account, 'user.name', 'Unknown');

// Render row with field defaults
const safe = safeRenderRow(account, {
    name: 'Unknown',
    email: 'N/A',
    status: 'inactive'
});

// Show error in panel instead of crashing
showPanelError('accountsPanel', 'Failed to load accounts');
```

**Location:** `templates/base.html` line ~248

## Best Practices

### When Writing API Endpoints

1. **Wrap the entire handler in try/except** for unexpected errors
2. **Catch specific exceptions** (DNS, SSL, auth) separately for better messages
3. **Always return JSON** with `success` and `error` fields
4. **Log warnings** for skipped/malformed data

```python
@accounts_bp.route('/api/something')
@login_required
def api_something():
    try:
        # Main logic
        result = do_something()
        return jsonify(success=True, data=result)
    except ValueError as e:
        return jsonify(success=False, error=f"Invalid input: {e}"), 400
    except Exception as e:
        log.exception("Unexpected error in api_something")
        return jsonify(success=False, error=str(e)), 500
```

### When Writing Frontend Code

1. **Use `safeFetch()` instead of raw `fetch()`**
2. **Always check `result.ok` before using data**
3. **Use `safeGet()` for nested properties**
4. **Show errors in UI** with `showPanelError()` or toast notifications
5. **Provide defaults** when rendering rows

```javascript
async function loadData() {
    const result = await safeFetch('/api/data');

    if (!result.ok) {
        showPanelError('dataPanel', result.error);
        return;
    }

    const items = result.data.items || [];
    items.forEach(item => {
        const safe = safeRenderRow(item, {
            name: 'Unknown',
            status: 'inactive',
            count: 0
        });
        renderRow(safe);
    });
}
```

### When Rendering Lists

1. **Never assume all rows are valid** - use safe serialization
2. **Log skipped rows** for debugging but don't fail the request
3. **Return partial results** rather than nothing

```python
safe_items = []
for raw_row in rows:
    try:
        safe_items.append(serialize_row(raw_row))
    except Exception as e:
        log.warning(f"Skipping bad row: {e}", extra={'row_id': raw_row.get('id')})
return jsonify(items=safe_items)
```

## Error Messages

### User-Facing Messages Should Be:

✅ **Clear**: "DNS lookup failed for IMAP host"
✅ **Actionable**: "Please check your connection"
✅ **Non-technical**: "Cannot connect to server"

❌ **Avoid**: "NoneType object has no attribute 'get'"
❌ **Avoid**: "Traceback (most recent call last)..."
❌ **Avoid**: Stack traces in API responses

### Log Messages Should Include:

- **Context**: endpoint, user, resource ID
- **Error type**: exception class name
- **Full details**: use `log.exception()` to capture traceback
- **Relevant data**: sanitized request params (never passwords!)

```python
log.warning(
    "Failed to serialize attachment",
    extra={
        'email_id': email_id,
        'attachment_id': att_id,
        'error': str(e)
    }
)
```

## Testing Error Handling

### Simulate Network Errors

```javascript
// In browser console
window.fetch = async () => { throw new Error('Failed to fetch'); };
// Then test your UI
```

### Test Malformed Data

```python
# In your tests
def test_handles_missing_fields():
    # Create row with missing fields
    row = {'id': 1}  # missing name, email, etc.
    result = _serialize_account_row(row)
    assert result['name'] == 'Unknown'  # Uses default
```

### Test Specific Exceptions

```python
def test_dns_error_handling(mocker):
    mocker.patch('socket.getaddrinfo', side_effect=socket.gaierror)
    response = client.post('/api/accounts/1/test')
    assert 'DNS lookup failed' in response.json['error']
```

## Summary

With these three layers of protection:

1. ✅ **Network failures** show friendly messages instead of breaking the UI
2. ✅ **Missing database fields** use defaults instead of crashing
3. ✅ **Unexpected exceptions** are logged and return JSON, not 500 HTML pages
4. ✅ **One bad row** doesn't prevent the rest from loading
5. ✅ **DNS/SSL/auth errors** show specific, actionable messages

The app is now resilient to common failure modes and degrades gracefully.
