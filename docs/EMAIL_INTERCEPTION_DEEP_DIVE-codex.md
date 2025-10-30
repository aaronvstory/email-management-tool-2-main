# Email Interception Deep Dive

> _Last updated: 2025-10-14_

This document explains the **active** interception pipeline (IMAP-based) and the legacy SMTP proxy (kept only for reference). Each section links to the concrete code responsible for the step so you can experiment or troubleshoot quickly.

---

## 1. Rule Evaluation & Shared Utilities

Before the IMAP watcher or manual tools decide whether to quarantine a message, we run the rule engine and use a shared database layer. These components are reused across the pipeline.

### 1.1 Rule Evaluation Engine
- **Location:** `app/utils/rule_engine.py`
- **Export:** `evaluate_rules(subject, body_text, sender, recipients, db_path=...)`
- **Purpose:** Returns `should_hold`, `risk_score`, `matched_rules`, and keywords for any message content. Supports both legacy (`keyword`, `action`, `priority`) and extended (`rule_type`, `condition_*`) schemas.
- **Key helpers:** `_normalize_recipients`, `_extract_sender_domain`, and dual-schema detection via `PRAGMA table_info`.

### 1.2 Database Utilities
- **Location:** `app/utils/db.py`
- **Highlights:**
  - `get_db()` sets up a SQLite connection with WAL mode and Row factory.
  - `get_db_path()` respects `TEST_DB_PATH` for isolated test runs.
  - `fetch_counts()` provides aggregated stats for dashboards.


---

## 2. IMAP-Based Interception (Active Path)

All live interception is handled through the IMAP watcher service, which monitors accounts, applies rules, moves mail into quarantine, and tracks status in the database.

### 2.1 Configuration & Lifecycle
- **Location:** `app/services/imap_watcher.py`
- **Entry point:** class `ImapWatcher(AccountConfig)` with `run_forever()` orchestrating connection, IDLE loop, and sweeps.
- **Heartbeat & circuit breaker:** `_update_heartbeat` and `_record_failure` update `worker_heartbeats` and disable accounts if repeated failures occur.

### 2.2 Polling for New Messages
- **Function:** `_handle_new_messages(client, changed)`
- **Process:**
  1. Derives candidate UIDs from `UIDNEXT` deltas and configurable last-N sweeps.
  2. Filters out previously stored UIDs via a SQL lookup on `email_messages.original_uid`.
  3. Delegates actual persistence and rule evaluation to `_store_in_database`.

### 2.3 Storing & Marking Messages
- **Function:** `_store_in_database(client, uids)`
- **Responsibilities:**
  - Fetches RFC822 payload, message metadata, and INTERNALDATE from the IMAP server.
  - Runs `evaluate_rules` to determine whether the message should be intercepted (`should_hold`).
  - Inserts a row into `email_messages` with `interception_status='INTERCEPTED'` when a rule match occurs and `'FETCHED'` otherwise.
  - Returns the list of UID integers that require movement to quarantine.
- **Unit coverage:** `tests/services/test_imap_watcher_decision.py::test_store_in_database_returns_only_rule_matched_uids`

### 2.4 Moving to Quarantine
- **Movement orchestrator:** `_move(held_uids)`
- **Fallback path:** `_copy_purge(held_uids)` for IMAP servers lacking `UID MOVE`.
- **Status reconciliation:** `_update_message_status(held_uids, 'HELD')` sets `interception_status='HELD'`, `status='PENDING'`, timestamps `action_taken_at`, and calculates latency if missing.
- **Helpers:** `_ensure_quarantine` and `_move_uid_to_quarantine` (detailed in §4) resolve folder names, create missing mailboxes, and perform the actual IMAP operations.

---

## 3. REST Endpoints & User Operations

