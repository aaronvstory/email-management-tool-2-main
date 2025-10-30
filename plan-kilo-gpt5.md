# E2E Attachments Plan — Email Interception System (Incremental, Backward-Compatible)

This extends the earlier release-concurrency and editor-parity plan with an end-to-end attachments capability, implemented consistently across quick view, modal editor, and full-page editor.

Primary integration points:
- [templates/emails_unified.html](templates/emails_unified.html)
- [templates/email_viewer.html](templates/email_viewer.html)
- [templates/email_editor_modal.html](templates/email_editor_modal.html)
- [static/js/app.js](static/js/app.js)
- [python.api_interception_release()](app/routes/interception.py:453)
- [config/config.py](config/config.py)

## 1) Storage layout and manifest (single source of truth)

On disk
- Originals: attachments/<email_id>/ — immutable, extracted from raw on first access
- Staged edits/additions: attachments_staged/<email_id>/ — user modifications pending release

Database
- Normalized table: email_attachments stores all attachment metadata (original and staged)
- Manifest JSON column on email_messages records the pending edit plan with a version for optimistic concurrency

Manifest shape (stored in email_messages.attachments_manifest)

```
{
  "version": 3,
  "last_updated": "2025-10-21T19:00:00Z",
  "items": [
    {
      "aid": 1012,
      "source": "original",
      "filename": "invoice.pdf",
      "mime_type": "application/pdf",
      "size": 234567,
      "sha256": "...",
      "disposition": "attachment",
      "content_id": null,
      "action": "keep",
      "staged_ref": 2055,
      "notes": "user replaced with redacted"
    }
  ]
}
```

Guidelines:
- email_attachments has is_original and is_staged flags
- storage_path always points under attachments/ or attachments_staged/
- content_id holds CID for inline parts (without brackets)
- Keep originals; stage changes in staged dir; manifest determines release decisions

## 2) Schema migration (SQLite)

Execute via a migration harness or startup guard in [python.get_db()](app/utils/db.py:1).

SQL

```
CREATE TABLE IF NOT EXISTS email_attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email_id INTEGER NOT NULL,
  filename TEXT NOT NULL,
  mime_type TEXT,
  size INTEGER,
  sha256 TEXT,
  disposition TEXT,
  content_id TEXT,
  is_original INTEGER NOT NULL DEFAULT 0,
  is_staged INTEGER NOT NULL DEFAULT 0,
  storage_path TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(email_id, filename, is_original, is_staged)
);

ALTER TABLE email_messages ADD COLUMN attachments_manifest TEXT;
ALTER TABLE email_messages ADD COLUMN version INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS email_release_locks (
  email_id INTEGER PRIMARY KEY,
  acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  key TEXT PRIMARY KEY,
  email_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  response_json TEXT
);
```

Optional model helpers can be added in [templates or python.EmailAttachment](app/models/email.py:1) for typed reads/writes; raw SQL is also acceptable.

## 3) Backend API surface in [python.interception.py](app/routes/interception.py:1)

List attachments
- GET /api/email/<int:email_id>/attachments
- Response:

```
{
  "ok": true,
  "email_id": 1621,
  "version": 3,
  "attachments": [
    {"id":1012,"filename":"invoice.pdf","mime_type":"application/pdf","size":234567,"sha256":"...","disposition":"attachment","content_id":null,"is_original":true,"is_staged":false},
    {"id":2055,"filename":"invoice-redacted.pdf","mime_type":"application/pdf","size":210000,"sha256":"...","disposition":"attachment","content_id":null,"is_original":false,"is_staged":true}
  ],
  "manifest": { ... }
}
```

Download attachment
- GET /api/attachment/<int:attachment_id>/download (streams path from originals or staged)

Upload add/replace (multipart/form-data)
- POST /api/email/<int:email_id>/attachments/upload
- Form fields: file, optional replace_aid
- Response: `{ "ok": true, "staged_id": 2055, "attachment": {...}, "version": 4 }`

