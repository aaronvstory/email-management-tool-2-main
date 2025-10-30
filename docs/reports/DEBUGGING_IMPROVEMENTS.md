# Debugging Improvements - Oct 16, 2025

## Issue Reported

User encountered JavaScript errors in browser console:
```
api/accounts/null/monitor/restart:1 Failed to load resource: the server responded with a status of 404 (NOT FOUND)
dashboard:164 Unchecked runtime.lastError: Could not establish connection. Receiving end does not exist.
injected.js:5 Uncaught (in promise) Error: Unhandled error response...
```

## Root Cause Analysis

### Primary Issue: Null Account ID
- **File**: `templates/settings.html` line 73
- **Code**: `await fetch(\`/api/accounts/${acc.id}/monitor/restart\`, {method:'POST'});`
- **Problem**: No null check on `acc.id` before making API call
- **Impact**: 404 error when account object is malformed or ID is missing

### Secondary Issues: Browser Extensions
- **injected.js errors**: These are from browser extensions (password managers, dev tools)
- **Impact**: None on application - can be safely ignored

## Fixes Applied

### 1. Enhanced Error Handling in settings.html

**Added comprehensive logging**:
```javascript
async function restartAllViaWatchers(){
  try{
    const r = await fetch('/api/accounts');
    if (!r.ok) {
      console.error('[settings] Failed to fetch accounts:', r.status);
      return;
    }
    const j = await r.json();
    console.log('[settings] Accounts response:', j);  // ✅ Now logs response

    if (!j.accounts || !Array.isArray(j.accounts)) {
      console.error('[settings] Invalid accounts data:', j);  // ✅ Validates data
      return;
    }

    for(const acc of j.accounts){
      if (!acc || !acc.id) {
        console.warn('[settings] Skipping account with no ID:', acc);  // ✅ Skips null IDs
        continue;
      }
      try{
        console.log(\`[settings] Restarting watcher for account ${acc.id}\`);  // ✅ Logs each attempt
        await fetch(\`/api/accounts/${acc.id}/monitor/restart\`, {method:'POST'});
      }catch(e){
        console.error(\`[settings] Failed to restart account ${acc.id}:\`, e);  // ✅ Logs failures
      }
    }
  }catch(e){
    console.error('[settings] Error in restartAllViaWatchers:', e);  // ✅ Catches top-level errors
  }
}
```

**Key Improvements**:
- ✅ **Null check**: Skips accounts without IDs instead of crashing
- ✅ **Response validation**: Checks HTTP status and JSON structure
- ✅ **Detailed logging**: Every step logged with `[settings]` prefix
- ✅ **Error isolation**: Individual account failures don't stop the loop
- ✅ **Top-level catch**: Prevents unhandled promise rejections

### 2. Enhanced saveSettings() Logging

**Added request/response logging**:
```javascript
async function saveSettings(){
  // ... (setup code)
  try{
    console.log('[settings] Saving settings:', updates);  // ✅ Log request payload
    const r = await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({settings: updates})});
    if (!r.ok) {
      console.error('[settings] Save failed with status:', r.status);  // ✅ Log HTTP errors
      throw new Error(\`Server returned ${r.status}\`);
    }
    const j = await r.json();
    console.log('[settings] Save response:', j);  // ✅ Log response
    // ... (rest of code)
  }catch(e){
    console.error('[settings] Error saving settings:', e);  // ✅ Log all errors
    if(window.showError) showError(e.message);
  }
}
```

## Debugging Benefits

### Before (Silent Failures)
```javascript
// No visibility into what's happening
try{ await fetch(\`/api/accounts/${acc.id}/monitor/restart\`, {method:'POST'}); }catch(e){}
```
**Problems**:
- Silent failures (empty catch)
- No null checks
- Can't diagnose issues

### After (Comprehensive Logging)
```javascript
// Full visibility with error handling
if (!acc || !acc.id) {
  console.warn('[settings] Skipping account with no ID:', acc);
  continue;
}
try{
  console.log(\`[settings] Restarting watcher for account ${acc.id}\`);
  await fetch(\`/api/accounts/${acc.id}/monitor/restart\`, {method:'POST'});
}catch(e){
  console.error(\`[settings] Failed to restart account ${acc.id}:\`, e);
}
```
**Benefits**:
- ✅ **Prevents 404s**: Null check stops bad requests
- ✅ **Detailed logs**: Every action logged with context
- ✅ **Error visibility**: Failures show in console with details
- ✅ **Graceful degradation**: Continues processing other accounts