### 3.1 Fetching Emails on Demand
- **Route:** `app/routes/emails.py::api_fetch_emails`
- **Flow:**
  1. Authenticated request / account selection.
  2. Performs IMAP `SEARCH`/`FETCH` to retrieve message headers & bodies.
  3. Inserts each fetched message as `'FETCHED'` by default.
  4. When `AUTO_MOVE_ON_FETCH=1`, evaluates rules inline and, if matched, calls `_ensure_quarantine` and `_move_uid_to_quarantine`. Successful moves update the row to `'HELD'` and store the resolved quarantine folder name.
- **Response payload:** Each item includes `should_hold`, `held`, and `quarantine_folder` to inform the UI.

### 3.2 Manual Intercept (Retroactive hold)
- **Route:** `app/routes/interception.py::api_email_intercept`
- **Use case:** Admin selects a previously delivered message and forces it back into quarantine.
- **Key steps:**
  - Short-circuits if the message is already `HELD`.
  - Establishes an IMAP session using `imaplib.IMAP4` or `IMAP4_SSL` with credentials from `email_accounts`.
  - Resolves IMAP UID using stored `original_uid`, `Message-ID`, `Subject`, and Gmail-specific `X-GM-RAW` search as a fallback.
  - Calls `_ensure_quarantine` + `_move_uid_to_quarantine`; aborts with 409/502 if the remote move fails (no false positives).
  - On success, updates `interception_status`, `status`, `quarantine_folder`, timestamps, and backfills `original_uid` if missing.
- **Tests:** `tests/routes/test_manual_intercept_logic.py`

### 3.3 Editing Held Messages
- **Route:** `app/routes/interception.py::api_email_edit`
- **Behavior:** Validates that the message is `HELD`, applies field updates (`subject`, `body_text`, `body_html`), and audits the change. Edits are reflected immediately for downstream release.

### 3.4 Releasing Messages
- **Route:** `app/routes/interception.py::release_email` (not excerpted earlier but co-located)
- **Process:**
  - Reconstructs MIME (including optional edits) and uses IMAP `APPEND` to restore the message to `INBOX`.
  - Sets `interception_status='RELEASED'`, `status='DELIVERED'`, and records latency / audit entries.
---

## 4. IMAP Movement Utilities

### 4.1 Folder Resolution
- **Function:** `_ensure_quarantine(imap_obj, folder_name='Quarantine')`
- **Implementation:** Iteratively attempts variants (`Quarantine`, `INBOX/Quarantine`, `INBOX.Quarantine`), creating folders when necessary and always returning the effective mailbox string. Ensures the original mailbox (usually `INBOX`) is re-selected afterward.
- **Usage:**
  - IMAP watcher during `_move` and `_copy_purge`.
  - On-demand fetch auto-move and manual intercept routes.

### 4.2 Movement Primitive
- **Function:** `_move_uid_to_quarantine(imap_obj, uid, quarantine='Quarantine')`
- **Steps:**
  1. Ensures target folder via `_ensure_quarantine`.
  2. Attempts native `UID MOVE`; on failure, falls back to `UID COPY` + `STORE \Deleted` + `EXPUNGE`.
  3. Swallows non-critical errors when setting flags to accommodate providers with UID remapping semantics.

### 4.3 Account Connector
- **Function:** `_imap_connect_account(account_row)`
- **Purpose:** Shared utility for on-demand routes to initiate a logged-in IMAP session with proper TLS/STARTTLS selection.
---

## 5. Database Schema Touchpoints

### 5.1 `email_messages`
- **Columns of interest:**
  - `interception_status` (`FETCHED`, `INTERCEPTED`, `HELD`, `RELEASED`)
  - `status` (workflow state: `PENDING`, `DELIVERED`, etc.)
  - `quarantine_folder` (resolved mailbox name)
  - `original_uid` (IMAP UID captured at interception)
  - `original_internaldate` (server timestamp)
  - `action_taken_at`, `latency_ms` (timings for dashboards)

### 5.2 `moderation_rules`
- **Schema detection:** handled inside `evaluate_rules` to support both legacy keyword-based rows and newer structured condition rows.
- **Testing:** `tests/utils/test_rule_engine_schemas.py` verifies both variants.
---