Mark actions (manifest-only)
- POST /api/email/<int:email_id>/attachments/mark
- Remove: `{ "aid": 1012, "action": "remove", "version": 4 }`
- Replace: `{ "aid": 1012, "action": "replace", "staged_ref": 2055, "version": 4 }`
- Add: `{ "aid": null, "action": "add", "staged_ref": 2060, "version": 4 }`

Delete staged artifact
- DELETE /api/email/<int:email_id>/attachments/staged/<int:staged_id>

Finalize release (extend) [python.api_interception_release()](app/routes/interception.py:453)
- POST /api/interception/release/<int:email_id> (uses manifest + subject/body edits)
- Optional header: X-Idempotency-Key

Key helpers (module-local in [python.interception.py](app/routes/interception.py:1)):
- _ensure_attachments_extracted(conn, row)
- _update_manifest(conn, email_id, mutator)
- _sanitize_and_store(file, dest_dir)
- _rebuild_mime_with_manifest(row, manifest)

Representative Python skeletons

```
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser
import hashlib, os, json, tempfile, mmap

MAX_ATTACHMENTS = int(os.getenv('ATTACHMENTS_MAX_COUNT', '25'))
MAX_ATTACHMENT_SIZE = int(os.getenv('ATTACHMENT_MAX_BYTES', str(25*1024*1024)))
ALLOWED_MIME = set((os.getenv('ATTACHMENT_ALLOWED_MIME', 'application/pdf,image/png,image/jpeg,text/plain')).split(','))

def _safe_filename(name: str) -> str: ...
def _norm_cid(cid): ...

def _ensure_attachments_extracted(conn, row):
    # Parse raw, write originals to attachments/<email_id>/, insert rows
    ...

def _rebuild_mime_with_manifest(row, manifest_dict):
    from email.utils import make_msgid
    new = EmailMessage()
    msg = _load_original_msg(row)
    for k,v in msg.items():
        if k.lower() in ('content-type','content-transfer-encoding','mime-version'): continue
        new[k] = v
    plain_body, html_body = _select_bodies(msg, row)
    new.set_content(plain_body or '')
    if html_body: new.add_alternative(html_body, subtype='html')
    for item in manifest_dict.get('items', []):
        if item.get('action') == 'remove': continue
        att = _resolve_attachment(row['id'], item)
        with open(att['storage_path'], 'rb') as f: data = f.read()
        maintype, subtype = (att['mime_type'] or 'application/octet-stream').split('/', 1)
        new.add_attachment(data, maintype=maintype, subtype=subtype, filename=_rfc2231_filename(att['filename']))
        if att['disposition']=='inline' and att['content_id']:
            part = new.get_payload()[-1]
            part.replace_header('Content-Disposition', f'inline; filename="{_rfc2231_filename(att["filename"])}"')
            part['Content-ID'] = f'<{att["content_id"]}>'
    new['Message-ID'] = make_msgid()
    return new
```

Streaming note: build MIME into a temporary file and mmap for APPEND to bound memory usage.

Multipart and headers:
- Preserve From/To/Cc/Bcc/Date/References/In-Reply-To
- Regenerate Message-ID on edit
- Prefer multipart/mixed with text/plain + text/html alternatives; add attachments; for CIDs, consider multipart/related
- Encode filenames via RFC 2231/5987
- Treat winmail.dat as opaque in this phase

## 4) UI updates (shared across quick view, modal, full)

Quick view [templates/emails_unified.html](templates/emails_unified.html)
- In Edit Email Modal body add an attachments panel with list, download, remove, replace, and DnD upload

Full-page [templates/email_viewer.html](templates/email_viewer.html)
- Replace simple list with enhanced panel; same IDs where practical

Modal [templates/email_editor_modal.html](templates/email_editor_modal.html)
- Add identical panel after body editors

JS module in [javascript.MailAttach](static/js/app.js:1)
- load(emailId), render(emailId)
- download(aid)
- onDragOver/onDrop/onFileSelect → uploadFiles(uploadOne)
- uploadOne(emailId, file, replaceAid?)
- replacePrompt(aid, emailId)
- markRemove(aid, emailId)
- Pre-release confirm: summarize add/remove/replace and warn on critical removals

