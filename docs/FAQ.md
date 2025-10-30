# Email Management Tool - Frequently Asked Questions (FAQ)

**Last Updated**: October 18, 2025

---

## General Questions

### Q: Do I need watchers running on both Gmail and Hostinger accounts?

**A:** No, only on the **destination inbox** you want to monitor.

For example:
- If you want to intercept emails **arriving AT Hostinger**, run a watcher on Hostinger only
- If you want to intercept emails **arriving AT Gmail**, run a watcher on Gmail only
- The sender account doesn't need a watcher - only the receiver does

**Bidirectional testing** (watchers on both) is useful for comprehensive validation but isn't required for normal operation.

---

### Q: How often does the watcher check for new emails?

**A:** It depends on the detection mode:

| Mode | Check Frequency | Notes |
|------|-----------------|-------|
| **IDLE** (default) | Real-time (<1 second) | Server pushes notifications |
| **Polling** (fallback) | Every ~30 seconds | Configurable via `IMAP_POLL_INTERVAL` |

**Hybrid Strategy:**
- Starts in IDLE mode for instant detection
- Automatically falls back to polling if IDLE keeps failing
- Retries IDLE periodically when in polling mode
- Current mode shown in Watchers page UI

---

### Q: What fields are checked when matching keywords?

**A:** By default, **subject AND body** text are checked together.

You can customize this with the "Condition Field" setting:

- `SUBJECT`: Subject line only
- `BODY`: Subject + body text combined (default for keywords)
- `SENDER`: Sender email address
- `RECIPIENT`: Recipient email address
- `SENDER_DOMAIN`: Sender's domain (e.g., "@spam.com")

**Example:**
```
Rule: Pattern="invoice", Field=BODY
→ Matches "Invoice #123" in subject
→ Matches "Please find the invoice attached" in body
→ Matches either/both
```

**Matching is case-insensitive** - "Invoice", "INVOICE", and "invoice" all match.

---

### Q: Which email providers are supported?

**A:** Validated with Gmail and Hostinger IMAP. Works with standard IMAP servers. Automatically falls back to polling if IDLE isn't supported.

**Tested & Verified:**
- ✅ Gmail (imap.gmail.com:993) - Full IDLE support
- ✅ Hostinger (imap.hostinger.com:993) - Full IDLE support

**Should Work (standard IMAP):**
- Outlook/Office365
- Yahoo Mail
- ProtonMail Bridge
- Custom mail servers
- Any IMAP-compliant provider

**Requirements:**
- IMAP access enabled
- SSL/TLS support (port 993 typical)
- IDLE capability (optional - falls back to polling if unavailable)

---

## Interception Workflow

### Q: What exactly happens when an email is "intercepted"?

**A:** Here's the complete flow:

1. **Email arrives** in your INBOX
2. **Watcher detects** it (IDLE <1s or polling ~30s)
3. **Rule engine evaluates** all active rules
4. **MATCH FOUND** → Email is:
   - **COPIED** to Quarantine folder
   - **DELETED** from INBOX (marked `\Deleted` + `EXPUNGE`)
   - **Stored** in database as `status=HELD`
5. **Email now exists ONLY in Quarantine** (not visible in INBOX)
6. **Appears** in your "Held" queue in web dashboard

**Result**: The recipient never sees the email in their normal inbox until you release it.

---

### Q: What happens to the original email after I release it?

**A:** The email leaves the Held queue. Only the released copy appears in INBOX; raw audit data may be retained.

**Release Process:**
1. **Edited or original** content is reconstructed as fresh email
2. **APPENDed** to INBOX with original timestamp preserved
3. **Quarantine copy** is marked `\Deleted` and EXPUNGEd (best-effort cleanup)
4. **Only released copy** visible in inbox; raw `.eml` file retained for audit trail

**Why?** To prevent duplicates. If we just "moved back," the user would see both the original (with Message-ID ABC) and the released version (Message-ID ABC or new ID), causing confusion.

---

### Q: Can I release an email without editing it?

**A:** Yes! Use the **"Release As-Is"** option.

The original email is reconstructed exactly as received and delivered to INBOX. The user sees it as if interception never happened (except for the slight delay).

