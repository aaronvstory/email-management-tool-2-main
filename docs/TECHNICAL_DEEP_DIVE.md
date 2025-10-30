# Technical Deep Dive — Email Management & Interception

This document is a practical, engineering-focused deep dive into how the system works today, what is required to build and operate it, and a blueprint for a clean, from-scratch implementation if we choose to reboot. It complements CLAUDE.md and docs/INTERCEPTION_IMPLEMENTATION.md.

## 1. Scope and Goals

- Intercept inbound email for review/moderation before delivery.
- Allow editing, holding, releasing, or discarding messages via a dashboard.
- Support multiple accounts (Gmail, Hostinger, Outlook, Yahoo, generic IMAP/SMTP).
- Securely store account credentials and provide auditable actions.
- Run locally on Windows with SQLite; no external services required.

Non-goals (current project):
- No POP3; no cloud persistence; no multi-tenant SaaS.
- No large-scale high-availability guarantees (single-node design).

## 2. High-Level Architecture

```
+-------------+    SMTP (port 8587)     +------------------+
| External    |  -------------------->  | SMTP Proxy (AIOS)|
| Senders     |                         |  Intercept+Store |
+-------------+                         +---------+--------+
                                                 |
                                                 v
                                         +---------------+
                                         | SQLite (WAL)  |
                                         | email_messages|
                                         | email_accounts|
                                         +-------+-------+
                                                 |
                                                 v
     +-------------------+                +--------------+
     | Flask Web (UI/API)| <--- SSE/REST | Stats/Audit  |
     +---------+---------+                +--------------+
               |
               v
         +-----------+
         | IMAP      |
         | Watchers  |
         +-----------+
```

Components:
- Web server (Flask): Dashboard, APIs, authentication, audit.
- SMTP proxy (aiosmtpd): Accepts inbound messages and stores them.
- IMAP watchers (threads): Monitor mailboxes, quarantine messages, record metadata.
- Rules engine: Keyword-based risk scoring, optional auto-hold.
- SQLite DB: Message store and encrypted credentials; WAL mode for concurrency.
- Frontend: Bootstrap 5 dark theme with toasts and modals.

## 3. Core Components

### 3.1 Web Server (Flask)
- Auth, account management, message listing/views, edit/release endpoints.
- SSE events and cached stats. CSRF and rate limit on auth.
- Uses dependency-injectable DB helpers for efficient counts/queries.

### 3.2 SMTP Proxy (aiosmtpd)
- Listens on 8587; parses MIME; applies rules; persists message rows (status=PENDING, optional HELD).
- Emits audit events and invalidates stats cache.

### 3.3 IMAP Watchers
- One thread per active account. IDLE loop; on new message, FETCH metadata (INTERNALDATE, UID), MOVE to Quarantine.
- Updates email_messages with interception_status=HELD, original_uid, latency.
- Respects SSL/STARTTLS settings and username overrides from DB.

### 3.4 Rules Engine
- moderation_rules table (active rules) with keyword lists and priority.
- Applies on SMTP receive; cumulative risk_score may trigger auto-hold.
- Fallback default keywords when DB has none.

### 3.5 Data Access Layer
- SQLite (WAL; busy_timeout) with indices for queue and counts.
- get_db() context manager with row_factory for dict-like access.

### 3.6 Credential Security
- email_accounts.passwords encrypted with Fernet (key.txt).
- Credentials come from DB at runtime; .env used by scripts/preflight.
- Never log plaintext secrets; redact in exceptions.

## 4. Data Model (Essential Tables)

email_accounts:
- id, account_name, email_address, imap_host/port/use_ssl, smtp_host/port/use_ssl,
  imap_username, smtp_username, imap_password (encrypted), smtp_password (encrypted), is_active.