## 5) Guardrails and security

Limits in [python.config](config/config.py:1)
- ATTACHMENTS_MAX_COUNT, ATTACHMENT_MAX_BYTES, ATTACHMENT_ALLOWED_MIME, ATTACHMENT_CLAMAV_ENABLED

Validation
- python-magic sniffing; sanitize filenames; compute SHA-256; optional dedupe
- Encrypted PDFs rejected unless allowed; flag in UI
- Antivirus scanning if enabled

Audit and metrics
- Log via [python.audit.log_action()](app/services/audit.py:1)
- Metrics in [python.metrics](app/utils/metrics.py:1): uploaded bytes, rejects, rebuild durations, failures

## 6) Concurrency, consistency, failure modes

- Optimistic concurrency: email_messages.version required on manifest mutations; 409 on mismatch
- Release lock: reuse [python.email_release_locks](app/routes/interception.py:453) workflow
- Success: clear manifest, delete staged rows/files, keep originals
- Discard: clear manifest, delete staged, keep originals
- Janitor job: purge orphans in attachments_staged/, enforce quotas (optional)

## 7) PDF operations scope

- Default replacement via user-uploaded PDFs
- Optional: merge/extract/watermark via PyPDF2 or qpdf under strict flags and limits

## 8) Phased implementation (incremental, feature-flagged)

Phase 1 — Foundation (schema, extraction, list+download)
- Backend: migration, _ensure_attachments_extracted, list, download
- Frontend: render lists; bind download
- Flags: ATTACHMENTS_UI_ENABLED=true (staging), EDIT=false, RELEASE=false
- Acceptance: intercepted email shows attachments in both views; downloads work
- Tests: unit MIME extraction; integration list+download
- Rollout: staging → prod (read-only)
- Rollback: flag off

Phase 2 — Upload add/replace (staged) and manifest updates
- Backend: upload, mark add/replace, delete staged
- Frontend: DnD/picker, progress, replace flow, toasts
- Flags: ATTACHMENTS_EDIT_ENABLED=true (staging)
- Acceptance: add, replace; staged badge visible; manifest version increments
- Tests: sanitizer, sniffing, SHA, AV stub; integration upload/replace
- Rollout/rollback: staging on/off

Phase 3 — Remove/keep and pre-release summary
- Backend: mark remove/keep with version checks
- Frontend: remove/undo UI; confirmation summary
- Acceptance: accurate summary; warnings for critical removals
- Tests: manifest transitions; UI assertions

Phase 4 — Release-time MIME rebuild and cleanup
- Backend: extend [python.api_interception_release()](app/routes/interception.py:453) to rebuild via manifest; temp-file+mmap APPEND; idempotency
- Frontend: Save & Release uses guarded flow; success closes modal and refreshes
- Acceptance: remove/replace/add → released MIME correct; staged cleaned; originals preserved
- Tests: unit rebuild (mixed/related, inline CIDs, filenames), property-based, integration via IMAP, smoke on memory
- Flags: ATTACHMENTS_RELEASE_ENABLED=true (staging/canary)
- Rollback: disable release flag; staged persists

Phase 5 — Janitor/quotas and observability
- Backend: periodic purge of orphans and storage monitoring; metrics/alerts
- Tests: janitor selection and FS integration

## 9) Acceptance criteria (E2E)

- Held email with two attachments can be listed, one removed, one replaced, one added, and released with correct MIME and filenames; staged artifacts are cleaned; audit and metrics recorded

## 10) Test plan (comprehensive)

- Unit (Python): parse/rewrite MIME, header encoding (RFC 2231), inline CIDs, nested multiparts, sanitizer, manifest transitions
- Property-based: randomized attachment sets round-trip invariants
- Integration: intercept → edits → release → IMAP fetch asserts; 409 on version conflict; release lock race (one 200, one 409)
- Frontend: uploads, replacements, removals, progress, errors in both modal and full views
- Smoke: large attachments use temp-file build, bounded memory

