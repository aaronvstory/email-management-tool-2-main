# 📱 UI Flow Guide - How to Use Edit/Release Features

**Last Updated:** October 16, 2025
**Status:** ✅ All features working and tested

---

## Quick Start: Testing the Complete Flow

### Step 1: View Held Emails
1. Open browser: http://localhost:5001
2. Login: `admin` / `admin123`
3. Navigate to: **Email Management** (left sidebar)
4. Click tab: **"Held"** (shows count in badge)

### Step 2: Edit an Email
1. Find email in Held list
2. Click **Edit button** (pencil icon)
3. Modal opens with:
   - From: (read-only)
   - To: (read-only)
   - Subject: (editable)
   - Message Body: (editable - add your changes here)
4. Add your edit text
5. Click **"Save Changes"** or **"Save & Release"**

### Step 3: Release to Inbox
- **Option A:** Click "Save & Release" in edit modal (one-step)
- **Option B:** Click "Release" button (unlock icon) after saving

### Step 4: Verify in IMAP
1. Open your email client (Gmail, Outlook, etc.)
2. Check INBOX folder
3. Find the email - it should show your edited content
4. Original version stays in Quarantine folder

---

## UI Components Fixed

### 1. Toast Notifications ✅

**What They Look Like:**
- Appear in top-right corner
- Auto-dismiss after 4-5 seconds
- Dark background with colored borders
- Close button (X) always visible

**Types:**
- ✅ **Success** (Green) - "Email edited successfully"
- ❌ **Error** (Red) - "Failed to release: [error]"
- ⚠️ **Warning** (Orange) - "Please select an account first"
- ℹ️ **Info** (Blue) - "Processing your request..."

**Confirmation Prompts:**
- 🔄 **Release:** "Release this email to inbox?"
- 🗑️ **Discard:** "Permanently discard this email?"
- ❌ **Reject:** "Reject this email?"

### 2. Edit Modal ✅

**Location:** Opens when you click Edit button on any HELD email

**Fields:**
- **From:** Read-only (shows sender)
- **To:** Read-only (shows recipients)
- **Subject:** Editable text input
- **Message Body:** Large textarea (monospace font)

**Buttons:**
- **Cancel:** Close modal without saving
- **Save Changes:** Save edits to database
- **Save & Release:** Save and immediately release to INBOX

**Styling:**
- Dark gradient background
- Red gradient header
- White text on dark inputs
- Clear contrast ratios

---

## Step-by-Step Workflows

### Workflow 1: Quick Edit and Release

```
1. Emails Unified page → Held tab
2. Click Edit (pencil icon) on email
3. Add timestamp or notes to body
4. Click "Save & Release"
5. Toast: "Email saved and released successfully"
6. Email moves to Released tab
7. Check INBOX in email client
```

**Time:** ~30 seconds

### Workflow 2: Edit, Review, Then Release

```
1. Emails Unified page → Held tab
2. Click Edit (pencil icon) on email
3. Modify subject and body
4. Click "Save Changes"
5. Toast: "Email saved successfully"
6. Modal closes, email still in Held
7. Click Release (unlock icon)
8. Confirm: "Release this email to inbox?"
9. Toast: "Email released successfully"
10. Email moves to Released tab
```

**Time:** ~1 minute

### Workflow 3: Discard Unwanted Email

```
1. Emails Unified page → Held tab
2. Click Discard (trash icon) on email
3. Confirm: "Permanently discard this email?"
4. Toast: "Email discarded successfully"
5. Email removed from Held list
```

**Time:** ~10 seconds

---

## UI Navigation Map

```
Dashboard (/)
│
├── Email Management (/emails-unified)
│   │
│   ├── Tabs:
│   │   ├── All      (all emails)
│   │   ├── Held     ← START HERE for intercepted emails
│   │   ├── Pending  (awaiting approval)
│   │   ├── Approved (admin approved)
│   │   ├── Released (sent to INBOX)
│   │   └── Rejected (admin rejected)
│   │
│   ├── Actions (per email):
│   │   ├── Edit (pencil) → Opens Edit Modal
│   │   ├── Release (unlock) → Sends to INBOX
│   │   ├── Discard (trash) → Permanently deletes
│   │   ├── Approve (check) → Marks approved
│   │   └── Reject (X) → Marks rejected
│   │
│   └── Account Selector (top)
│       ├── All Accounts
│       ├── Gmail - NDayijecika
│       └── Hostinger - Corrinbox
│
└── Settings (/accounts)
    ├── View all accounts
    ├── Test connections
    └── Start/stop watchers
```

