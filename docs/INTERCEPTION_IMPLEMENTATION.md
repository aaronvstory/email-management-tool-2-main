# Interception Implementation (FINAL – IMAP-Only)

This replaces all prior mixed (Sieve + IMAP) plans.
Sieve / ManageSieve support is fully abandoned and archived.
Interception now operates solely via rapid IMAP MOVE (or COPY+DELETE fallback).

---

## Objectives

- Intercept inbound mail using only mailbox (IMAP/SMTP) credentials.
- Remove message from INBOX as fast as possible and place it into Quarantine.
- Allow operator to review, edit (subject/body), optionally strip attachments, and release (APPEND) to INBOX.
- Preserve original MIME for audit (stored on disk via raw_path).
- Provide diff (original vs edited) and attachment removal listing.
- Supply unified stats and health endpoints.

---

## High-Level Flow

1. IMAPRapidInterceptor thread IDLEs on INBOX.
2. On UIDNEXT increase:
   - Determine new UIDs (delta).
   - MOVE (preferred) to `Quarantine` (creates folder if absent).
   - Fallback: COPY to `Quarantine` + add \\Deleted + EXPUNGE.
3. Store database row:
   - interception_status='HELD'
   - raw_path pointing to saved `.eml`
4. UI lists HELD messages (preview text snippet extracted from first text/plain or stripped HTML).
5. User edits subject/body (PUT /api/email/<id>/edit).
6. User releases (POST /api/interception/release/<id>):
   - Optional: strip_attachments=true => remove all attachments, insert placeholder notice.
   - Rebuild MIME and APPEND to INBOX (preserving original internaldate if available).
   - Mark interception_status='RELEASED'.
7. Optional discard (POST /api/interception/discard/<id>) sets interception_status='DISCARDED'.

---

## Database (Key Columns Used)

Table: email_messages
Relevant fields:
- interception_status (HELD | RELEASED | DISCARDED)
- direction (inbound/outbound) – inbound for intercepted
- subject, body_text, body_html
- raw_path (filesystem path to original)
- original_uid, original_internaldate
- edited_message_id (Message-ID of released message)
- latency_ms (capture time from detection to quarantine MOVE)

No Sieve-related columns required; any legacy sieve_* fields in email_accounts are marked deprecated but left intact for backward DB compatibility.

---

## Core Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/interception/held | GET | List HELD messages |
| /api/interception/held/<id>?include_diff=1 | GET | Detail + preview + optional unified diff |
| /api/interception/release/<id> | POST | Release edited message back to INBOX |
| /api/interception/discard/<id> | POST | Discard (mark DISCARDED) |
| /api/email/<id>/edit | POST | Persist subject/body edits (draft) |
| /api/inbox | GET | Unified inbox (legacy + released) |
| /api/unified-stats | GET | Counts: total/pending/held/released |
| /healthz | GET | Health & basic metrics |

Legacy compatibility shims:
- /api/held → 307 redirect to /api/interception/held
- /api/emails/pending → JSON deprecation guidance

---

## Release Payload (Example)

POST /api/interception/release/42
```json
{
  "edited_subject": "Updated Subject",
  "edited_body": "Final body after moderation.",
  "strip_attachments": true
}
```

Response snippet:
```json
{
  "ok": true,
  "released_to": "INBOX",
  "attachments_removed": ["invoice.pdf"],
  "edited_message_id": "<newid@example>"
}
```

---

## Inline Diff

GET /api/interception/held/42?include_diff=1 returns:
```json
"body_diff": [
  "--- original",
  "+++ edited",
  "@@ -1 +1 @@",
  "-Original line",
  "+Edited line"
]
```
Absent or unchanged => body_diff = null.

---

## Attachment Scrubbing

When strip_attachments=true:
- All parts with disposition=attachment are omitted.
- Plain-text footer appended listing removed filenames.
- JSON returns attachments_removed array.

---

## IMAP Rapid Interceptor Behavior

Pseudocode outline:
```python
connect()
ensure Quarantine folder
loop:
  IDLE  (timeout ~60s)
  check UIDNEXT
  if new range:
     search new UIDs
     MOVE or fallback COPY+DELETE+EXPUNGE
     persist row + raw_path
recover on errors with small backoff
```

Resilience:
- Reconnect on exceptions.
- Minimal sleep backoff (2s) after failure.
- Future: OPTIONAL backoff library integration.

---

## Security & Audit

- Original raw MIME never modified; edits only applied to released copy.
- Edited subject/body recorded; diff derived on demand.
- Potential future: store an immutable hash of original for tamper verification.

---

## Unified Stats (Sample)

GET /api/unified-stats:
```json
{
  "total": 1204,
  "pending": 14,
  "held": 5,
  "released": 1180
}
```

---

## Health Endpoint

/healthz returns cached metrics (5s TTL):
- db_ok
- held_count
- released_count
- working_threads (names of active interceptors)
- latency aggregates (if recorded)

---

## Editing Workflow

1. Select HELD message in dashboard.
2. Modify subject/body (autosave or explicit save via /api/email/<id>/edit).
3. Review diff (include_diff=1).
4. Release with or without attachment stripping.
5. Row changes interception_status HELD → RELEASED.

Discard path:
- POST /api/interception/discard/<id>
- Row marked DISCARDED; no append performed.

---

## Gmail Specific Note

MOVE results in label changes—some ephemeral notifications may still appear. Interception is "best effort rapid" not cryptographically guaranteed pre-delivery suppression.

---

## Known Limitations / Roadmap (Optional)

Potential enhancements:
- Percentile latency metrics endpoint (/api/latency-stats).
- Bulk release/discard actions.
- Role-based restrictions (moderator vs admin).
- Attachment type policy (allowlist vs strip all).
- HTML diff (currently only text/plain diffing).

---

## Testing Strategy

Implemented tests cover:
- Route uniqueness (no duplicates).
- Edit → release end-to-end (mocked IMAP).
- Attachment scrubbing logic (verifies removed list).
- Diff generation integrity.
- Legacy shim presence.

Recommended additional tests (if expanding):
- Large message raw fetch performance.
- HTML fallback rendering for preview.
- Latency_ms correctness with synthetic timing.

---

## Operational Runbook (Minimal)

Startup:
```bash
python simple_app.py
```

Check health:
```bash
curl http://127.0.0.1:5000/healthz
```

Stats refresh in UI every 10s.

Logs (WINDOWS PowerShell):
```powershell
Get-Content -Path .\app.log -Wait
```
(Adjust if file logging configured.)

---

## Deployment Notes

- Keep raw_path storage location on fast local disk.
- Rotate or prune raw files older than retention policy (e.g. nightly job).
- Backup SQLite or migrate to Postgres if concurrency grows.

---

## Deprecated / Removed

- ALL Sieve code paths, detection logic, scripts, SRV probing.
- Any ManageSieve activation attempts.
- Prior mixed-mode docs (this file is canonical now).

---

## Minimal Developer API Summary

| Action | Call |
|--------|------|
| List held | GET /api/interception/held |
| View one + diff | GET /api/interception/held/<id>?include_diff=1 |
| Edit draft | POST /api/email/<id>/edit (subject, body) |
| Release | POST /api/interception/release/<id> |
| Discard | POST /api/interception/discard/<id> |
| Stats | GET /api/unified-stats |
| Health | GET /healthz |

---

## Version Tag

INTERCEPTION_SPEC_VERSION=IMAP_ONLY_1.0

---

**Last Updated**: September 30, 2025
**Status**: Production Ready
**Architecture**: IMAP-Only (Sieve Deprecated)