## 11) Observability and monitoring

- Structured logs for upload/replace/remove/finalize with email_id, attachment_id, filename, size, sha256
- Metrics via [python.metrics](app/utils/metrics.py:1)
- Audit entries via [python.audit](app/services/audit.py:1); optional UI surface
- Alerts for low disk in attachments dirs and spikes in rebuild failures/rejections

## 12) Rollout and flags

Flags in [python.config](config/config.py:1):
- ATTACHMENTS_UI_ENABLED
- ATTACHMENTS_EDIT_ENABLED
- ATTACHMENTS_RELEASE_ENABLED
- ATTACHMENT_MAX_BYTES
- ATTACHMENTS_MAX_COUNT
- ATTACHMENT_ALLOWED_MIME
- ATTACHMENT_CLAMAV_ENABLED

Stages
- P1 read-only → P2 edits → P3 remove/keep → P4 release → P5 janitor/quotas
- Canary accounts before broad enablement

Estimates and dependencies
- P1: 1–2d, P2: 2–3d, P3: 1d, P4: 3–5d, P5: 1d; tests/obs: 2–3d
- Dependencies: python-magic; optional ClamAV; disk space alerts; IMAP stability

## 13) Deliverables (by file)

Backend
- Endpoints and helpers in [python.interception.py](app/routes/interception.py:1)
- MIME rebuild integrated into [python.api_interception_release()](app/routes/interception.py:453)
- Migration SQL; janitor (e.g., [python.imap_startup worker](app/workers/imap_startup.py:1))

Frontend
- Template updates in [templates/emails_unified.html](templates/emails_unified.html), [templates/email_viewer.html](templates/email_viewer.html), [templates/email_editor_modal.html](templates/email_editor_modal.html)
- JS additions in [javascript.app.js](static/js/app.js:1) for MailAttach

Docs
- Update [docs/INTERCEPTION_IMPLEMENTATION.md](docs/INTERCEPTION_IMPLEMENTATION.md) and [docs/USER_GUIDE.md](docs/USER_GUIDE.md)

Metrics and audit
- Counters/timers in [python.metrics](app/utils/metrics.py:1); audit entries via [python.audit](app/services/audit.py:1)

## 14) Sequence overview (Mermaid)

```mermaid
sequenceDiagram
  participant U as UI
  participant S as Server
  participant DB as Database
  participant I as IMAP

  U->>S: GET /api/email/{id}/attachments
  S->>DB: Ensure originals extracted
  S-->>U: attachments + manifest + version
  U->>S: POST upload (staged) or mark replace/remove (with version)
  S->>DB: Update staged rows + manifest (optimistic concurrency)
  U->>S: POST /api/interception/release/{id} (idempotency key)
  S->>DB: Acquire release lock
  S->>S: Rebuild MIME from manifest + edits (temp file)
  S->>I: APPEND to INBOX (stream/mmapped)
  S->>DB: Update email status; clear manifest; delete staged
  S-->>U: 200 ok; UI refreshes
```

This plan is cohesive with the existing editing and releasing flow, aligns with current project conventions, and is immediately actionable for Phase 1 implementation.

---

# Autonomous Implementation Runbook (for Claude Code/Codex/Droid)

Purpose
- Enable an autonomous coding agent to implement the E2E attachments plan end-to-end, run tests, and proceed uninterrupted for long stretches.
- Provide explicit, deterministic steps, commands, guardrails, gates, and rollback points per phase.
- Minimize ambiguity by naming exact files, functions, DOM IDs, endpoints, and success criteria.

Execution Mode
- Create a feature branch, implement one phase at a time, run tests, gate, commit, then proceed.
- Persist progress to plan-state.json at repo root after each gate passes (simple JSON with {"phase": "P1.3", "timestamp": "..."}).
- Use feature flags to dark-ship safely and avoid breaking current flows.