---

## Button Reference

### Action Buttons (on email rows)

| Icon | Button | Action | Available When |
|------|--------|--------|----------------|
| ✏️ | **Edit** | Open edit modal | HELD, PENDING |
| 🔓 | **Release** | Send to INBOX | HELD |
| 🗑️ | **Discard** | Permanently delete | HELD |
| ✅ | **Approve** | Mark as approved | PENDING |
| ❌ | **Reject** | Mark as rejected | PENDING |
| 👁️ | **View** | Open email viewer | All statuses |

### Modal Buttons

| Button | Action | Keyboard Shortcut |
|--------|--------|-------------------|
| **Cancel** | Close without saving | Esc |
| **Save Changes** | Save edits only | - |
| **Save & Release** | Save and send to INBOX | - |

### Confirmation Buttons

| Button | Action | Style |
|--------|--------|-------|
| **Cancel** | Abort action | Secondary (gray) |
| **Confirm** | Proceed | Primary (red gradient) |

---

## Keyboard Shortcuts

**Edit Modal:**
- `Esc` - Close modal
- `Tab` - Navigate between fields
- `Ctrl+Enter` - Save changes (if implemented)

**Email List:**
- Click row - View email details
- Click action button - Perform action

---

## Visual Indicators

### Status Badges

| Status | Color | Meaning |
|--------|-------|---------|
| **HELD** | 🟡 Orange | Intercepted, awaiting action |
| **PENDING** | 🔵 Blue | Awaiting approval |
| **APPROVED** | 🟢 Green | Admin approved |
| **RELEASED** | 🟢 Green | Sent to INBOX |
| **REJECTED** | 🔴 Red | Admin rejected |
| **DISCARDED** | ⚫ Gray | Permanently deleted |

### Watcher Status Chips

| Status | Color | Meaning |
|--------|-------|---------|
| **Active** | 🟢 Green | Watcher running |
| **Stopped** | 🔴 Red | Watcher not running |
| **Unknown** | ⚫ Gray | Status unavailable |

---

## Common Questions

### Q: Why can't I edit Released emails?
**A:** Once released, emails are in the recipient's INBOX. Use IMAP to edit them there, or intercept again.

### Q: Can I undo a release?
**A:** No. Once released, the email is in INBOX. You can manually move it back to Quarantine via IMAP client.

### Q: What happens to the original email?
**A:** The original stays in Quarantine folder. Only the edited version goes to INBOX.

### Q: Can I edit attachments?
**A:** Not currently. The edit modal only supports subject and body text.

### Q: Why don't I see the Edit button?
**A:** Edit is only available for HELD and PENDING emails. Check the status tab you're viewing.

---

## Troubleshooting UI Issues

### Toast Not Showing
1. Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
2. Clear browser cache
3. Check browser console for errors (F12)

### Modal Not Opening
1. Check if Bootstrap is loaded (see browser console)
2. Verify CSRF token is present in page source
3. Try different browser

### Buttons Disabled
1. Check if you're logged in as admin
2. Verify email status allows the action
3. Check watcher status for the account

### Text Not Visible
1. ✅ **FIXED** - CSS color inheritance issue resolved
2. If still an issue, report with screenshot

---

## Testing Checklist

Before reporting an issue, verify:

- [ ] Logged in as admin
- [ ] Account watcher is Active (green chip)
- [ ] Email status allows the action
- [ ] Browser cache cleared
- [ ] JavaScript enabled
- [ ] No console errors (F12)

---

## Pro Tips

### 1. Batch Operations
Select multiple emails with checkboxes → Use bulk actions at bottom

### 2. Search Filter
Use search box to filter by sender, recipient, or subject

### 3. Auto-Refresh
Enable auto-refresh checkbox for real-time updates (30-second interval)

### 4. Quick Release
Use "Save & Release" button to combine edit and release in one step

### 5. Account Switching
Use account selector to view emails for specific accounts only

---

## Support Resources

**Documentation:**
- `COMPLETE_FLOW_TEST_SUCCESS.md` - End-to-end flow verification
- `UI_FIX_AND_FLOW_TEST_SUCCESS.md` - CSS fixes and test results
- `CLAUDE.md` - Complete system documentation

**Test Script:**
- `test_edit_release_flow.py` - Automated test for edit/release flow

**Logs:**
- `app_output.log` - Flask application logs
- `email_manager.db` - SQLite database (query with DB Browser)

---

**Last Verified:** 2025-10-16 09:53:40
**All Features:** ✅ Working and tested
**Browser Tested:** Chrome/Edge (Chromium-based)
