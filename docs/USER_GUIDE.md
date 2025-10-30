# Email Management Tool - Complete User Guide

**Version**: 2.8
**Last Updated**: October 18, 2025
**Audience**: All users (beginner to advanced)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Core Concepts](#core-concepts)
3. [Quick Start - Your First Interception](#quick-start)
4. [Step-by-Step Walkthroughs](#step-by-step-walkthroughs)
5. [Common Workflows](#common-workflows)
6. [Understanding Performance](#understanding-performance)
7. [Advanced Topics](#advanced-topics)

---

## Introduction

The Email Management Tool intercepts, holds, and allows you to review emails **before they appear in your inbox**. This gives you complete control over incoming mail - you can edit, approve, or discard messages before delivery.

### What This Tool Does

- **Monitors your inbox** in real-time using IMAP
- **Intercepts matching emails** based on rules you configure (keywords, senders, etc.)
- **Moves them to Quarantine** so they don't appear in your inbox
- **Lets you review** via web dashboard
- **Releases edited or approved** emails back to inbox

### What Makes This Different

- **No MX records or DNS changes required** - uses only mailbox credentials
- **Local-first** - runs entirely on your computer (no cloud)
- **Transparent** - original emails are preserved for audit
- **Fast** - sub-second detection with IDLE mode

---

## Core Concepts

### Security Note

**Credential Storage**: Email account passwords are encrypted at rest using Fernet symmetric encryption. The encryption key (`key.txt`) is automatically generated and **must NOT be committed to version control**.

**⚠️ Important**: Never commit `key.txt`, `.env`, or any files containing credentials. All sensitive data is git-ignored by default.

### 1. Watchers (IMAP Monitors)

A **watcher** is a background process that monitors a specific email account's INBOX folder.

**Key Points:**
- You only need a watcher on the **destination inbox** (where emails arrive)
- Example: For Gmail→Hostinger flow, only Hostinger needs a watcher
- Each account can have one active watcher
- Watchers run automatically when you click "Start Monitor"

### 2. Detection Modes: IDLE vs Polling

The watcher uses two modes to detect new emails:

| Mode | Speed | How It Works |
|------|-------|--------------|
| **IDLE** (preferred) | <1 second | Server pushes notifications when new mail arrives |
| **Polling** (fallback) | ~30 seconds | App checks inbox periodically |

**Automatic Hybrid Strategy:**
- Starts in IDLE mode for real-time detection
- Falls back to polling if IDLE keeps failing
- Retries IDLE periodically when in polling mode
- You'll see current mode in Watchers page: "IDLE" (green) or "POLLING" (yellow)

### 3. Rule Matching

Rules determine which emails get intercepted. Each rule has:

- **Pattern**: What to look for (e.g., "invoice", "payment")
- **Field**: Where to look:
  - `SUBJECT`: Subject line only
  - `BODY`: Subject + body text combined
  - `SENDER`: Sender email address
  - `RECIPIENT`: Recipient email address
  - `SENDER_DOMAIN`: Sender's domain (e.g., "@company.com")
- **Operator**: How to match:
  - `CONTAINS`: Pattern appears anywhere (default)
  - `EQUALS`: Exact match
  - `STARTS_WITH`: Field starts with pattern
  - `ENDS_WITH`: Field ends with pattern
  - `REGEX`: Advanced regular expression

**Example Rules:**
```
Rule 1: Pattern="invoice", Field=BODY, Operator=CONTAINS
  → Matches any email with "invoice" in subject OR body

Rule 2: Pattern="@spam.com", Field=SENDER_DOMAIN, Operator=EQUALS
  → Matches all emails from spam.com domain
```

**Matching is case-insensitive by default** - "Invoice", "INVOICE", and "invoice" all match.

### 4. The Interception Workflow

When a new email arrives that matches a rule:

```
1. Email lands in INBOX
   ↓
2. Watcher detects it (IDLE <1s or polling ~30s)
   ↓
3. Checks against all active rules
   ↓
4. MATCH FOUND → Immediately:
   - COPIES to Quarantine folder
   - DELETES from INBOX (marked \Deleted + EXPUNGE)
   - Stores in database as "HELD"
   ↓
5. Email is NOW ONLY in Quarantine
   (NOT visible in INBOX)
   ↓
6. Appears in your "Held" queue in web dashboard
```

**Result**: User never sees the email in their normal inbox until you release it.

### 5. Release Mechanisms

You have two options when releasing a held email:

#### Option A: Release As-Is

- Original email is **reconstructed** exactly as received
- **APPENDed** to INBOX with original timestamp preserved
- Quarantine copy is **removed** (best-effort cleanup; no duplicates)
- Raw `.eml` file retained for audit trail
- User sees it as if interception never happened

#### Option B: Edit Then Release

- You modify subject, body, or strip attachments
- **Only the edited version** is APPENDed to INBOX
- Quarantine copy is **removed** (best-effort cleanup)
- Raw data retained for audit
- User sees only the edited version

**Important**: After release, the email exists in ONLY one place (INBOX). The Quarantine copy is always removed to prevent duplicates.

### 6. Bidirectional vs Unidirectional

**Common Question**: "Do I need watchers on both Gmail and Hostinger?"

**Answer**: No, only on the **destination** inbox.

**Example Scenarios:**

**Scenario 1: Monitor Hostinger Inbox**
- Goal: Intercept emails TO Hostinger (from anyone)
- Setup: Watcher on Hostinger only
- Result: Any email arriving AT Hostinger gets intercepted

**Scenario 2: Monitor Gmail Inbox**
- Goal: Intercept emails TO Gmail (from anyone)
- Setup: Watcher on Gmail only
- Result: Any email arriving AT Gmail gets intercepted

**Scenario 3: Monitor Both Directions** (bidirectional validation)
- Goal: Test interception works both ways
- Setup: Watchers on both Gmail AND Hostinger
- Result: Emails TO Gmail get held, emails TO Hostinger get held
- Use case: Comprehensive testing, not typical production use

---

## Quick Start

### Your First Email Interception in 5 Steps

**Prerequisites:**
- Email Management Tool running (`python simple_app.py`)
- Access to web dashboard (http://localhost:5000)
- Login credentials (default: admin / admin123)

---

**Step 1: Add Your Email Account**

1. Go to **Accounts** page
2. Click **"Add Account"**
3. Fill in details:
   - **Account Name**: "My Gmail" (or "My Hostinger")
   - **Email Address**: your.email@gmail.com
   - **IMAP Settings**: Auto-detected for Gmail/Hostinger
     - Gmail: imap.gmail.com:993 (SSL)
     - Hostinger: imap.hostinger.com:993 (SSL)
   - **Password**: Use App Password for Gmail (not regular password)
4. Click **Save**
5. **Test connection** - should show green checkmark

**Step 2: Start the Watcher**

1. Go to **Watchers** page
2. Find your account card
3. Click **"Start"** button
4. Status should change to "IDLE" (green) or "POLLING" (yellow)
5. Heartbeat timestamp updates every ~30 seconds

**Step 3: Create an Interception Rule**

1. Go to **Rules** page
2. Click **"Add Rule"**
3. Configure:
   - **Rule Name**: "Block Invoices"
   - **Rule Type**: KEYWORD
   - **Pattern**: `invoice`
   - **Condition Field**: BODY (matches subject + body)
   - **Action**: HOLD
   - **Priority**: 10
4. Ensure **Status** is "Active" (toggle if needed)
5. Click **Save**

**Step 4: Send a Test Email**

1. From another account (or the same account), send an email TO your monitored inbox
2. **Test #1 (Control)**: Subject: "Hello" (no keyword)
   - Check your real inbox: Email should appear normally
   - Check Held page: Should be empty
3. **Test #2 (Interception)**: Subject: "March invoice"
   - Check your real inbox: Email should **NOT** appear
   - Check Held page: Email should appear with status "HELD"

**Step 5: Release the Email**

1. Go to **Held** page (or Dashboard → Held tab)
2. Click on the held email to open details
3. Option A: Click **"Quick Release"** – delivers the held message exactly as captured
4. Option B: Click **"Edit & Release"**, adjust subject/body in the modal, then press **"Save & Release"**
5. Option C: Use **"Edit"** to save changes without releasing yet (the edits persist for later review)
6. Check your real inbox: Released email now appears
7. Check Quarantine folder: Original should be deleted

---

## Step-by-Step Walkthroughs

### Walkthrough 1: Gmail → Hostinger Interception

**Goal**: Intercept emails sent TO Hostinger, review them, edit if needed, then release.

**Participants:**
- Gmail account (sender@gmail.com)
- Hostinger account (receiver@corrinbox.com)

---

**Setup Phase:**

1. **Add Hostinger Account** (destination):
   ```
   Account Name: Hostinger Main
   Email: receiver@corrinbox.com
   IMAP Host: imap.hostinger.com
   IMAP Port: 993 (SSL)
   Password: [your hostinger password]
   ```

2. **Start Hostinger Watcher**:
   - Watchers page → Find "Hostinger Main" → Click "Start"
   - Wait for status: "IDLE" or "POLLING"

3. **Create Rule**:
   ```
   Rule Name: Suspicious Keywords
   Type: KEYWORD
   Pattern: urgent,payment,invoice,account suspended
   Field: BODY
   Operator: CONTAINS
   Action: HOLD
   Priority: 20
   Status: Active
   ```

---

**Test Phase:**

**Test 1: Control Email (should NOT be intercepted)**

1. From Gmail, send to receiver@corrinbox.com:
   ```
   Subject: Team Meeting Notes
   Body: Here are the notes from today's meeting.
   ```

2. Check Results:
   - Hostinger INBOX: ✅ Email appears normally
   - Web App Held page: ❌ Empty (not intercepted)
   - **Conclusion**: Normal delivery works

**Test 2: Keyword Match (should be intercepted)**

1. From Gmail, send to receiver@corrinbox.com:
   ```
   Subject: Urgent: Payment Required
   Body: Your account will be suspended unless you pay immediately.
   ```

2. Check Results:
   - Hostinger INBOX: ❌ Email does NOT appear
   - Web App Held page: ✅ Shows email with status "HELD"
   - Hostinger Quarantine folder: ✅ Copy stored temporarily

3. View Details:
   - Click on held email in web dashboard
   - See original subject, body, sender, timestamp
   - Risk score calculated based on matched keywords

**Test 3: Edit and Release**

1. In Held view, click **"Edit"** on the suspicious email
2. Modify content:
   ```
   Original Subject: Urgent: Payment Required
   New Subject: [REVIEWED] Payment Reminder

   Original Body: Your account will be suspended...
   New Body: This is a payment reminder. Please verify authenticity before responding.
   ```
3. Click **"Save"**
4. Click **"Release"**
5. Check Results:
   - Hostinger INBOX: ✅ Edited version appears
   - Hostinger Quarantine: ❌ Copy removed (no duplicate visible)
   - Web App status: Changed to "RELEASED"
   - Raw audit data: ✅ Retained in `.eml` file

---

### Walkthrough 2: Hostinger → Gmail (Reverse Flow)

**Goal**: Prove interception works in opposite direction.

**Setup:**
1. Add Gmail account to tool
2. Start watcher on Gmail (not Hostinger)
3. Use same "Suspicious Keywords" rule

**Test:**
1. From Hostinger, send email with keyword to Gmail
2. Gmail INBOX: Email should NOT appear
3. Web App Held: Email appears
4. Release as-is or edit, then verify in Gmail INBOX

---

### Walkthrough 3: Attachment Handling

**Goal**: Strip attachments from a held email before release.

**Test Email:**
```
From: sender@example.com
To: monitored@account.com
Subject: Invoice with PDF
Body: Please review the attached invoice.
Attachments: invoice.pdf (250 KB)
```

**Process:**
1. Email gets held (matches "invoice" keyword)
2. In Held view, click email details
3. See attachment list: "invoice.pdf (250 KB)"
4. Click **"Edit"**
5. Check box: **"Strip Attachments"**
6. Click **"Release"**

**Result in INBOX:**
```
Subject: Invoice with PDF
Body: Please review the attached invoice.

[Attachments removed: invoice.pdf]
```

**Use Case**: Remove potentially dangerous files before delivery.

---

## Common Workflows

### Daily Email Review Process

**Morning Routine:**

1. **Check Held Queue**:
   - Dashboard → Held tab
   - See count of intercepted emails overnight

2. **Bulk Review**:
   - Sort by risk score (highest first)
   - Quickly scan subjects and senders

3. **Triage**:
   - **Legitimate emails**: Click "Release" (batch operation if supported)
   - **Spam**: Click "Discard"
   - **Suspicious**: Click "Edit", clean content, then "Release"

4. **Check Metrics**:
   - Dashboard shows interception stats
   - Review latency (should be <1s for IDLE)

### Managing Multiple Accounts

**Scenario**: You monitor 5 different inboxes (Gmail, Outlook, 3x Hostinger).

**Setup:**

1. **Add all 5 accounts** in Accounts page
2. **Start watchers** for each account
3. **Use shared rules** (rules apply to all accounts)
4. **Monitor in Watchers page**:
   - See all 5 accounts at a glance
   - Check heartbeats for health
   - Restart individual watchers if needed

**Held Queue Filtering:**
- Use account filter dropdown to see held emails per account
- Or view unified queue (all accounts combined)

### Rule Management Best Practices

**Organizing Rules:**

1. **Use Priority Levels**:
   ```
   Priority 100: Critical security (e.g., "password reset")
   Priority  50: Moderate risk (e.g., "invoice", "payment")
   Priority  10: Low risk monitoring (e.g., "urgent")
   ```

2. **Test Rules Before Activating**:
   - Create rule as "Inactive"
   - Send test emails
   - Review matches in logs
   - Toggle to "Active" when confident

3. **Regular Cleanup**:
   - Review unused rules quarterly
   - Delete outdated patterns
   - Update based on new spam trends

---

## Understanding Performance

### Detection Speed

| Mode | Typical Detection Time | Notes |
|------|------------------------|-------|
| IDLE (Gmail) | <1 second | Push notification from server |
| IDLE (Hostinger) | <2 seconds | Varies by provider |
| Polling | ~30 seconds | Configurable via `IMAP_POLL_INTERVAL` |

### Latency Metrics

The dashboard shows **interception latency** - time from email arrival to database storage.

**Target Latencies:**
- IDLE mode: <500ms
- Polling mode: <35s (30s poll + 5s processing)

**Measuring Latency:**
```bash
# Check recent interceptions
curl http://localhost:5000/healthz
```

Response includes:
```json
{
  "median_latency_ms": 187,
  "held_count": 12,
  "released_24h": 45
}
```

### Scaling Considerations

**Single Account:**
- Handles thousands of emails per day
- Minimal CPU/memory impact
- Latency stays consistent

**Multiple Accounts (5+):**
- Each watcher uses ~10MB RAM
- Slight CPU increase during IDLE restarts
- No noticeable slowdown

**Large Mailboxes:**
- Initial startup may scan last 100 messages
- IDLE maintains position automatically
- No performance degradation over time

---

## Advanced Topics

### Gmail-Specific Behavior

#### Why Gmail Release Behavior Differs

Gmail uses a **label-based IMAP system** instead of traditional folders:
- **Traditional IMAP** (Hostinger, etc.): Messages physically exist in one folder at a time
- **Gmail IMAP**: All messages exist in `[Gmail]/All Mail` with labels like `\Inbox`, `Quarantine`, etc.

**What This Means for You:**
When releasing edited emails on Gmail accounts, the system performs extra cleanup to ensure only the edited version appears in your INBOX. We **physically move** the original from `[Gmail]/All Mail` to Trash using the IMAP MOVE command (or COPY+EXPUNGE fallback). This prevents Gmail from ever reapplying the Inbox label.

#### The Release Process (Gmail)

1. **Intercept**: Original email moved to Quarantine (removes `\Inbox` label)
2. **Edit**: You modify subject/body in the dashboard
3. **Release**: System performs defense-in-depth cleanup:
   - Appends edited email to INBOX (with new Message-ID)
   - Removes original from Quarantine folder
   - **Moves original from `[Gmail]/All Mail` to `[Gmail]/Trash`** using RFC 6851 MOVE or traditional COPY+FLAGS+EXPUNGE
   - Physically expunges the message from All Mail

**Result**: Only the edited email appears in your Gmail INBOX. The original is physically removed from All Mail and placed in Trash.

**Technical Details:**
- Uses `UID MOVE` command if server supports it (RFC 6851)
- Falls back to `UID COPY` → `+FLAGS \Deleted` → `EXPUNGE` for compatibility
- Automatically discovers mailboxes using IMAP LIST special-use flags (`\All`, `\Trash`)
- Supports both `[Gmail]/All Mail` and `[Google Mail]/All Mail` (international Gmail)

#### Verifying Gmail Release Success

Check application logs for this line:
```
[Gmail] Original moved to Trash and removed from All Mail
  (email_id=X, uids=['123'], mbox='[Gmail]/All Mail', trash='[Gmail]/Trash', used_move=True, used_uidplus=True)
```

If you don't see this log:
- Verify IMAP is enabled in Gmail Settings → Forwarding and POP/IMAP
- Ensure `[Gmail]/All Mail` folder is accessible over IMAP
- Check that `GMAIL_ALL_MAIL_PURGE` env var is not set to `0`

#### Emergency Rollback (Gmail Purge)

If Gmail release behaves unexpectedly, you can temporarily disable All Mail purge:

```bash
# In .env file or environment
GMAIL_ALL_MAIL_PURGE=0
```

**Note**: This keeps Droid's INBOX/Quarantine cleanup active but skips the Gmail-specific All Mail purge. Use this only if troubleshooting Gmail issues.

---

### Environment Variables for Tuning

Configure via `.env` file:

```bash
# Force polling mode (disable IDLE)
IMAP_DISABLE_IDLE=1

# Polling interval in seconds (default: 30)
IMAP_POLL_INTERVAL=10

# Circuit breaker threshold (failures before disabling account)
IMAP_CIRCUIT_THRESHOLD=5

# Force COPY+PURGE instead of UID MOVE
IMAP_FORCE_COPY_PURGE=1
```

### Quarantine Folder Management

**Default Behavior:**
- Watcher creates "Quarantine" folder automatically
- Uses IMAP MOVE if supported (fast, atomic)
- Falls back to COPY + DELETE + EXPUNGE (safe, universal)

**Custom Folder Names:**
- Configure per-account in database: `quarantine_folder` column
- Example: Use "Held" instead of "Quarantine"

**Cleanup:**
- Released emails: Quarantine copy removed (best-effort), raw audit data retained
- Discarded emails: Quarantine copy may remain depending on configuration
- Manual cleanup: Delete old Quarantine messages via email client if needed

### IDLE Connection Management

**How It Works:**
- Opens persistent connection to INBOX
- Server sends EXISTS/RECENT notifications on new mail
- Connection times out after ~29 minutes (Gmail), ~30 minutes (Hostinger)

**Automatic Handling:**
- Health check every 14 minutes (NOOP command)
- Graceful IDLE exit before timeout
- Reconnect and resume monitoring
- Fallback to polling if IDLE fails 3 times

**Manual Intervention:**
- Restart watcher: Watchers page → Restart button
- Check logs: `logs/app.log` for IDLE/polling transitions

### Security and Privacy

**Data Storage:**
- Original emails saved in `data/inbound_raw/<id>.eml`
- Database stores metadata only (subject, sender, timestamps)
- Passwords encrypted with Fernet symmetric encryption
- Encryption key in `key.txt` (NEVER commit to git)

**Access Control:**
- Login required for all web pages (Flask-Login)
- Rate limiting on authentication endpoints
- CSRF protection on all POST requests

**Audit Trail:**
- All actions logged in `audit_log` table
- Tracks: who released/discarded, when, which email
- Useful for compliance and investigations

---

## Next Steps

Now that you understand the complete workflow:

1. **Set up your first account** following the Quick Start
2. **Review the [API Reference](API_REFERENCE.md)** for automation
3. **Check [Troubleshooting](TROUBLESHOOTING.md)** if issues arise
4. **Read [FAQ](FAQ.md)** for common questions

**Support:**
- GitHub Issues: https://github.com/aaronvstory/email-management-tool/issues
- Documentation: All docs in `docs/` folder

---

**Last Updated**: October 18, 2025
**Version**: 2.8