Core Files (anchors used throughout)
- Backend: [python.interception.py](app/routes/interception.py:1), [python.get_db()](app/utils/db.py:1), [python.audit.log_action()](app/services/audit.py:1), [python.metrics](app/utils/metrics.py:1)
- Frontend: [templates/emails_unified.html](templates/emails_unified.html), [templates/email_viewer.html](templates/email_viewer.html), [templates/email_editor_modal.html](templates/email_editor_modal.html), [javascript.app.js](static/js/app.js:1)
- Config: [python.config](config/config.py:1)
- Plan file: [plan-kilo-gpt5.md](plan-kilo-gpt5.md)

Environment Preparation (once)
1) Python env and dependencies
- Windows PowerShell:
  - python -m venv .venv
  - .\.venv\Scripts\Activate.ps1
  - pip install -U pip wheel
  - pip install -r requirements.txt
  - pip install python-magic-bin  # Windows-friendly magic; on Linux/Mac use python-magic
  - Optional AV: ensure ClamAV daemon reachable if ATTACHMENT_CLAMAV_ENABLED=true
2) Repo hygiene
- git checkout -b feature/attachments-e2e
- Create plan-state.json with {"phase": "INIT", "timestamp": "<now>"}

Feature Flags (initial defaults)
Add or verify in [python.config](config/config.py:1) or environment:
- ATTACHMENTS_UI_ENABLED=false
- ATTACHMENTS_EDIT_ENABLED=false
- ATTACHMENTS_RELEASE_ENABLED=false
- ATTACHMENT_MAX_BYTES=26214400  # 25MB
- ATTACHMENTS_MAX_COUNT=25
- ATTACHMENT_ALLOWED_MIME=application/pdf,image/png,image/jpeg,text/plain
- ATTACHMENT_CLAMAV_ENABLED=false

If config keys aren’t present, add them with sane defaults and read via os.getenv in [python.interception.py](app/routes/interception.py:1).

Directory Baseline
- Ensure directories exist (created lazily by code later, but safe to create now):
  - attachments/
  - attachments_staged/

Global Commands Reference
- Run server: python start.py (or flask run if applicable)
- Run tests: pytest -q
- Lint fast (optional): python -m pyflakes app || true
- State write: echo {"phase":"P?.?","timestamp":"..."} > plan-state.json

Gating and Rollback
- Each phase has Gate Criteria. If a gate fails, perform phase rollback described in that phase (usually toggling flags, reverting changes, or skipping to a safe branch point).
- Always commit after each successful gate with a descriptive message.

-------------------------------------------------------------------------------

PHASE 1 — Foundation: Schema, Extraction, Read-only List + Download

Objective
- Introduce schema, safely extract original attachments to disk, list them via API, and allow download. No edits.

Backend Tasks
1) Add schema migration
- Implement a tiny bootstrap migration applicator in [python.get_db()](app/utils/db.py:1) or a new module app/migrations_runner.py that runs the SQL from the plan.
- Migration SQL is defined earlier in this plan file; execute with a single connection before first request (e.g., in app/__init__.py startup).
2) Implement extraction helper
- Add [python._ensure_attachments_extracted()](app/routes/interception.py:1) to:
  - Parse raw (raw_path or raw_content)
  - Walk MIME tree, persist attachments to attachments/&lt;email_id&gt;/
  - Insert rows into email_attachments (is_original=1)
3) List API
- Add GET /api/email/&lt;email_id&gt;/attachments to [python.interception.py](app/routes/interception.py:1)
  - Enforce ATTACHMENTS_UI_ENABLED or return {"ok": false, "error": "disabled"} 403
  - Ensure originals extracted, return attachments array, version, manifest JSON (empty if none)
4) Download API
- GET /api/attachment/&lt;attachment_id&gt;/download to stream the FS file with proper headers

Frontend Tasks
1) Full view panel
- In [templates/email_viewer.html](templates/email_viewer.html), replace attachments section with:
  - Container: &lt;div id="attachmentsList" class="attachment-list"&gt;&lt;/div&gt;
  - Fetch: On DOMContentLoaded or when showing the panel, call MailAttach.load({{ email.id }})
  - Render: read-only; show name, type, size, Download button
