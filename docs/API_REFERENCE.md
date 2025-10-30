# Email Management Tool - API Reference

**Version**: 2.8
**Last Updated**: October 18, 2025
**Base URL**: `http://localhost:5001` (development)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Account Management](#account-management)
3. [Interception Endpoints](#interception-endpoints)
4. [Email Operations](#email-operations)
5. [Monitoring & Health](#monitoring--health)
6. [Response Formats](#response-formats)
7. [Error Codes](#error-codes)

---

## Authentication

All API endpoints require authentication via Flask session cookies.

### Login

**Endpoint:** `POST /login`

**Description:** Authenticate and receive session cookie

**Request:**
```bash
curl -i -c cookie.txt -X POST \
  -d "username=admin" \
  -d "password=admin123" \
  http://localhost:5001/login
```

**Response:**
```
HTTP/1.1 302 FOUND
Set-Cookie: session=eyJ...
Location: /dashboard
```

**Usage:**
```bash
# Save cookies to file
curl -c cookie.txt -X POST -d "username=admin" -d "password=admin123" http://localhost:5001/login

# Use cookies in subsequent requests
curl -b cookie.txt http://localhost:5001/api/interception/held
```

### Logout

**Endpoint:** `GET /logout`

**Description:** Clear session and logout

**Request:**
```bash
curl -b cookie.txt http://localhost:5001/logout
```

---

## Account Management

### List All Accounts

**Endpoint:** `GET /api/accounts`

**Description:** Retrieve all configured email accounts

**Request:**
```bash
curl -b cookie.txt http://localhost:5001/api/accounts
```

**Response:**
```json
[
  {
    "id": 1,
    "account_name": "Gmail Main",
    "email_address": "user@gmail.com",
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "is_active": 1,
    "provider_type": "gmail",
    "last_checked": "2025-10-18 14:23:45",
    "quarantine_folder": "Quarantine"
  },
  {
    "id": 2,
    "account_name": "Hostinger Main",
    "email_address": "user@corrinbox.com",
    "imap_host": "imap.hostinger.com",
    "imap_port": 993,
    "is_active": 1,
    "provider_type": "hostinger"
  }
]
```

### Start IMAP Watcher

**Endpoint:** `POST /api/accounts/<id>/monitor/start`

**Description:** Start IMAP watcher for specified account

**Request:**
```bash
curl -b cookie.txt -X POST \
  http://localhost:5001/api/accounts/1/monitor/start
```

**Response:**
```json
{
  "ok": true,
  "message": "Watcher started for account 1",
  "account_id": 1,
  "watcher_status": "starting"
}
```

### Stop IMAP Watcher

**Endpoint:** `POST /api/accounts/<id>/monitor/stop`

**Description:** Stop IMAP watcher for specified account

**Request:**
```bash
curl -b cookie.txt -X POST \
  http://localhost:5001/api/accounts/1/monitor/stop
```

**Response:**
```json
{
  "ok": true,
  "message": "Watcher stopped for account 1",
  "account_id": 1
}
```

### Restart IMAP Watcher

**Endpoint:** `POST /api/accounts/<id>/monitor/restart`

**Description:** Restart IMAP watcher (stop then start)

**Request:**
```bash
curl -b cookie.txt -X POST \
  http://localhost:5001/api/accounts/1/monitor/restart
```

---

## Interception Endpoints

### List Held Messages

**Endpoint:** `GET /api/interception/held`

**Description:** Retrieve all HELD (intercepted) messages with statistics

**Request:**
```bash
curl -b cookie.txt http://localhost:5001/api/interception/held
```

**Response:**
```json
{
  "stats": {
    "total_held": 12,
    "last_24h": 5,
    "avg_latency_ms": 247
  },
  "emails": [
    {
      "id": 42,
      "account_id": 1,
      "subject": "Urgent: Payment Required",
      "sender": "spam@example.com",
      "recipients": "user@gmail.com",
      "status": "HELD",
      "risk_score": 45,
      "keywords_matched": ["urgent", "payment"],
      "created_at": "2025-10-18 12:34:56",
      "latency_ms": 187,
      "preview": "Your account will be suspended unless..."
    }
  ]
}
```

**Query Parameters:**
- `limit` (int): Max results (default: 200)
- `account_id` (int): Filter by account

**Examples:**
```bash
# Get last 50 held messages
curl -b cookie.txt "http://localhost:5001/api/interception/held?limit=50"

# Get held messages for account 2
curl -b cookie.txt "http://localhost:5001/api/interception/held?account_id=2"
```

### Get Held Message Details

**Endpoint:** `GET /api/interception/held/<id>`

**Description:** Retrieve full details for a specific held message

**Request:**
```bash
curl -b cookie.txt http://localhost:5001/api/interception/held/42
```

**Response:**
```json
{
  "id": 42,
  "subject": "Urgent: Payment Required",
  "sender": "spam@example.com",
  "recipients": "user@gmail.com",
  "body_text": "Your account will be suspended unless you pay immediately.",
  "body_html": "<p>Your account will be suspended...</p>",
  "risk_score": 45,
  "keywords_matched": ["urgent", "payment"],
  "attachments": [
    {
      "filename": "invoice.pdf",
      "size": 256000,
      "content_type": "application/pdf"
    }
  ],
  "headers": {
    "Message-ID": "<abc123@example.com>",
    "Date": "Thu, 18 Oct 2025 12:34:00 +0000"
  },
  "original_uid": 12345,
  "original_internaldate": "2025-10-18T12:34:10",
  "raw_path": "data/inbound_raw/42.eml"
}
```


### Release Message to INBOX

**Endpoint:** `POST /api/interception/release/<id>`

**Description:** Release held message back to INBOX (with optional edits)

**Request (Release As-Is):**
```bash
curl -b cookie.txt -H "Content-Type: application/json" \
  -X POST \
  http://localhost:5001/api/interception/release/42
```

**Request (Release with Edits):**
```bash
curl -b cookie.txt -H "Content-Type: application/json" \
  -X POST \
  -d '{
    "edited_subject": "[REVIEWED] Payment Reminder",
    "edited_body": "This is a reviewed payment reminder. Please verify authenticity.",
    "strip_attachments": false
  }' \
  http://localhost:5001/api/interception/release/42
```

**Request (Strip Attachments):**
```bash
curl -b cookie.txt -H "Content-Type: application/json" \
  -X POST \
  -d '{"strip_attachments": true}' \
  http://localhost:5001/api/interception/release/42
```

**Response:**
```json
{
  "ok": true,
  "message": "Email released to INBOX",
  "email_id": 42,
  "released_to": "INBOX",
  "edited": true,
  "attachments_removed": ["invoice.pdf"],
  "edited_message_id": "<edited-abc123@example.com>"
}
```

### Discard Held Message

**Endpoint:** `POST /api/interception/discard/<id>`

**Description:** Mark message as discarded (won't be delivered)

**Request:**
```bash
curl -b cookie.txt -X POST \
  http://localhost:5001/api/interception/discard/42
```

**Response:**
```json
{
  "ok": true,
  "message": "Email discarded",
  "email_id": 42,
  "status": "DISCARDED"
}
```

---

## Email Operations

### Edit Email Content

**Endpoint:** `POST /api/email/<id>/edit`

**Description:** Save edits to subject/body for a held email

**Request:**
```bash
curl -b cookie.txt -H "Content-Type: application/json" \
  -X POST \
  -d '{
    "subject": "[REVIEWED] Updated Subject",
    "body_text": "Cleaned body text",
    "body_html": "<p>Cleaned body HTML</p>"
  }' \
  http://localhost:5001/api/email/42/edit
```

**Response:**
```json
{
  "ok": true,
  "message": "Email updated successfully",
  "email_id": 42
}
```

**Note:** Edits are saved but not released until you call `/release/<id>`

### Manually Intercept Email

**Endpoint:** `POST /api/email/<id>/intercept`

**Description:** Manually move an email to Quarantine (retroactive hold)

**Request:**
```bash
curl -b cookie.txt -X POST \
  http://localhost:5001/api/email/42/intercept
```

**Response:**
```json
{
  "ok": true,
  "message": "Email moved to Quarantine",
  "email_id": 42,
  "status": "HELD"
}
```

---

## Monitoring & Health

### Health Check

**Endpoint:** `GET /healthz`

**Description:** Get system health and recent metrics

**Request:**
```bash
curl http://localhost:5001/healthz
```

**Response:**
```json
{
  "ok": true,
  "held_count": 12,
  "released_24h": 45,
  "median_latency_ms": 187,
  "workers": [
    {
      "worker": "imap_1",
      "last_heartbeat_sec": 3.14,
      "status": "ok"
    },
    {
      "worker": "imap_2",
      "last_heartbeat_sec": 2.87,
      "status": "ok"
    }
  ],
  "timestamp": "2025-10-18T14:23:45Z"
}
```

**Caching:** Responses cached for 5 seconds

### Unified Inbox

**Endpoint:** `GET /api/inbox`

**Description:** Get combined inbox view (all messages including released)

**Request:**
```bash
curl -b cookie.txt "http://localhost:5001/api/inbox"
```

**Response:**
```json
{
  "total": 234,
  "messages": [
    {
      "id": 42,
      "subject": "Meeting Notes",
      "sender": "colleague@example.com",
      "status": "DELIVERED",
      "interception_status": "RELEASED",
      "created_at": "2025-10-18 12:00:00"
    }
  ]
}
```

**Query Parameters:**
- `q` (string): Search query (matches subject/body)
- `status` (string): Filter by status (HELD, RELEASED, DELIVERED, DISCARDED)
- `limit` (int): Max results (default: 100)
- `offset` (int): Pagination offset

**Examples:**
```bash
# Search for "invoice"
curl -b cookie.txt "http://localhost:5001/api/inbox?q=invoice"

# Get only released emails
curl -b cookie.txt "http://localhost:5001/api/inbox?status=RELEASED"

# Pagination
curl -b cookie.txt "http://localhost:5001/api/inbox?limit=50&offset=100"
```

### Metrics

**Endpoint:** `GET /api/metrics`

**Description:** Get Prometheus-style metrics

**Request:**
```bash
curl http://localhost:5001/api/metrics
```

**Response:**
```
# HELP emails_held_total Total number of emails currently held
# TYPE emails_held_total gauge
emails_held_total 12

# HELP emails_released_24h Total emails released in last 24 hours
# TYPE emails_released_24h gauge
emails_released_24h 45

# HELP interception_latency_ms_median Median interception latency
# TYPE interception_latency_ms_median gauge
interception_latency_ms_median 187
```

### SMTP Proxy Health

**Endpoint:** `GET /api/smtp-health`

**Description:** Check SMTP proxy server status

**Request:**
```bash
curl http://localhost:5001/api/smtp-health
```

**Response:**
```json
{
  "ok": true,
  "listening": true,
  "host": "127.0.0.1",
  "port": 8587,
  "uptime_seconds": 3600,
  "last_selfcheck": "2025-10-18T14:20:00Z"
}
```

### Get Watchers Status

**Endpoint:** `GET /api/watchers/overview`

**Description:** Returns IMAP watcher status and SMTP proxy health for all accounts.

**Example Request:**
```bash
curl -b cookie.txt http://localhost:5001/api/watchers/overview
```

**Example Response:**
```json
{
  "smtp": {
    "listening": true,
    "host": "127.0.0.1",
    "port": 8587,
    "last_selfcheck_ts": "2025-10-18 14:32:05"
  },
  "accounts": [
    {
      "id": 1,
      "account_name": "Gmail Primary",
      "email_address": "user@gmail.com",
      "is_active": true,
      "watcher": {
        "state": "idle",
        "last_heartbeat": "3.2s ago"
      }
    }
  ]
}
```

**States:** `idle` (IDLE mode), `polling` (fallback mode), `stopped`, `unknown`

---

## Response Formats

### Success Response

```json
{
  "ok": true,
  "message": "Operation completed successfully",
  "data": { ... }
}
```

### Error Response

```json
{
  "ok": false,
  "error": "Error message here",
  "code": "ERROR_CODE",
  "details": { ... }
}
```

### List Response

```json
{
  "total": 100,
  "limit": 50,
  "offset": 0,
  "items": [ ... ]
}
```

---

## Error Codes

| HTTP Code | Error Type | Description |
|-----------|------------|-------------|
| 200 | Success | Request completed successfully |
| 302 | Redirect | Redirect (typically to /login) |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Not logged in or session expired |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found (email ID, account ID) |
| 409 | Conflict | Resource state conflict (e.g., already released) |
| 429 | Rate Limit | Too many requests |
| 500 | Server Error | Internal server error |

### Common Error Scenarios

**401 Unauthorized:**
```bash
# Forgot to send cookies
curl http://localhost:5001/api/interception/held

# Response
{
  "ok": false,
  "error": "Authentication required",
  "code": "AUTH_REQUIRED"
}

# Fix: Include cookies
curl -b cookie.txt http://localhost:5001/api/interception/held
```

**404 Not Found:**
```bash
# Invalid email ID
curl -b cookie.txt http://localhost:5001/api/interception/held/99999

# Response
{
  "ok": false,
  "error": "Email not found",
  "code": "EMAIL_NOT_FOUND",
  "email_id": 99999
}
```

**409 Conflict:**
```bash
# Trying to release already-released email
curl -b cookie.txt -X POST http://localhost:5001/api/interception/release/42

# Response
{
  "ok": false,
  "error": "Email already released",
  "code": "ALREADY_RELEASED",
  "email_id": 42,
  "current_status": "RELEASED"
}
```

---

## Complete Workflow Example

### End-to-End Interception Test

```bash
#!/bin/bash
# Complete test workflow using API

# 1. Login
curl -c cookie.txt -X POST \
  -d "username=admin" \
  -d "password=admin123" \
  http://localhost:5001/login

# 2. Start watcher for account 1
curl -b cookie.txt -X POST \
  http://localhost:5001/api/accounts/1/monitor/start

# 3. Wait for test email to be intercepted (send manually via email client)
sleep 10

# 4. List held messages
curl -b cookie.txt http://localhost:5001/api/interception/held | jq '.emails[0]'

# 5. Get email ID from response (assume 42)
EMAIL_ID=42

# 6. Get full details
curl -b cookie.txt "http://localhost:5001/api/interception/held/${EMAIL_ID}" | jq '.'

# 7. Edit the email
curl -b cookie.txt -H "Content-Type: application/json" -X POST \
  -d '{
    "subject": "[REVIEWED] Updated Subject",
    "body_text": "Cleaned content"
  }' \
  "http://localhost:5001/api/email/${EMAIL_ID}/edit"

# 8. Release edited email
curl -b cookie.txt -H "Content-Type: application/json" -X POST \
  -d '{"edited_subject": "[REVIEWED] Final", "edited_body": "Final text"}' \
  "http://localhost:5001/api/interception/release/${EMAIL_ID}"

# 9. Verify in inbox
curl -b cookie.txt "http://localhost:5001/api/inbox?status=RELEASED" | jq '.messages[0]'

# 10. Check health metrics
curl http://localhost:5001/healthz | jq '.'
```

---

## Rate Limiting

**Limits:**
- Login: 5 attempts per minute per IP
- API endpoints: 100 requests per minute per session

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1634567890
```

**Exceeded Response:**
```json
{
  "ok": false,
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT",
  "retry_after_seconds": 45
}
```

---

## Webhook Support

**Coming Soon** - Webhook notifications for:
- New messages held
- Messages released
- Watcher state changes

---

## SDK & Libraries

**Official:**
- Python: Coming soon
- JavaScript: Coming soon

**Community:**
- See GitHub for community contributions

---

**For More Information:**
- [User Guide](USER_GUIDE.md) - Complete walkthrough
- [FAQ](FAQ.md) - Common questions
- [Troubleshooting](TROUBLESHOOTING.md) - Problem solving

---

**Last Updated**: October 18, 2025
**Version**: 2.8
