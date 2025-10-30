# Architecture Documentation

## Executive Summary (High-Level)

**Email Management Tool** is a Flask-based interception and moderation gateway that sits between inbound email (via SMTP proxy / IMAP monitoring) and the user's mailbox. It runs entirely on Windows (Python 3.13) with SQLite for persistence, and ships with two real test accounts (Gmail & Hostinger).

**System Layout**:
```
+---------------------+           +-----------------------+
| External senders    | --------> | SMTP Proxy (port 8587)|
+---------------------+           +-----------------------+
                                          |
                                          v
                               +-----------------------+
                               | SQLite (email_messages|
                               |  + encrypted creds)   |
                               +-----------------------+
                                          |
                                          v
                    +-----------------------------------------+
                    | Flask Dashboard (http://localhost:5001) |
                    |  Auth / Dashboard / Stats / Moderation  |
                    +-----------------------------------------+
```

**Core Capabilities**:
| Capability | How it works |
|------------|--------------|
| **Intercept inbound mail** | SMTP proxy accepts message, stores raw content, risk score, keywords, sets `status=PENDING`. IMAP watcher can also quarantine messages after delivery. |
| **Hold & release** | Dashboard lists HELD messages; admins can edit subject/body, release back to IMAP via APPEND, or discard (with audit logging). |
| **Editing** | `POST /api/email/<id>/edit` persists changes; diff shown in UI. |
| **Rules & auto-hold** | Moderation rules (UI + DB) can auto-mark messages for hold based on keywords/score. |
| **Compose/reply/forward** | Drafts through the web UI hit SMTP providers directly (STARTTLS or SSL depending on port). |
| **Audit trail** | audit.py logs actions (LOGIN, INTERCEPT, RELEASE, etc.) for traceability. |
| **Live stats** | stats.py caches aggregated counts (total, pending, held, released, etc.) with TTL; SSE endpoint streams updates. |

## Application Structure

**`simple_app.py`** (~918 lines) - Core application bootstrap and services; all web routes live in blueprints:

- Flask web server with authentication (Flask-Login)
- SMTP proxy server (aiosmtpd on port 8587)
- IMAP monitoring threads (one per active account)
- SQLite database layer with encrypted credentials (Fernet)
- 25+ route handlers for web interface and API (Legacy routes - being migrated to blueprints)

## Registered Blueprints (Phase 1B/1C Modularization)

**`app/routes/auth.py`** - Authentication blueprint:
- Routes: `/`, `/login`, `/logout`
- Uses: `app.models.simple_user.SimpleUser`, `app.services.audit.log_action`

**`app/routes/dashboard.py`** - Dashboard blueprint:
- Routes: `/dashboard`, `/dashboard/<tab>`, `/test-dashboard`
- Features: Account selector, stats display, recent emails, rules overview

**`app/routes/stats.py`** - Statistics API blueprint:
- Routes: `/api/stats`, `/api/unified-stats`, `/api/latency-stats`, `/stream/stats`, `/api/events` (SSE)
- Features: 2s-5s caching, SSE streaming for real-time updates

**`app/routes/moderation.py`** - Moderation blueprint:
- Routes: `/rules`
- Features: Admin-only access, rule management interface

**`app/routes/interception.py`** - Interception blueprint (Phase 1A):
- Email hold/release/discard operations
- Email editing with diff tracking
- Attachment stripping functionality
- Health and diagnostic endpoints

**`app/routes/emails.py`** - Emails blueprint (Phase 1C):
- Routes: `/emails`, `/email/<id>`, `/email/<id>/action`, `/email/<id>/full`, `/api/fetch-emails`, `/api/email/<id>/reply-forward`, `/api/email/<id>/download`
- Features: Queue, viewer, reply/forward helpers, .eml download, IMAP UID fetch

**`app/routes/accounts.py`** - Accounts blueprint (Phase 1C):
- Routes: `/accounts`, `/accounts/add`, `/api/accounts`, `/api/accounts/<id>` (GET/PUT/DELETE), `/api/accounts/<id>/health`, `/api/accounts/<id>/test`, `/api/accounts/export`, `/api/test-connection/<type>`, `/api/accounts/<id>/monitor/start`, `/api/accounts/<id>/monitor/stop`, `/diagnostics[/<id>]`
- Features: Smart detection API, connectivity tests, export, diagnostics redirect, per‑account IMAP watcher control (start/stop)

**`app/routes/inbox.py`** - Inbox blueprint (Phase 1C):
- Route: `/inbox`
- Features: Unified inbox view by account

**`app/routes/compose.py`** - Compose blueprint (Phase 1C):
- Routes: `/compose` (GET, POST)
- Features: Email composition and sending via SMTP
- Supports both form and JSON API requests
- SMTP connection with SSL/STARTTLS support

## Component Layer

**`app/models/simple_user.py`** - Lightweight User model:
- SimpleUser class for Flask-Login integration
- Replaces inline User class in simple_app.py
- Independent of SQLAlchemy models

**`app/services/audit.py`** - Audit logging service:
- log_action() - Best-effort audit logging
- get_recent_logs() - Retrieve audit history
- SQLite-based with silent failure pattern

**`app/utils/`**:
- `db.py` - Dependency-injectable database layer with row_factory for dict-like results
  - `get_db(db_path=None, conn=None)` - Returns context manager for DB access
  - `fetch_counts(conn=None)` - Single-pass aggregate query for all dashboard stats
  - Enforces WAL mode, foreign keys, busy_timeout
- `crypto.py` - Fernet encryption for email credentials

## Threading Model

- **Main Thread**: Flask web server (port 5001)
- **SMTP Thread**: Email interception proxy (port 8587, daemon)
- **IMAP Threads**: Per-account monitoring (daemon, auto-reconnect)
  - Controlled by `ENABLE_WATCHERS` env var (default: enabled)
  - Started via `app/workers/imap_startup.py::start_imap_watchers()`
  - All threads share SQLite DB; WAL + busy_timeout mitigate contention

## Email Processing Pipeline

```
1. SMTP Interception (port 8587)
   ↓
2. Risk Assessment & Storage (status=PENDING)
   ↓
3. Dashboard Review & Editing
   ↓
4. Approval/Rejection Decision
   ↓
5. SMTP Relay to Destination
   ↓
6. Audit Trail & Logging
```

## IMAP Interception Flow (Current Implementation)

```
1. IMAP IDLE on INBOX → detect new message
   ↓
2. MOVE to Quarantine folder (or COPY+DELETE fallback)
   ↓
3. Store in database (interception_status='HELD')
   ↓
4. UI Review → Edit subject/body if needed
   ↓
5. Release: APPEND back to IMAP via APPEND (or discard)
```

## Related Documentation

- **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - Database design and performance
- **[SECURITY.md](SECURITY.md)** - Security implementation details
- **[HYBRID_IMAP_STRATEGY.md](HYBRID_IMAP_STRATEGY.md)** - IMAP watcher implementation
- **[TECHNICAL_DEEP_DIVE.md](TECHNICAL_DEEP_DIVE.md)** - Deep technical reference