2) Modal panel (read-only for now)
- In [templates/emails_unified.html](templates/emails_unified.html) Edit Email Modal add:
  - &lt;div id="modalAttachmentsList"&gt;&lt;/div&gt;
  - When editEmail(id) loads modal, call MailAttach.load(id); render read-only
3) JS module (skeleton)
- In [javascript.app.js](static/js/app.js:1), add a minimal window.MailAttach with:
  - load(emailId): GET /api/email/{id}/attachments -> cache -> render
  - render(emailId): populate attachmentsList or modalAttachmentsList
  - download(aid): set window.location to /api/attachment/{aid}/download

DB/FS Changes
- Create tables via migration
- Create attachments/&lt;email_id&gt;/ on-demand

Config/Guardrails
- Only expose list/download when ATTACHMENTS_UI_ENABLED=true
- Enforce auth (existing login_required usage)

Gate Criteria
- With ATTACHMENTS_UI_ENABLED=true:
  - Held email with 2+ attachments lists in both views
  - Download works for each attachment
  - No JavaScript console errors

Test Plan
- Unit (add new tests):
  - MIME extraction -> files and DB rows inserted; filenames sanitized; CID normalized
- Integration:
  - Intercept → GET list → validate array contents → GET download for each
- Run: pytest -q

Commands (suggested sequence)
- Set ATTACHMENTS_UI_ENABLED=true (staging)
- python start.py (validate server starts)
- curl http://127.0.0.1:5001/api/email/{id}/attachments (logged-in session or via browser)
- pytest -q
- git add -A && git commit -m "P1: schema, extraction, list+download endpoints and read-only UI"
- Write plan-state.json with phase P1.DONE

Rollback
- Set ATTACHMENTS_UI_ENABLED=false to dark-ship; no removals needed

-------------------------------------------------------------------------------

PHASE 2 — Upload (Add/Replace) Staging and Manifest Updates

Objective
- Allow uploads into attachments_staged/, stage replaces/adds, and mutate manifest with optimistic version.

Backend Tasks
1) Upload Endpoint
- POST /api/email/&lt;email_id&gt;/attachments/upload in [python.interception.py](app/routes/interception.py:1):
  - Multipart form: file, optional replace_aid
  - Validate: count limit (ATTACHMENTS_MAX_COUNT), size limit (ATTACHMENT_MAX_BYTES), allowed MIME (sniff via python-magic)
  - Optional AV (ATTACHMENT_CLAMAV_ENABLED): reject infected
  - Store under attachments_staged/&lt;email_id&gt;/
  - Insert email_attachments row (is_staged=1)
  - Update manifest (add or replace) and bump email_messages.version
2) Mark Endpoint
- POST /api/email/&lt;email_id&gt;/attachments/mark:
  - Actions: add, replace, keep (no-op), remove
  - Require version in request; if mismatch -> 409 return latest manifest + version
3) Delete Staged Endpoint
- DELETE /api/email/&lt;email_id&gt;/attachments/staged/&lt;staged_id&gt;:
  - Remove FS file and row; update manifest if referenced

Frontend Tasks
1) Upload UI
- In both [templates/email_viewer.html](templates/email_viewer.html) and [templates/emails_unified.html](templates/emails_unified.html):
  - Add DnD area and file picker
  - On drop/select -> MailAttach.uploadOne(emailId, file, replaceAid?) -> reload list on success
2) Replace action
- Render “Replace” button per attachment: triggers file picker -> calls uploadOne with replaceAid=aid
3) Remove action
- Render “Remove” button -> POST mark remove with current version -> reload
4) JS (window.MailAttach) in [javascript.app.js](static/js/app.js:1):
  - uploadFiles/uploadOne with FormData, progress (optional)
  - replacePrompt(aid, emailId)
  - markRemove(aid, emailId) with version
  - load/render reuse from P1

DB/FS
- Create attachments_staged/&lt;email_id&gt;/ as needed

