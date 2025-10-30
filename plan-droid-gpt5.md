# Release Flow Hardening and UI Reliability Plan

## Stage 0 — Reproduce, Baseline, and Guardrails
- Actions:
  - Capture logs around duplicate releases; confirm endpoints used by full page vs unified modal.
  - Verify CSRF, session, and current JS fetch patterns in static/js/app.js.
  - Add temporary correlation ID per request (uuid4 in g.request_id) to trace flows end-to-end.
- Acceptance:
  - One-page runbook with exact steps to reproduce and a log snippet proving current duplication.

## Stage 1 — Frontend Debounce + UX Feedback
- Actions:
  - Disable all per-email release/edit buttons immediately upon click; show spinner and prevent further clicks until response.
  - Debounce handlers (300–500 ms) and guard against repeated submissions.
  - Always show toast on success/failure; no silent redirects; keep user on context page.
- Acceptance:
  - Rapid-click (10x) on Save & Release triggers only one network call.
  - Visual spinner and disabled state are consistent across full view and unified modal.
- Key pattern (example):
  - JS: trackProcessing[emailId] = true; disable buttons with [data-email-id="ID"]. Re-enable on completion/errors.

## Stage 2 — Unified Modal and Detail View Fixes
- Actions:
  - Implement tabs parity: Raw, HTML, Plain across modal and full view; ensure missing functions (showRawBody, showDetails) populate content.
  - Raw body: decode b'..' payload, convert CRLF → newlines, escape safely, use <pre> with wrapping.
  - Details grid: populate Message-ID, From, To, Subject, Date, MIME-Version, Content-Type, CTE, Sender IP (from Received) from backend payload; hide "—" placeholders only when truly missing.
- Acceptance:
  - Toggling tabs shows correct content in both views; details grid fully populated for known messages.
- Key pattern:
  - Backend returns raw, text, html, headers map; front-end renders consistently via one renderEmailDetails(data) function.
## Stage 3 — Server-Side Concurrency Control (Locks + Idempotency)
- Actions:
  - Add per-email release lock using DB-backed lock table + in-memory map (to cover multi-thread + multi-request in same process):
    - Table: release_locks(email_id INTEGER PRIMARY KEY, operation TEXT, created_at DATETIME)
    - Unique constraint on email_id; acquire via INSERT OR IGNORE; release in finally.
  - Accept Idempotency-Key header (UUID from client). Persist active operation keyed by (email_id, op='release', idempotency_key) and return existing result if repeated.
  - On duplicate in-progress: return 409 Conflict with {job_id, status:"RUNNING"}.
- Acceptance:
  - Two concurrent POSTs for same email: one runs, one returns 409 with the same job reference; only one IMAP sequence executes.
