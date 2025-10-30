# API Documentation

## Core Routes (simple_app.py)

```
GET  /                          # Login page
GET  /dashboard                 # Main dashboard with tabs
GET  /emails                    # Email queue (with status filter)
GET  /inbox                     # Inbox viewer
GET  /compose                   # Email composer
POST /compose                   # Send new email
GET  /accounts                  # Account management
POST /accounts/add              # Add new account (supports auto-detection)
POST /email/<id>/action         # Approve/reject email
```

## Registered Blueprints (Phase 1B/1C Modularization)

### Authentication Blueprint (`app/routes/auth.py`)
- Routes: `/`, `/login`, `/logout`
- Uses: `app.models.simple_user.SimpleUser`, `app.services.audit.log_action`

### Dashboard Blueprint (`app/routes/dashboard.py`)
- Routes: `/dashboard`, `/dashboard/<tab>`, `/test-dashboard`
- Features: Account selector, stats display, recent emails, rules overview

### Statistics API Blueprint (`app/routes/stats.py`)
- Routes: `/api/stats`, `/api/unified-stats`, `/api/latency-stats`, `/stream/stats`, `/api/events` (SSE)
- Features: 2s-5s caching, SSE streaming for real-time updates

### Moderation Blueprint (`app/routes/moderation.py`)
- Routes: `/rules`
- Features: Admin-only access, rule management interface

### Interception Blueprint (`app/routes/interception.py`)
- Email hold/release/discard operations
- Email editing with diff tracking
- Attachment stripping functionality
- Health and diagnostic endpoints

### Emails Blueprint (`app/routes/emails.py`)
- Routes: `/emails`, `/email/<id>`, `/email/<id>/action`, `/email/<id>/full`, `/api/fetch-emails`, `/api/email/<id>/reply-forward`, `/api/email/<id>/download`
- Features: Queue, viewer, reply/forward helpers, .eml download, IMAP UID fetch

### Accounts Blueprint (`app/routes/accounts.py`)
- Routes: `/accounts`, `/accounts/add`, `/api/accounts`, `/api/accounts/<id>` (GET/PUT/DELETE), `/api/accounts/<id>/health`, `/api/accounts/<id>/test`, `/api/accounts/export`, `/api/test-connection/<type>`, `/diagnostics[/<id>]`
- Features: Smart detection API, connectivity tests, export, diagnostics redirect

### Inbox Blueprint (`app/routes/inbox.py`)
- Route: `/inbox`
- Features: Unified inbox view by account

### Compose Blueprint (`app/routes/compose.py`)
- Routes: `/compose` (GET, POST)
- Features: Email composition and sending via SMTP
- Supports both form and JSON API requests
- SMTP connection with SSL/STARTTLS support

## Smart Detection API

```
POST /api/detect-email-settings  # Auto-detect SMTP/IMAP settings
```

### Request
```json
{
  "email": "user@gmail.com"
}
```

### Response
```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_use_ssl": false,
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "imap_use_ssl": true
}
```

## Interception API (app/routes/interception.py)

```
GET  /api/interception/held                    # List HELD messages
GET  /api/interception/held/<id>?include_diff=1 # Detail with diff
POST /api/interception/release/<id>            # Release to inbox
POST /api/interception/discard/<id>            # Discard message
POST /api/email/<id>/edit                      # Save email edits
GET  /api/unified-stats                        # Dashboard stats (5s cache)
GET  /api/latency-stats                        # Percentile latency (10s cache)
GET  /stream/stats                             # SSE stream for live updates
GET  /healthz                                  # Health check
```

## Email Editing & Release API

### Fetch Email for Editing
```
GET /email/<id>/edit
```
Returns JSON with email details for editing modal.

### Save Email Changes
```
POST /api/email/<id>/edit
```

#### Request Body
```json
{
  "subject": "Updated Subject",
  "body_text": "Updated body content"
}
```

#### Response
```json
{
  "success": true,
  "message": "Email updated successfully"
}
```

### Release Email to Inbox
```
POST /api/interception/release/<id>
```
Rebuilds MIME with edited content and APPENDs to INBOX.

### Discard Email
```
POST /api/interception/discard/<id>
```
Marks email as discarded with audit trail.

## Account Management API

### List All Accounts
```
GET /api/accounts
```

### Get Account Details
```
GET /api/accounts/<id>
```

### Update Account
```
PUT /api/accounts/<id>
```

#### Request Body
```json
{
  "email": "user@example.com",
  "smtp_host": "smtp.example.com",
  "smtp_port": 587,
  "smtp_use_ssl": false,
  "imap_host": "imap.example.com",
  "imap_port": 993,
  "imap_use_ssl": true,
  "username": "user@example.com",
  "password": "app-password"
}
```

### Delete Account
```
DELETE /api/accounts/<id>
```