email_messages:
- id, account_id, message_id, sender, recipients, subject, body_text, body_html, raw_content,
  status (PENDING/APPROVED/REJECTED/DELIVERED/SENT), interception_status (HELD/RELEASED/DISCARDED),
  risk_score, keywords_matched, original_uid, latency_ms, timestamps.

Indices:
- On interception_status, status, account filters, direction combos, and original_uid.

## 5. Configuration & Environments

.env (not committed):
- FLASK_SECRET_KEY, DB_PATH, ENABLE_WATCHERS.
- Live tests toggles and live credentials for scripts.

Provider detection rules:
- 587 → STARTTLS; 465 → SSL; 993 → SSL; username=email for most providers.

## 6. Detailed Flows

### 6.1 SMTP Interception Pipeline
1) Accept DATA → parse MIME (subject/body/attachments).
2) risk_score = rules(keyword hits with priority) → optional auto-hold.
3) INSERT row (status=PENDING; interception_status=HELD if held).
4) Audit log + stats cache invalidate.

### 6.2 IMAP Watcher Pipeline
1) Connect (SSL 993 or STARTTLS 143) → LOGIN → SELECT INBOX → IDLE.
2) On signal: search new UIDs → FETCH INTERNALDATE/ENVELOPE.
3) MOVE to Quarantine (or COPY+DELETE fallback).
4) UPSERT/UPDATE row: original_uid, interception_status=HELD, latency_ms.

### 6.3 Release Pipeline
1) Build MIME (merge edits if any) → IMAP APPEND to INBOX.
2) Update interception_status=RELEASED, status=DELIVERED; audit.

### 6.4 Compose/Send Pipeline
1) Resolve SMTP settings → connect (SSL vs STARTTLS) → AUTH.
2) sendmail; if 250 OK, INSERT SENT row (direction=outbound); audit.

## 7. State Machines

Interception status:
- NEW → HELD → RELEASED; or NEW/HELD → DISCARDED.

Message status:
- PENDING → APPROVED/REJECTED → DELIVERED; or SENT for outbound.

Invalid transitions return 409/400.

## 8. Concurrency Model & Backoff

- Threads: 1 main Flask, 1 SMTP proxy, N IMAP watcher threads.
- SQLite WAL mode + busy_timeout ensures reads while writes.
- IMAP failures: exponential backoff (cap ~5 minutes).
- SMTP intermittent: reconnect and single retry.

## 9. Error Handling & Taxonomy

- IMAP: AUTHENTICATIONFAILED (fix creds), timeouts (retry), MOVE unsupported (COPY+DELETE).
- SMTP: SMTPAuthenticationError (fix creds), disconnections/timeouts (retry), STARTTLS mismatch.
- DB: "database is locked" mitigated by WAL + busy_timeout + retry.

## 10. Observability

- app.log: key events with context (account id, provider, action).
- /healthz: DB OK, counts, security flags, worker heartbeats.
- Stats cache (2s/10s) + SSE stream for live dashboard.

## 11. Security Architecture

- CSRF via Flask-WTF (forms + AJAX header).
- Rate limit on login (5/min) with 429 + Retry-After.
- Secrets: FLASK_SECRET_KEY (64 hex) in .env; never log values.
- Fernet encryption for account passwords (key.txt). Plan for rotation by re-encryption.

## 12. Testing Strategy

- Unit: parsing, rules, counts, helpers.
- Integration (local): interception flow, stats TTL, edit/release transitions.
- Live (gated): scripts/live_check.py validates real providers using .env creds.
- CI: run stable subset first; expand as imports/fixtures stabilize.

## 13. Performance & Scaling Notes

- SQLite fine for single-node; indices keep counts/queues fast.
- Offload raw_content to filesystem if DB grows too large.
- Caching live stats reduces query load; invalidate on mutations.

## 14. From-Scratch Blueprint (Reboot Option)

Goals:
- Cleaner boundaries, typed models, easier testing, fewer globals.