**Steps:**
1. Go to Held page
2. Click the email
3. Click **"Release"** button (don't click "Edit")
4. Original content sent to INBOX
5. Quarantine copy deleted

---

### Q: If I edit an email, does the recipient see the original version anywhere?

**A:** No, only the **edited version** appears in their INBOX.

**What happens:**
- Original stays in Quarantine until release
- When you click "Release" after editing:
  - Only the edited version goes to INBOX
  - Quarantine copy removed; raw data retained for audit
  - No trace of original in user's view

**Use Case**: Clean up phishing attempts, remove suspicious links, sanitize content before delivery.

---

### Q: How do I strip attachments from an email?

**A:** Use the "Strip Attachments" option during release:

1. Email is HELD with attachment (e.g., suspicious.pdf)
2. In Held view, click email details
3. See attachment list
4. Click **"Edit"** → Check box **"Strip Attachments"**
5. Click **"Release"**

**Result in INBOX:**
```
Original email body...

[Attachments removed: suspicious.pdf]
```

**Note**: Stripping is permanent - you can't recover the attachment after release.

---

## Technical Details

### Q: What if IDLE mode fails or times out?

**A:** The system automatically handles this with the **hybrid IDLE+polling strategy**:

**Automatic Fallback:**
1. IDLE connection fails (timeout, server disconnect, protocol error)
2. Failure counter increments
3. If IDLE **keeps failing** → force polling mode
4. Polling continues at 30-second intervals
5. Periodically retries IDLE mode
6. If IDLE succeeds → reset failure counter and return to IDLE

**Manual Recovery:**
- Go to Watchers page
- Click **"Restart"** on the affected account
- Watcher reconnects and tries IDLE again

---

### Q: How can I tell if my watcher is in IDLE or polling mode?

**A:** Check the **Watchers page** in the web dashboard.

**Status Indicators:**
- **"IDLE"** (green badge) = Real-time detection active (<1s)
- **"POLLING"** (yellow badge) = Polling mode active (~30s intervals)
- **"STOPPED"** (red badge) = Not running
- **"ACTIVE"** (green badge) = Processing messages

**Heartbeat Timestamp:**
- Updates every ~30 seconds
- Shows "X seconds ago"
- Stale heartbeat (>60s) indicates connection issue

---

### Q: Can I change the polling interval?

**A:** Yes, via environment variable.

**Method 1: Edit `.env` file**
```bash
# Default is 30 seconds
IMAP_POLL_INTERVAL=10  # Poll every 10 seconds

# Or slower
IMAP_POLL_INTERVAL=60  # Poll every 60 seconds
```

**Method 2: Restart with environment variable**
```bash
IMAP_POLL_INTERVAL=15 python simple_app.py
```

**Valid Range**: 5-300 seconds (clamped automatically)

**Recommendation**: Keep at 30s for balance of performance and server load.

---

### Q: What is "interception latency" and why does it matter?

**A:** Interception latency is the time between:
- Email arriving at server
- Email being copied to Quarantine and stored in database

**Target Latencies:**
- IDLE mode: <500ms (typical: ~200ms)
- Polling mode: <35s (30s poll interval + ~5s processing)

**Why It Matters:**
- Lower latency = email disappears from INBOX faster
- Sub-second latency means recipient never sees it flash in inbox
- Metrics shown in Dashboard and `/healthz` endpoint

**Check Your Latency:**
```bash
curl http://localhost:5001/healthz
```

Response includes:
```json
{
  "median_latency_ms": 187,
  "held_count": 12
}
```

---

### Q: Does this work with Gmail labels or Outlook folders?

**A:** Yes, but with nuances:

**Gmail:**
- "Folders" are actually **labels**
- "Quarantine" becomes a Gmail label
- Moving to Quarantine = removing INBOX label + adding Quarantine label
- Released emails get INBOX label back

**Outlook/Office365:**
- True folder structure
- Quarantine is a real subfolder
- Standard IMAP MOVE/COPY operations

**Hostinger/Custom:**
- Standard folder structure
- Quarantine as subfolder of INBOX or root

**Result**: Works identically across all providers despite different underlying implementations.

---

## Troubleshooting

### Q: Why aren't my emails being intercepted?

**Checklist:**
1. **Is the watcher running?**
   - Check Watchers page → Status should be "IDLE" or "POLLING"
   - If "STOPPED", click "Start"

2. **Is the rule active?**
   - Check Rules page → Rule should have "Active" badge
   - Click to edit → Ensure "Status" toggle is ON

3. **Does the pattern match?**
   - Check exact keyword spelling
   - Remember: matching is case-insensitive
   - Test with simple pattern first (e.g., "test")

4. **Is the rule checking the right field?**
   - If pattern is in subject, ensure Field = SUBJECT or BODY
   - If pattern is in sender, ensure Field = SENDER

5. **Is the watcher monitoring the right inbox?**
   - For Gmail→Hostinger, watcher should be on **Hostinger**
   - Common mistake: watcher on sender instead of receiver

**Quick Test:**
```
1. Create rule: Pattern="TESTWORD123", Field=BODY, Action=HOLD
2. Send email to monitored inbox with subject "TESTWORD123"
3. Wait 5 seconds
4. Check Held page - should appear
5. If not → check Watchers page for errors
```

---

### Q: I see "Circuit Open" error - what does this mean?

**A:** The watcher exceeded the error threshold and automatically disabled itself.

**Cause:**
- 5+ consecutive connection failures (default threshold)
- Usually due to: wrong password, network issues, server down

**Fix:**
1. Check account credentials (Accounts page)
2. Test connection (click "Test Connection" button)
3. Fix any authentication issues
4. Go to Watchers page → Click "Start" to re-enable

**Prevention:**
- Use App Passwords (not regular passwords) for Gmail
- Verify IMAP is enabled on the email account
- Check firewall/network allows IMAP port 993

---

### Q: Emails appear in INBOX briefly before disappearing - is this normal?

**A:** Depends on the mode:

**IDLE Mode (<1s latency):**
- Email should **NOT** flash in inbox
- Interception happens before most email clients refresh
- If you see a flash, latency might be higher than expected

**Polling Mode (~30s latency):**
- Email **MAY** appear briefly in inbox
- Client refreshes faster than polling interval
- This is expected behavior in polling mode

**Solutions:**
1. Ensure watcher is in IDLE mode (check Watchers page)
2. Restart watcher to force IDLE reconnect
3. Check latency metrics: `/healthz` endpoint

---

### Q: Can I run multiple watchers for the same account?

**A:** No, only one watcher per account is supported.

**Why?**
- Duplicate processing of same emails
- Race conditions in Quarantine folder
- Increased server load

**Attempting to start second watcher:**
```json
{
  "ok": false,
  "error": "Watcher already running for account 1",
  "code": "WATCHER_ALREADY_RUNNING"
}
```

---

## Security & Privacy

### Q: Where are my email credentials stored?

**A:** In the SQLite database (`email_manager.db`) with **Fernet symmetric encryption**.

**Security Measures:**
- Passwords encrypted before storage
- Encryption key in `key.txt` (never commit to git!)
- Key auto-generated on first run
- Database file has restricted permissions

**Best Practices:**
- Use **App Passwords** for Gmail/Outlook (not your main password)
- Keep `key.txt` and `email_manager.db` secure
- Never share or commit these files
- Rotate credentials if accidentally exposed

---

### Q: Are original emails deleted after release?

**A:** **From Quarantine: Yes.** From audit trail: No.

**What's Kept:**
- Raw email file: `data/inbound_raw/<id>.eml` (preserved for audit)
- Database metadata: subject, sender, timestamps, risk score
- Audit log: who released, when, what changes made

**What's Deleted:**
- Copy in Quarantine folder (to prevent duplicates; best-effort cleanup)
- IMAP server representation in Quarantine

**Result**: You can always review original via web dashboard (raw content viewer), but it won't exist in the email client's Quarantine folder.

---

### Q: Is this GDPR/compliance friendly?

**A:** Depends on your use case and jurisdiction.

**Privacy Considerations:**
- **Data minimization**: Only stores necessary metadata
- **Audit trail**: Complete log of all actions
- **Encryption**: Credentials encrypted at rest
- **Local storage**: No cloud/third-party access

**Compliance Checklist:**
- Document data retention policies
- Implement regular purging of old emails
- Ensure users consent to interception (if applicable)
- Review local laws on email monitoring

**Recommendation**: Consult legal counsel for your specific use case.

---

## Advanced Usage

### Q: Can I automate releases via API?

**A:** Yes! See [API Reference](API_REFERENCE.md) for complete examples.

**Example: Auto-release emails from trusted sender**
```bash
#!/bin/bash
# Get all held emails
held=$(curl -s -b cookie.txt http://localhost:5001/api/interception/held)

# Filter by sender, extract IDs, release each
echo "$held" | jq -r '.emails[] | select(.sender == "trusted@example.com") | .id' | while read id; do
   curl -s -b cookie.txt -X POST "http://localhost:5001/api/interception/release/$id"
done
```

---

### Q: Can I use this with Docker?

**A:** Yes, though the app doesn't require Docker.

**Simple Dockerfile:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["python", "simple_app.py"]
```

**Run:**
```bash
docker build -t email-tool .
docker run -p 5001:5001 -v $(pwd)/email_manager.db:/app/email_manager.db email-tool
```

---

## Still Have Questions?

**Resources:**
- [User Guide](USER_GUIDE.md) - Complete walkthrough
- [API Reference](API_REFERENCE.md) - REST API documentation
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Architecture](ARCHITECTURE.md) - System design deep dive

**Support:**
- GitHub Issues: https://github.com/aaronvstory/email-management-tool/issues
- Logs: Check `logs/app.log` for detailed error messages
- Health check: `curl http://localhost:5001/healthz`

---

**Last Updated**: October 18, 2025