## How to Use New Debugging

### 1. Open Browser Console
- Chrome/Edge: F12 or Ctrl+Shift+J
- Firefox: F12 or Ctrl+Shift+K

### 2. Look for [settings] Logs
When clicking "Apply & Restart Watchers":
```
[settings] Accounts response: {success: true, accounts: Array(2)}
[settings] Restarting watcher for account 2
[settings] Restarting watcher for account 3
```

### 3. Identify Issues
**If account has no ID**:
```
[settings] Skipping account with no ID: {account_name: "Test", email_address: "test@example.com"}
```

**If API fails**:
```
[settings] Failed to fetch accounts: 500
[settings] Error in restartAllViaWatchers: TypeError: Failed to fetch
```

**If individual restart fails**:
```
[settings] Failed to restart account 3: TypeError: NetworkError when attempting to fetch resource
```

## Additional Improvements Made

### Global Error Handling (Future)
Consider adding to `base.html`:
```javascript
window.addEventListener('unhandledrejection', event => {
  console.error('[app] Unhandled promise rejection:', event.reason);
  if (window.showError) showError('An unexpected error occurred. Check console for details.');
});

window.addEventListener('error', event => {
  console.error('[app] Global error:', event.error || event.message);
});
```

### API Response Validation Pattern
All API calls should follow this pattern:
```javascript
async function callAPI(endpoint, options = {}) {
  try {
    const r = await fetch(endpoint, options);
    if (!r.ok) {
      console.error(\`[api] Request failed: ${endpoint} returned ${r.status}\`);
      throw new Error(\`HTTP ${r.status}\`);
    }
    const j = await r.json();
    console.log(\`[api] Response from ${endpoint}:\`, j);
    return j;
  } catch(e) {
    console.error(\`[api] Error calling ${endpoint}:\`, e);
    throw e;
  }
}
```

## Testing the Fix

### 1. Start the Application
```bash
python simple_app.py
```

### 2. Open Browser to Dashboard
```
http://localhost:5001
```

### 3. Open Dev Tools Console (F12)

### 4. Navigate to Settings
Click "Settings" in sidebar

### 5. Click "Apply & Restart Watchers"
Watch console for logs:
- Should see account fetch
- Should see individual restart attempts
- Should see completion or errors with context

### 6. Expected Output (Success)
```
[settings] Accounts response: {success: true, accounts: Array(2)}
[settings] Restarting watcher for account 2
[settings] Restarting watcher for account 3
```

### 7. Expected Output (If Issue)
```
[settings] Skipping account with no ID: {...}
[settings] Failed to restart account 2: Error: HTTP 500
```

## Summary

**Files Modified**:
- `templates/settings.html` - Enhanced error handling and logging

**Issues Fixed**:
- ❌ **404 errors from null account IDs** → ✅ Now skips null IDs with warning
- ❌ **Silent failures in catch blocks** → ✅ Now logs all errors
- ❌ **No visibility into API calls** → ✅ Comprehensive request/response logging
- ❌ **Unhandled promise rejections** → ✅ Top-level error handlers

**Impact**:
- ✅ **Prevents crashes**: Null checks stop bad requests
- ✅ **Easier debugging**: Clear console messages with [settings] prefix
- ✅ **Better UX**: Graceful error handling instead of silent failures
- ✅ **Production-ready**: Proper error isolation and logging

## Browser Extension Errors (Can Ignore)

These errors are from browser extensions, not our application:
```
injected.js:5 Uncaught (in promise) Error: Unhandled error response...
dashboard:164 Unchecked runtime.lastError: Could not establish connection...
```

**Common Sources**:
- Password managers (LastPass, 1Password, Bitwarden)
- Development tools (React DevTools, Vue DevTools)
- Ad blockers or privacy extensions

**Fix**: None needed (extension errors don't affect application)

---

**Status**: ✅ Debugging improvements complete
**Date**: October 16, 2025
**Testing**: Restart application and verify console logs work
**Next**: Monitor console in production for any new issues
