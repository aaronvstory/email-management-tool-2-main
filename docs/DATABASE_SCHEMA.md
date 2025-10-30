# Database Schema Documentation

## Critical Tables

### `email_accounts` - Encrypted IMAP/SMTP credentials per account

**Fields**:
- `id` (INTEGER PRIMARY KEY)
- `email_address` (TEXT UNIQUE)
- `imap_host`, `imap_port`, `imap_username`, `imap_password` (encrypted), `imap_use_ssl`
- `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password` (encrypted), `smtp_use_ssl`
- `is_active` (INTEGER) - Enable/disable account
- `created_at` (TEXT)

**Note**: `sieve_*` fields deprecated but kept for backward compatibility

### `email_messages` - All intercepted/moderated emails with audit trail

**Key fields**:
- `id` (INTEGER PRIMARY KEY)
- `message_id` (TEXT) - Email Message-ID header
- `account_id` (INTEGER FOREIGN KEY)
- `sender`, `recipients` (TEXT)
- `subject`, `body_text`, `body_html` (TEXT)
- `raw_content` (TEXT) - Full MIME message
- `has_attachments` (INTEGER)
- `direction` (TEXT) - 'inbound' or 'outbound'

**Status fields**:
- `status` (TEXT) - PENDING/APPROVED/REJECTED/SENT
- `interception_status` (TEXT) - HELD/RELEASED/DISCARDED

**Tracking fields**:
- `latency_ms` (INTEGER) - Processing latency
- `risk_score` (REAL) - Calculated risk (0.0-1.0)
- `keywords_matched` (TEXT) - Matched moderation keywords
- `review_notes` (TEXT) - Admin notes
- `approved_by` (TEXT) - Admin username

**Timestamps**:
- `created_at` (TEXT) - When intercepted
- `processed_at` (TEXT) - When reviewed
- `action_taken_at` (TEXT) - When released/discarded

**IMAP-specific fields**:
- `original_uid` (INTEGER) - IMAP UID in Quarantine
- `server_timestamp` (TEXT) - INTERNALDATE from server

### `users` - Authentication with bcrypt password hashing

**Fields**:
- `id` (INTEGER PRIMARY KEY)
- `username` (TEXT UNIQUE)
- `password_hash` (TEXT) - bcrypt hashed
- `role` (TEXT) - 'admin' or 'user'
- `created_at` (TEXT)

### `moderation_rules` - Keyword-based interception rules

**Fields**:
- `id` (INTEGER PRIMARY KEY)
- `name` (TEXT)
- `keywords` (TEXT) - Comma-separated list
- `action` (TEXT) - 'hold', 'flag', or 'allow'
- `priority` (INTEGER) - Rule execution order
- `is_active` (INTEGER)
- `created_at` (TEXT)

### `audit_log` - Action audit trail

**Fields**:
- `id` (INTEGER PRIMARY KEY)
- `timestamp` (TEXT)
- `username` (TEXT)
- `action` (TEXT) - LOGIN, INTERCEPT, RELEASE, DISCARD, etc.
- `details` (TEXT) - JSON or description
- `ip_address` (TEXT)

## Performance Indices (Phase 0 DB Hardening)

**Optimized indices added for fast filtering and aggregation:**

```sql
CREATE INDEX idx_email_messages_interception_status 
ON email_messages(interception_status);

CREATE INDEX idx_email_messages_status 
ON email_messages(status);

CREATE INDEX idx_email_messages_account_status 
ON email_messages(account_id, status);

CREATE INDEX idx_email_messages_account_interception 
ON email_messages(account_id, interception_status);

CREATE INDEX idx_email_messages_direction_status 
ON email_messages(direction, interception_status);

CREATE INDEX idx_email_messages_original_uid 
ON email_messages(original_uid);
```

**Query optimizer benefits**:
- Dashboard COUNT queries use covering indices (no table scan)
- Account-specific queries leverage composite indices
- WAL mode enabled for concurrent read/write performance

**Migration**: Run `python scripts/migrations/20251001_add_interception_indices.py`

**Verification**: Run `python scripts/verify_indices.py` to see query plans

## Database Configuration

**WAL Mode** (Write-Ahead Logging):
- Enabled via `PRAGMA journal_mode=WAL`
- Allows concurrent reads during writes
- Improves performance for multi-threaded access

**Foreign Keys**:
- Enabled via `PRAGMA foreign_keys=ON`
- Enforces referential integrity
- Cascading deletes configured where appropriate

**Busy Timeout**:
- Set to 5000ms via `PRAGMA busy_timeout=5000`
- Prevents "database is locked" errors
- Automatic retry on contention

## Database Access Pattern

**CRITICAL**: Always use `row_factory` for dict-like access:

```python
from app.utils.db import get_db

with get_db() as conn:
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM email_messages WHERE status=?", ('PENDING',)).fetchall()
    for row in rows:
        print(row['subject'])  # Dict access, not row[2]
```

**Dependency Injection Support**:

```python
from app.utils.db import get_db, fetch_counts

# Use default database
with get_db() as conn:
    counts = fetch_counts(conn)

# Use custom database (for testing)
with get_db(db_path='test.db') as conn:
    counts = fetch_counts(conn)

# Inject existing connection
conn = sqlite3.connect(':memory:')
counts = fetch_counts(conn=conn)
```

## Common Queries

**Dashboard Stats** (Single-pass aggregate):
```python
from app.utils.db import fetch_counts

counts = fetch_counts()
# Returns: {
#   'total': 150,
#   'pending': 10,
#   'held': 5,
#   'released': 100,
#   'discarded': 15,
#   'sent': 20
# }
```

**Account-Specific Filtering**:
```sql
SELECT * FROM email_messages 
WHERE account_id = ? 
  AND interception_status = 'HELD'
ORDER BY created_at DESC;
```

**Risk-Based Filtering**:
```sql
SELECT * FROM email_messages 
WHERE risk_score >= 0.7
  AND status = 'PENDING'
ORDER BY risk_score DESC;
```

## Migration Strategy

**Always check for column existence first**:

```python
cursor.execute('PRAGMA table_info(email_messages)')
columns = [col[1] for col in cursor.fetchall()]
if 'new_field' not in columns:
    cursor.execute('ALTER TABLE email_messages ADD COLUMN new_field TEXT')
    conn.commit()
```

## Related Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture overview
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development workflow and patterns
- **[TESTING.md](TESTING.md)** - Test strategy and coverage