- Minimal SQL (illustrative):
  - CREATE TABLE IF NOT EXISTS release_locks (email_id INTEGER PRIMARY KEY, operation TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
  - INSERT OR IGNORE INTO release_locks(email_id, operation) VALUES (?, 'release'); -- if 0 rows → already locked

## Stage 4 — Job/Operation Tracking API
- Actions:
  - Create email_operations table (id, email_id, op_type, idempotency_key, state [PENDING/RUNNING/SUCCESS/FAILED], started_at, finished_at, result_meta JSON).
  - release/edit endpoints:
    - On accept: create job (RUNNING), return 202 Accepted with Location: /api/jobs/{job_id} and JSON {job_id}.
    - Client polls job status (simple GET) until terminal state; update UI accordingly.
- Acceptance:
  - Client remains on page, shows progress; job reaches SUCCESS; duplicate clicks receive the same job_id or 409 with running job.
## Stage 5 — IMAP Release Pipeline Idempotency
- Actions:
  - Tag appended message with custom header X-EMT-Release-UUID: <job_id> and persist new UID/Gmail-Message-ID in DB.
  - Before append: search mailbox for header X-EMT-Release-UUID == job_id; if found, skip append and proceed to verification.
  - Ensure purge/cleanup phases are safe to re-run; make every phase check-before-do.
- Acceptance:
  - Re-running the release pipeline for the same job_id does not create duplicates; phases are no-ops if already completed.

## Stage 6 — Post-Release UI Truth Source
- Actions:
  - After SUCCESS, refresh the list/detail from DB using the edited body and headers; ensure UI shows the edited content, not original.
  - Update any cached state in unified modal to reflect edited data; no redirect to list unless user triggers it.
- Acceptance:
  - UI shows edited message content immediately after SUCCESS; inbox also shows edited; no stale renders.

## Stage 7 — Styling and Accessibility
- Actions:
  - Conform to docs/STYLEGUIDE.md for buttons: padding, line-height, icon alignment; use a shared .action-btn spec.
  - Ensure focus/disabled states are visible; aria-busy on actionable elements during processing.
- Acceptance:
  - Buttons are visually consistent across pages; keyboard navigation and focus states verified.
## Stage 8 — Tests and Instrumentation
- Actions:
  - Pytest: simulate concurrent POSTs (threaded client) verifying one success + one 409; verify no IMAP duplicates (mock IMAP).
  - JS unit/integration (if present) or Playwright-lite flows: rapid-click test prevents duplicates and shows spinner/toast.
  - Structured logs: include request_id and job_id in every phase A–E log line.
- Acceptance:
  - New tests pass; log lines show clear correlation; manual rapid-click test is safe.

## Stage 9 — Rollout and Migration
- Actions:
  - Migration scripts to create release_locks and email_operations; feature flag (ENV or config) to enable lock/idempotency.
  - Backfill none required; no downtime needed (SQLite CREATE IF NOT EXISTS).
- Acceptance:
  - Migrations run cleanly; flag can toggle behavior if issues arise.

### Implementation Touchpoints (no code changes yet)
- Frontend: static/js/app.js, templates/emails_unified.html (or equivalent), templates/email_detail.html, shared components/styles.
- Backend: app/routes/interception.py (release/edit endpoints), app/routes/emails.py (detail fetch), app/utils/db.py, app/services/imap/* (release phases), app/utils/logging.py (request_id/job_id), new tables.
### Client–Server Contract (minimal)
- Request: POST /api/email/{id}/edit and/or POST /api/interception/release/{id}
  - Headers: X-CSRFToken, Idempotency-Key: <uuid>
- Response on accept: 202 { job_id, status:"RUNNING" }, Location: /api/jobs/{job_id}
- GET /api/jobs/{job_id} → { job_id, email_id, op_type, status, error?, result_meta }
- Duplicate in-progress: 409 { job_id, status:"RUNNING" }

### Success Criteria (end-to-end)
- Zero duplicate releases under 10 rapid clicks or page re-submits.
- Only one IMAP append per email/job under all conditions.
- Unified modal and full view show correct tabs and details; edited content reflects immediately.
- Clear visual feedback and consistent button behavior; tests cover concurrency and idempotency.

Preferred sequence: Stage 1 → Stage 3 first (debounce, locks, idempotency), then Stage 2/6 (UI fidelity), followed by jobs API and tests.
## Stage 10 — Attachments: Data Model & Storage
- Actions:
  - Create on-disk layout: attachments/<email_id>/original/ and attachments/<email_id>/staged/.
  - Persist metadata for each original attachment: filename, mime_type, size_bytes, checksum (sha256), disk_path, is_inline, content_id.
  - Tables (SQLite):
    - email_attachments(id INTEGER PK, email_id INTEGER, filename TEXT, mime_type TEXT, size_bytes INTEGER, checksum TEXT, disk_path TEXT, is_inline INTEGER DEFAULT 0, content_id TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP).
    - email_attachment_edits(id INTEGER PK, email_id INTEGER, action TEXT CHECK(action IN ('add','replace','remove')), original_attachment_id INTEGER NULL, filename TEXT NULL, mime_type TEXT NULL, size_bytes INTEGER NULL, checksum TEXT NULL, disk_path TEXT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP).
- Acceptance:
  - For a held email with 2 attachments, they appear in email_attachments with correct checksums and files exist on disk.
## Stage 11 — Ingestion: Watcher Persists Attachments
- Actions:
  - Extend the IMAP watcher/store function to iterate MIME parts and save attachments to attachments/<email_id>/original/.
  - Compute sha256 while streaming to disk; avoid loading large files fully in memory.
  - Insert metadata rows into email_attachments.
- Acceptance:
  - New incoming messages with attachments create files and metadata; large files (>10MB) do not cause memory spikes.

## Stage 12 — API: Attachment Management Endpoints
- Actions:
  - Routes (examples):
    - GET  /api/email/<id>/attachments → list originals + staged preview state.
    - GET  /api/email/<id>/attachments/<att_id>/download?scope=original|staged → stream download.
    - POST /api/email/<id>/attachments (multipart) → upload new (staged, action='add').
    - PUT  /api/email/<id>/attachments/<att_id> (multipart) → replace original with uploaded (staged, action='replace').
    - DELETE /api/email/<id>/attachments/<att_id>?scope=original → stage removal (action='remove').
    - DELETE /api/email/<id>/attachments/staged → clear staged changes.
  - Reuse CSRF and Idempotency-Key; return JSON manifest summary.
- Acceptance:
  - Can add/replace/remove staged attachments via API; downloads stream as_attachment with correct mime.
## Stage 13 — UI: Attachments Panel (Modal + Full View)
- Actions:
  - Build a shared attachments component (templated partial + JS module) used by emails-unified modal and email detail page.
  - Display list with filename, size, type, badges for inline; actions: Download, Remove, Replace.
  - Add drag-and-drop and button upload; show progress, size/type validation, and toasts; disable actions while processing.
  - Respect debounce/lock system; buttons reflect job state; consistent styling per STYLEGUIDE.
- Acceptance:
  - User can add a new attachment, replace an existing one, or stage a removal in both views; UI state persists and reflects staged actions.

## Stage 14 — Manifest: Persist Staged Decisions
- Actions:
  - Persist user intent in email_attachment_edits per operation (add/replace/remove) with references to staged files.
  - Expose GET /api/email/<id>/attachments/manifest → consolidated view combining originals + staged edits (effective result).
  - Ensure server-side validation of actions (e.g., replace requires original_attachment_id).
- Acceptance:
  - Manifest reflects all staged edits; clearing staged removes entries and files under staged/.
## Stage 15 — Release: MIME Reconstruction with Attachments
- Actions:
  - On release, load originals + manifest and reconstruct MIME using email.mime module:
    - Create multipart/mixed; include text/plain and text/html parts as edited; preserve inline images via Content-ID mapping.
    - Apply staged ops: remove originals, replace bodies, add new attachments from staged/.
    - Set new Message-ID; keep Date and From/To; update headers accordingly.
  - Integrate with existing idempotent release pipeline; write X-EMT-Release-UUID and persist new UID/Message-Id.
- Acceptance:
  - E2E: Replace original PDF with new version and add a second PDF; released message in inbox matches expected attachments.

## Stage 16 — Cleanup & Retention
- Actions:
  - On SUCCESS or DISCARD, delete staged files and edits rows; keep originals for N days (config) then purge.
  - Provide scripts/cleanup_attachments.py and nightly job (optional) to enforce retention.
- Acceptance:
  - No orphaned staged files after operations; retention purges old originals per policy.
## Stage 17 — Security & Guardrails
- Actions:
  - Enforce MAX_ATTACHMENT_SIZE_MB and ALLOWED_MIME/EXT lists; verify content by sniffing minimal magic (e.g., %PDF- for PDFs).
  - Sanitize filenames (secure_filename), store outside static/, and serve via send_file with as_attachment.
  - Compute and store checksum for integrity; reject duplicates if needed.
  - Rate-limit attachment endpoints; include CSRF tokens; log user + IP.
- Acceptance:
  - Oversized/unsupported uploads are blocked with clear toasts; downloads are streamed safely.

## Stage 18 — Tests: Unit + Integration
- Actions:
  - Unit: MIME part extraction, checksum computation, filename sanitization; manifest merge logic for add/replace/remove.
  - Integration: intercept email with PDF, stage remove, stage replace, stage add; Save & Release; verify IMAP result and no duplicates under fast clicks.
  - Concurrency test: parallel uploads for same email obey locks and produce deterministic manifest.
- Acceptance:
  - All new tests pass; coverage increases over attachments code paths.

## Stage 19 — Rollout & Migration
- Actions:
  - Migrations for new tables; create folders on startup if missing; config flags for enabling attachments UI and size limits.
  - Backward-compatible: emails without attachments unaffected; feature flag can disable UI.
- Acceptance:
  - Migrations run without downtime; toggling flag hides attachments UI safely.

## Stage 20 — Observability
- Actions:
  - Structured logs include request_id, job_id, email_id, attachment_id, action, bytes.
  - Metrics: attachment_upload_total, attachment_bytes_total, attachment_edit_failures_total.
- Acceptance:
  - Dashboards/grepable logs clearly show attachment operations and failures.
### Client–Server Contract Addendum (Attachments)
- GET  /api/email/{id}/attachments → { originals: [...], staged: [...], effective: [...] }
- GET  /api/email/{id}/attachments/{att_id}/download?scope=original|staged → file stream
- POST /api/email/{id}/attachments (multipart) → stage add; returns manifest
- PUT  /api/email/{id}/attachments/{att_id} (multipart) → stage replace; returns manifest
- DELETE /api/email/{id}/attachments/{att_id}?scope=original → stage remove; returns manifest
- DELETE /api/email/{id}/attachments/staged → clear staged edits
- Headers: X-CSRFToken, Idempotency-Key
- Responses: 200/202 with manifest; 413 for size; 415 for type; 409 on conflicts (locked)

### Success Criteria (Attachments)
- Users can add/replace/remove/download attachments from both unified modal and full view.
- Release reconstructs MIME correctly and idempotently; inbox shows expected attachments.
- No duplicate releases under rapid clicks; uploads obey size/type/security policies.

## Autonomous Agent Runbook — Overnight Execution

This section provides exact, step-by-step instructions for a coding agent (Claude Code / Codex / Droid CLI) to implement the plan autonomously, test thoroughly, and run uninterrupted for hours. Follow the gates strictly; do not skip tests or commits.

### Global Rules
- Environment: Windows (PowerShell or CMD). Use absolute paths.
- Do NOT run the Flask server during implementation steps. Avoid network-dependent tests (mock IMAP/SMTP where needed).
- Always run: python -m pytest tests/ -v after each stage. Fix all failures before proceeding.
- Before any commit:
  1) git status and git diff (and git diff --cached if staged)
  2) Scan diffs for secrets (keys, tokens, passwords)
  3) Run tests, ensure all pass
- Commit atomically per stage with clear messages; never push unless a human requests it.

### Tooling Setup (once)
- python -m pip install -r requirements.txt
- If available: python -m pip install -r requirements-dev.txt
- Optional: pre-commit run -a (if pre-commit is installed)
- Baseline: python -m pytest tests/ -v

### Branching/Commits
- Create branch: git checkout -b feat/release-hardening-attachments
- Commit template (example):
  fix(release): add per-email locks and idempotency; debounce UI; tests for concurrency
  
  Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>

### Execution Order (with Gates)
- Phase A: Stage 1 (debounce/UX) → Gate GA
- Phase B: Stage 3 (locks/idempotency) → Gate GB
- Phase C: Stage 4 (jobs API) → Gate GC
- Phase D: Stage 2 + Stage 6 (UI parity + post-release truth) → Gate GD
- Phase E: Stage 7 (styling) → Gate GE
- Phase F: Stage 8 (tests/instrumentation) → Gate GF
- Phase G: Stage 9 (rollout/migration) → Gate GG
- Phase H: Stage 10–12 (attachments: model, ingestion, API) → Gate GH
- Phase I: Stage 13–15 (UI attachments + MIME reconstruction) → Gate GI
- Phase J: Stage 16–20 (cleanup, security, tests, rollout, observability) → Gate GJ

Each Gate requires: all tests pass; no lints blocking; diffs reviewed; commit created.

### Per-Stage Checklist Template
1) Identify touchpoints (files/modules) and planned edits
2) Make minimal changes to satisfy acceptance criteria
3) Update/add unit tests
4) Run: python -m pytest tests/ -v (and narrower -k filters while iterating)
5) Review diffs for secrets/unsafe changes
6) Commit with the stage-specific message
7) Proceed to the next stage

### Phase A — Stage 1: Frontend Debounce + UX
- Targets: static/js/app.js, templates (modal + full view buttons)
- Tasks:
  - Disable buttons on click; add spinner; prevent double-submits; toasts for outcomes; no forced redirects
  - Share utilities for button state per emailId
- Tests: existing UI tests or add small JS-focused checks if framework exists; otherwise validate via endpoint call counts in Python tests (simulate multiple POSTs prevented at UI handler)
- Gate GA Commands:
  - python -m pytest tests/ -v -k "(intercept or release) and not slow"
  - git add -A && git commit -m "feat(ui): debounce release/edit actions; disable buttons; add consistent toasts"

### Phase B — Stage 3: Locks + Idempotency
- Targets: app/routes/interception.py, app/utils/db.py, app/services/imap/* (only for lock hooks)
- Tasks:
  - Add DB table release_locks; in-memory lock map; acquire/release; return 409 with job ref on duplicates
  - Accept Idempotency-Key header
- Tests: concurrent POSTs → one RUNNING, one 409; no duplicate IMAP pipeline calls (mock)
- Gate GB Commands:
  - python -m pytest tests/ -v -k "concurrent or idempotent"
  - git add -A && git commit -m "fix(release): per-email DB+memory locks; 409 on duplicates; idempotency key support"

### Phase C — Stage 4: Jobs API
- Targets: routes for /api/jobs/<id>, modifications to release/edit endpoints
- Tasks: return 202 with Location; polling endpoint; state transitions
- Tests: accept returns job_id; polling reaches SUCCESS
- Gate GC Commands:
  - python -m pytest tests/ -v -k jobs
  - git add -A && git commit -m "feat(api): job tracking with 202+Location and polling endpoint"

### Phase D — Stage 2 + 6: UI Parity + Truth Source
- Targets: modal + full view tabs; detail grid; renderEmailDetails
- Tasks: Wire tabs; proper raw/HTML/plain; details populated; after SUCCESS reflect edited content without redirect
- Tests: verify rendering via API payloads; server unit tests ensure fields provided
- Gate GD Commands:
  - python -m pytest tests/ -v -k "ui or details"
  - git add -A && git commit -m "feat(ui): parity across views; correct details; post-release shows edited content"

### Phase E — Stage 7: Styling
- Targets: CSS/HTML classes per STYLEGUIDE
- Tasks: normalize padding/line-height; icon alignment; focus states; aria-busy
- Gate GE Commands:
  - python -m pytest tests/ -v
  - git add -A && git commit -m "style: unify action button styles per STYLEGUIDE"

### Phase F — Stage 8: Tests/Instrumentation
- Targets: add tests; logging correlation IDs
- Tasks: concurrent tests; structured logs include request_id/job_id
- Gate GF Commands:
  - python -m pytest tests/ -v
  - git add -A && git commit -m "test(log): concurrency tests and structured logging with correlation IDs"

### Phase G — Stage 9: Rollout/Migration
- Targets: migration scripts; config flags
- Tasks: CREATE IF NOT EXISTS for new tables; feature flags for locks/idempotency
- Gate GG Commands:
  - python -m pytest tests/ -v
  - git add -A && git commit -m "chore(migration): tables and flags for locks/idempotency"

### Phase H — Stages 10–12: Attachments Model, Ingestion, API
- Targets: tables, storage layout; watcher; REST endpoints
- Tasks: implement on-disk + metadata; persist originals; API list/download/add/replace/remove
- Tests: unit (parsing); integration (list/download); size/mime validation basics
- Gate GH Commands:
  - python -m pytest tests/ -v -k "attachment and not slow"
  - git add -A && git commit -m "feat(attachments): model, ingestion, and REST endpoints"

### Phase I — Stages 13–15: UI + MIME Reconstruction
- Targets: attachments panel in modal and full view; release MIME builder
- Tasks: shared component; DnD uploads; manifest; MIME rebuild with inline CID mapping
- Tests: end-to-end manifest → release; compare resulting attachments
- Gate GI Commands:
  - python -m pytest tests/ -v -k "attachments and (ui or release)"
  - git add -A && git commit -m "feat(attachments): UI flows and idempotent MIME reconstruction on release"

### Phase J — Stages 16–20: Cleanup, Security, Tests, Rollout, Observability
- Targets: cleanup script/policy; guards; metrics/logs
- Tasks: retention purge; filename sanitization; rate-limit; metrics counters
- Tests: security/unit; concurrent uploads; cleanup assertions
- Gate GJ Commands:
  - python -m pytest tests/ -v
  - git add -A && git commit -m "chore(attachments): cleanup, security guardrails, tests, and observability"

### Failure & Resume Policy
- If tests fail:
  - Fix and re-run up to 3 attempts per stage; keep changes minimal
  - If still failing, revert the last staged edits and open a NOTE in the commit message describing blockers
- If process stops mid-run:
  - On restart, read this runbook; find the last gate commit; resume at the next phase

### Resource & Time Budgets (guidance)
- Stage 1/3: 45–90 min each
- Jobs API + UI parity: 60–120 min
- Attachments phases collectively: 3–5 hours (broken across H and I)
- Security/cleanup/tests: 60–120 min

### Safety Notes
- Never modify key.txt or commit secrets
- Avoid touching production-like configs; use feature flags default-off
- SQLite migrations must be backward-compatible