### Test Account Connection
```
GET /api/accounts/<id>/test
```
Tests both SMTP and IMAP connectivity.

### Health Check
```
GET /api/accounts/<id>/health
```
Returns account health status.

### Export Accounts
```
GET /api/accounts/export
```
Downloads accounts as CSV (passwords excluded).

## Statistics API

### Dashboard Statistics
```
GET /api/unified-stats
```

#### Response
```json
{
  "total": 100,
  "pending": 10,
  "held": 5,
  "released": 80,
  "rejected": 5,
  "sent": 75,
  "received": 25
}
```

### Latency Statistics
```
GET /api/latency-stats
```

#### Response
```json
{
  "median_ms": 123,
  "p95_ms": 456,
  "p99_ms": 789,
  "count": 100
}
```

## Server-Sent Events (SSE)

### Real-time Statistics Stream
```
GET /stream/stats
```

Streams real-time updates for dashboard statistics.

### Event Stream
```
GET /api/events
```

General event stream for real-time updates.

## Health Check Endpoint

```
GET /healthz
```

### Response
```json
{
  "ok": true,
  "db": "ok",
  "held_count": 0,
  "released_24h": 0,
  "median_latency_ms": null,
  "workers": [],
  "timestamp": "2025-10-10T12:00:00Z",
  "security": {
    "secret_key_configured": true,
    "secret_key_prefix": "a1b2c3d4",
    "csrf_enabled": true,
    "csrf_time_limit": null,
    "session_cookie_secure": false,
    "session_cookie_httponly": true
  }
}
```

### Response Fields
- `ok` - Overall health status (true/false)
- `db` - Database connectivity ("ok" or null if error)
- `held_count` - Number of currently held messages
- `released_24h` - Messages released in last 24 hours
- `median_latency_ms` - Median interception latency (milliseconds)
- `workers` - IMAP worker heartbeat status
- `timestamp` - ISO 8601 UTC timestamp
- `security` - Security configuration status:
  - `secret_key_configured` - Is SECRET_KEY strong (≥32 chars)?
  - `secret_key_prefix` - First 8 chars of SECRET_KEY for verification
  - `csrf_enabled` - CSRF protection status
  - `csrf_time_limit` - Token expiry (null = no expiry)
  - `session_cookie_secure` - Secure flag status
  - `session_cookie_httponly` - HttpOnly flag status

## Email Processing Pipeline

### Email Interception

#### SMTP Proxy (Port 8587)
```python
class EmailModerationHandler:
    async def handle_DATA(self, server, session, envelope):
        # 1. Parse email
        # 2. Calculate risk score
        # 3. Store as PENDING in database
        # 4. Return 250 Message accepted
```

#### IMAP Monitoring
- IDLE command for instant notification
- MOVE to Quarantine folder on detection
- Store raw `.eml` file for audit (raw_path)
- Record latency_ms for performance tracking
- Extracts INTERNALDATE (server timestamp) and original_uid from IMAP

### Interception Flow

#### SMTP Path
1. `EmailModerationHandler.handle_DATA` stores message
2. Populates risk metadata
3. Returns 250 (message accepted)
4. Optionally triggers rule-based auto-holds

#### IMAP Path
1. Threads select INBOX, IDLE
2. Fetch new UIDs
3. Move to Quarantine
4. Update database: `interception_status='HELD'`
5. Capture `original_uid`

#### Release Flow
1. `app/routes/interception.py::release_email` rebuilds MIME
2. Optionally uses edited body
3. APPENDs to INBOX
4. Sets `interception_status='RELEASED'`
5. Sets `status='DELIVERED'`

#### Manual Intercept
```
POST /api/email/<id>/intercept
```
- Re-opens already inboxed messages
- Moves from inbox back to hold
- Computes latency
- Logs action

## Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 302 | Redirect (login required) |
| 400 | Bad Request (CSRF token missing) |
| 401 | Unauthorized |
| 404 | Not Found |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |

## Authentication

The API uses Flask-Login for session management. Most endpoints require authentication except:
- `/` (login page)
- `/login` (login endpoint)
- `/healthz` (health check)

For authenticated requests from external clients, ensure:
1. Login via `/login` with CSRF token
2. Include session cookie in subsequent requests
3. Include CSRF token for state-changing operations

## CSRF Protection

All POST/PUT/DELETE requests require a CSRF token:

### For Forms
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

### For AJAX Requests
```javascript
headers: {
  'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
}
```

### Exempt Routes
- `/stream/stats` (SSE)
- `/api/events` (SSE)

## Rate Limiting

Authentication endpoints are rate-limited:
- `/login`: 5 attempts per minute per IP
- Returns 429 with `Retry-After` header when exceeded

## Error Handling

All API endpoints return consistent error responses:

```json
{
  "error": true,
  "message": "Error description",
  "details": {}  // Optional additional context
}
```