Config/Guardrails
- ATTACHMENTS_EDIT_ENABLED=true to enable UPLOAD/MARK/DELETE
- Enforce limits and sanitize filenames
- Compute SHA-256 and store

Gate Criteria
- Add new PDF (shows as staged)
- Replace existing (shows staged badge)
- Remove marks reflected in manifest; version increments
- Version conflict returns 409 and resolves by reload

Test Plan
- Unit: sanitizer, sniffing, SHA, AV stubs, manifest transitions (add/replace/remove)
- Integration: upload add → list shows staged; replace; mark remove; delete staged
- Run: pytest -q

Commands
- Set ATTACHMENTS_EDIT_ENABLED=true
- python start.py; exercise uploads and marks via UI
- pytest -q
- git add -A && git commit -m "P2: upload/replace staging, manifest endpoints, shared UI"
- Update plan-state.json to P2.DONE

Rollback
- ATTACHMENTS_EDIT_ENABLED=false to block edits; staged artifacts remain for later cleanup

-------------------------------------------------------------------------------

PHASE 3 — Remove/Keep Actions & Pre-Release Confirmation

Objective
- Allow explicit remove/keep decisions and show a pre-release summary dialog warning about critical removals.

Backend Tasks
- Extend POST /attachments/mark to support keep explicitly and validate combinations
- No new endpoints beyond P2

Frontend Tasks
- Add “Undo Remove” or “Keep” actions
- Pre-release confirmation (used by both Save & Release buttons):
  - Summarize: X added, Y replaced, Z removed
  - Warn on “critical” types removal (configurable: e.g., PDFs)
  - Confirm -> proceed; cancel -> return to editor

Gate Criteria
- Summary matches manifest history
- Warnings display when configured
- Confirmation controls continue to work in both modal and full-page editors

Test Plan
- Unit: summary computation from manifest
- UI: click flows for remove/undo and pre-release confirm
- Run: pytest -q

Commands
- python start.py; validate in UI
- pytest -q
- git add -A && git commit -m "P3: remove/keep and pre-release confirmation in editors"
- Write plan-state.json P3.DONE

Rollback
- Hide summary UI via feature flag; server remains unchanged

-------------------------------------------------------------------------------

PHASE 4 — Release-time MIME Rebuild, Streaming APPEND, Cleanup

Objective
- Extend release path to rebuild MIME using manifest; stream via IMAP APPEND; cleanup staged artifacts; preserve originals.

Backend Tasks
1) Extend [python.api_interception_release()](app/routes/interception.py:453)
- Acquire per-email lock (from prior concurrency plan)
- Reload manifest and email_messages.version; validate limits
- Build message with [python._rebuild_mime_with_manifest()](app/routes/interception.py:1):
  - Preserve headers (From/To/Cc/Bcc/Date/References/In-Reply-To)
  - Regenerate Message-ID when edited (existing code already does this at [python.api_interception_release()](app/routes/interception.py:621))
  - Multipart/mixed with text/plain + html alternative; handle inline via CID and inline disposition (multipart/related acceptable as follow-on)
  - Filenames via RFC 2231/5987 helper
- Write to temp file and mmap for imap.append
- On success:
  - Set RELEASED state (existing code downstream)
  - Clear attachments_manifest and delete staged rows/files
  - Keep originals
2) Idempotency
- Respect X-Idempotency-Key if sent (optional)
3) Audit & Metrics
- Log attachment decisions and timings; record counters in [python.metrics](app/utils/metrics.py:1)

Frontend Tasks
- Save & Release buttons (modal and full-page) call pre-release summary, then release API
- On success: close modal / show success toast; reload list

Config/Guardrails
- ATTACHMENTS_RELEASE_ENABLED=true to turn on rebuild logic in release flow

Gate Criteria
- Scenario: remove one, replace one, add one -> release succeeds
- Final IMAP message shows expected MIME structure and filenames
- Staged directory empty for that email after release; originals remain

Test Plan
- Unit: filename encoding (RFC 2231), CID inline handling, nested multiparts
- Property-based: randomized attachments round-trip structural invariants
- Integration (end-to-end):
  - intercept → edits → release → IMAP fetch → assert MIME