## 6. Testing & Experimentation Aids

### 6.1 Unit Tests
- `tests/services/test_imap_watcher_decision.py`
  - Focuses on `_store_in_database` and `_update_message_status` using a monkeypatched `evaluate_rules` for deterministic outcomes.
- `tests/routes/test_manual_intercept_logic.py`
  - Simulates IMAP interactions with `FakeIMAP` to validate success and failure paths.
- `tests/utils/test_rule_engine_schemas.py`
  - Confirms rule engine behavior across legacy and extended schemas.

### 6.2 Live Experiments (Opt-in)
- `tests/live/test_quarantine_flow_e2e.py`
  - Gated by `ENABLE_LIVE_EMAIL_TESTS=1` and provider-specific credentials.
  - Sends a real email via SMTP, waits for delivery, runs watcher primitives manually, verifies movement, and restores the message to `INBOX` for repeatability.

### 6.3 Environment Toggles
- `AUTO_MOVE_ON_FETCH` (route-level auto quarantine during `/api/fetch-emails`).
- `IMAP_FORCE_COPY_PURGE`, `IMAP_SWEEP_LAST_N`, `IMAP_CIRCUIT_THRESHOLD` (watcher tuning knobs).
- `ENABLE_WATCHERS` and per-account `is_active` flag (start/stop threads).
- `TEST_DB_PATH` to isolate test databases.
---

## 7. Quick Reference Table

| Stage | Function / Route | File | Notes |
|-------|------------------|------|-------|
| Rule evaluation | `evaluate_rules` | `app/utils/rule_engine.py` | Dual schema detection, returns `should_hold`. |
| Watcher persistence | `_store_in_database` | `app/services/imap_watcher.py` | Inserts `INTERCEPTED` vs `FETCHED`. |
| Watcher move | `_move`, `_copy_purge` | `app/services/imap_watcher.py` | Uses IMAP helpers based on capabilities. |
| Watcher status update | `_update_message_status` | `app/services/imap_watcher.py` | Marks `HELD`, computes latency. |
| Auto fetch route | `api_fetch_emails` | `app/routes/emails.py` | Optional auto-move on fetch. |
| Manual intercept | `api_email_intercept` | `app/routes/interception.py` | UID resolution + move with truthful status. |
| Edit held email | `api_email_edit` | `app/routes/interception.py` | Validates `HELD`, persists edits. |
| Release email | `release_email` | `app/routes/interception.py` | Rebuilds MIME, appends to INBOX, sets `RELEASED`. |
| IMAP helpers | `_ensure_quarantine`, `_move_uid_to_quarantine` | `app/utils/imap_helpers.py` | Folder discovery + move primitive. |
---

## 8. Suggested Experimentation Workflow

1. **Adjust rule logic** in `app/utils/rule_engine.py`; run `pytest tests/utils/test_rule_engine_schemas.py` to validate both schemas.
2. **Prototype movement variations** by editing `_move_uid_to_quarantine`; use the live E2E test (with credentials) for validation.
3. **Toggle auto-move behavior** via `AUTO_MOVE_ON_FETCH` when evaluating UX changes.
4. **Inspect watcher throughput** by enabling verbose logging (`IMAP_LOG_VERBOSE=1`) and observing `app/logs` output.
5. **Iterate safely** by leveraging `TEST_DB_PATH` to sandbox database changes during automated tests or notebook-style experiments.
---

## 9. Additional References

- `docs/INTERCEPTION_IMPLEMENTATION.md` – Original high-level architecture notes.
- `CLAUDE.md` – Comprehensive project overview, including security posture and testing strategy.
- `scripts/live_interception_e2e.py` – CLI script for full pipeline validation against staged accounts.

This deep dive should now reflect the current system: IMAP watcher as the active pipeline, shared rule/database utilities, optional REST entry points, and helper modules. Use it as a roadmap when experimenting with new interception strategies or debugging the existing flow.