Recommended Stack:
- API: FastAPI (pydantic models) or Flask with dataclasses/pydantic.
- Workers: aiosmtpd (separate process) and asyncio-based IMAP (imapclient/imaplib2) service.
- Data: SQLite with repository pattern; optional move to Postgres later.
- Settings: pydantic-settings or dynaconf for single-source config.
- UI: Next.js/React or keep Bootstrap templates; SSR or API-driven.

Module Boundaries:
- core/email (parsing, MIME build, rule engine)
- core/providers (settings detection)
- data (repositories, migrations, encryption utils)
- services/smtp (proxy server)
- services/imap (watchers)
- web/api (auth, accounts, messages, rules)
- web/ui (dashboard)

Contracts:
- No module-level DB_PATH; everything passed as dependency.
- Pure functions where feasible; narrow IO wrappers.

Testing:
- Unit on pure core; integration on services with fakes; gated live tests.

Migration Path:
- Extract portable core libs from current codebase; adapt Flask routes to new libs.
- Stand up new workers with identical APIs; cut over incrementally.

## 15. API Catalog (Current)

- Web: /, /login, /logout, /dashboard, /emails, /email/<id>, /compose, /accounts, /inbox
- API: /api/unified-stats, /api/latency-stats, /api/interception/*, /api/email/<id>/edit,
  /api/accounts, /api/accounts/<id> (GET/PUT/DELETE/test/health), /api/detect-email-settings
- Streams: /stream/stats; Health: /healthz

## 16. Configuration Keys (Quick Reference)

- FLASK_SECRET_KEY, DB_PATH, ENABLE_WATCHERS
- ENABLE_LIVE_EMAIL_TESTS, LIVE_EMAIL_ACCOUNT
- GMAIL_ADDRESS/GMAIL_PASSWORD, HOSTINGER_ADDRESS/HOSTINGER_PASSWORD

## 17. Troubleshooting Checklists

- SMTP proxy not listening: restart app; check port 8587; see logs for proxy start.
- IMAP auth failing: verify DB creds via Edit modal; username=email; SSL flags correct.
- Compose not recording: confirm INSERT on success; check exceptions around sendmail.
- UI console errors: ensure no jQuery dependency; use Bootstrap 5 APIs.

## 18. Live E2E Test (REAL Providers)

- Script: `scripts/live_interception_e2e.py`
- Purpose: Prove the full path with real Gmail/Hostinger accounts: provider SMTP send → IMAP watcher holds (not in INBOX) → edit via API → release → edited message present in INBOX.
- Safety: Requires `ENABLE_LIVE_EMAIL_TESTS=1` in environment; uses `.env` for credentials; logs no secrets.
- Prereqs:
  - App running at `http://localhost:5001`
  - Accounts for both emails exist in DB
  - `pip install requests python-dotenv`
- Run:
  ```bash
  set ENABLE_LIVE_EMAIL_TESTS=1  # or export on Unix
  python scripts/live_interception_e2e.py
  ```
- What it does:
  1) Logs in as admin to the app, updates DB creds from `.env`
  2) Starts watcher for recipient account (via `/api/accounts/<id>/monitor/start`)
  3) Sends email via provider SMTP, asserts NOT in INBOX (held), optionally in Quarantine
  4) Locates HELD mail in app DB, edits and releases via API
  5) Confirms edited subject appears in INBOX (IMAP search)

## 19. Per‑Account Monitoring Controls

- API:
  - `POST /api/accounts/<id>/monitor/start` → sets `is_active=1` and starts watcher thread if not running
  - `POST /api/accounts/<id>/monitor/stop` → sets `is_active=0` and signals watcher to stop (self-terminates)
- UI: Accounts page shows Start/Stop buttons based on `is_active`.
- Internals: Watchers poll DB and exit promptly when `is_active=0`; simple_app exposes helper start/stop functions and maintains thread/watcher registries.

---

Reference: See CLAUDE.md “Deep Dive Addendum (v2.8)” for state machines and playbooks.