- Smoke: large attachment rebuild bounded memory (temp-file + mmap)
- Run: pytest -q

Commands
- Set ATTACHMENTS_RELEASE_ENABLED=true (staging/canary)
- Run scenario; verify via inbox or IMAP fetch
- pytest -q
- git add -A && git commit -m "P4: release-time MIME rebuild, streaming append, staged cleanup"
- plan-state.json P4.DONE

Rollback
- Disable ATTACHMENTS_RELEASE_ENABLED; edits remain staged until next window

-------------------------------------------------------------------------------

PHASE 5 — Janitor, Quotas, Observability

Objective
- Add periodic purge of orphaned staged artifacts, optional per-account quotas, enhanced metrics and alerts.

Backend Tasks
- Janitor job (cron-like within process or external runner) to:
  - Delete attachments_staged/&lt;email_id&gt;/ older than N hours with empty manifest or non-HELD status
  - Log deletions and count bytes reclaimed
- Add metrics: attachments_janitor_deleted_bytes_total, attachments_janitor_runs_total

Frontend Tasks (optional)
- UI surface for storage warnings (if quotas implemented)

Gate Criteria
- Orphans get deleted after threshold; no data loss of originals
- Metrics exposed and logs readable

Test Plan
- Unit: janitor selection and deletion
- Integration: create dummy staged, simulate age, run janitor, verify cleanup

Commands
- Run janitor once manually; then schedule
- pytest -q
- git add -A && git commit -m "P5: janitor, quotas (optional), and metrics"
- plan-state.json P5.DONE

Rollback
- Disable janitor; no further action needed

-------------------------------------------------------------------------------

Long-running Autonomous Execution Guidance

- The agent should:
  1) Execute phases sequentially; do not parallelize backend + frontend changes within a phase.
  2) After each implementation subtask, run pytest -q; on failures, fix and re-run up to 5 times.
  3) Keep flags OFF until gate validation is ready; then flip the minimum flag needed per phase.
  4) Persist phase checkpoints to plan-state.json after gate passes.
  5) Commit with a descriptive message per phase and sub-phase; push if CI is present.

Timeouts and Retries
- Unit tests: 5 minutes per phase
- Integration/IMAP tests: 10 minutes; retry once on network flake
- Server start: 120 seconds; fail if health endpoint doesn’t respond

Artifacts and State
- plan-state.json for progress
- logs/… for build logs
- screenshots/ and tests/ outputs retained for regression analysis (if applicable)

Security and Risk Controls
- Never overwrite originals in attachments/
- Only delete staged artifacts after successful release or explicit staged-delete endpoint call
- Always sanitize filenames and sniff content; never trust client MIME
- Enforce size/count limits; fail early with actionable messages
- Audit log every upload/replace/remove/finalize via [python.audit.log_action()](app/services/audit.py:1)

Branching and Commits
- Branch: feature/attachments-e2e
- Commit messages:
  - P1: schema, extraction, list+download endpoints and read-only UI
  - P2: upload/replace staging, manifest endpoints, shared UI
  - P3: remove/keep and pre-release confirmation in editors
  - P4: release-time MIME rebuild, streaming append, staged cleanup
  - P5: janitor, quotas (optional), and metrics

Smoke Validation Script (manual or CI step)
- Flags: UI=true, EDIT=true, RELEASE=true
- Steps:
  - Create a held email with 2 attachments (fixture or live)
  - Add a new PDF, replace existing, remove one
  - Save & Release
  - Fetch via IMAP and assert structure (test helper)
  - Ensure attachments_staged/&lt;email_id&gt;/ empty; attachments/&lt;email_id&gt;/ preserved

This runbook is designed to be followed by an autonomous agent executing unattended for hours. Each phase contains deterministic tasks, gates, and explicit rollback paths. The coding agent should implement code in the named files, run the commands listed, and only advance when the Gate Criteria are satisfied. If a gate fails, apply the rollback described, fix issues, and reattempt until the gate passes.
