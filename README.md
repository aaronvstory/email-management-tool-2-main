# Email Management Tool

A comprehensive email moderation system for Windows that intercepts, holds, and allows review of emails before sending. No Docker required - runs natively on Windows with Python.

## 🚀 Features

- **SMTP Proxy Server**: Intercepts outgoing emails on port 8587
- **Web Dashboard**: Modern Bootstrap 5.3 interface for email management
- **Email Moderation**: Hold, review, edit, approve, or reject emails
- **Rule Engine**: Configurable rules for automatic email filtering
- **Audit Trail**: Complete logging of all actions
- **User Management**: Role-based access control with secure authentication
- **Real-time Updates**: Dashboard with live statistics and charts
- **Windows Service**: Can run as a Windows service for production deployment

## 🔐 Security Note

**Credential Storage**: Email account passwords are encrypted at rest using Fernet symmetric encryption. The encryption key (`key.txt`) is automatically generated and **must NOT be committed to version control** (already in .gitignore).

**⚠️ Important**: Never commit `key.txt`, `.env`, or any files containing credentials. All sensitive data is git-ignored by default.

## 📚 Documentation

**Getting Started**:
- **[User Guide](docs/USER_GUIDE.md)** - Complete step-by-step workflows for email interception, editing, and release
- **[API Reference](docs/API_REFERENCE.md)** - REST API documentation with production-ready cURL examples
- **[FAQ](docs/FAQ.md)** - Frequently asked questions about watchers, IDLE/polling modes, and workflows
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues, gotchas, and debugging guides

**Architecture & Technical**:
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and component interactions
- **[Database Schema](docs/DATABASE_SCHEMA.md)** - Complete database design with indices and relationships
- **[IMAP Strategy](docs/HYBRID_IMAP_STRATEGY.md)** - Hybrid IDLE+polling implementation details
- **[Security Guide](docs/SECURITY.md)** - CSRF protection, rate limiting, and hardening

**Development**:
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflow and best practices
- **[Testing Guide](docs/TESTING.md)** - Test strategy and coverage guidelines
- **[Style Guide](docs/STYLEGUIDE.md)** - UI/UX standards (mandatory for UI changes)
- **[Test Scripts](scripts/README.md)** - Automated testing utilities and examples

## 📋 Requirements

- Windows 10/11 or Windows Server 2016+
- Python 3.9 or higher
- 100 MB free disk space
- Administrator privileges (for service installation only)

## 🔧 Quick Start

### 1. Initial Setup

```batch
# Run the setup script
setup.bat
```

This will:

- Check Python installation
- Create virtual environment
- Install all dependencies
- Create necessary directories
- Generate default configuration

### 2. Configure Email Settings

Edit `config\config.ini` with your email server details:

```ini
[SMTP_RELAY]
relay_host = your-smtp-server.com
relay_port = 587
use_tls = true
username = your-email@domain.com
password = your-password
```

### 3. Start the Application

```batch
# Run the application
start.bat
```

The application will start with:

- SMTP Proxy on `localhost:8587`
- Web Dashboard on `http://localhost:5001`
- Default login: `admin` / `admin123`

## 🧪 How to Run Locally

For development and testing:

```bash
# 1. Start the application
python simple_app.py

# 2. Access the web dashboard
http://localhost:5001

# 3. Login with default credentials
Username: admin
Password: admin123

# 4. If port conflicts occur, restart cleanly
python cleanup_and_start.py
```

### Using the Professional Launcher

For a cleaner startup experience:

```batch
# Professional menu-driven launcher
EmailManager.bat

# Quick launch
launch.bat
```

## ✅ Basic Test Checklist

After starting the application, verify core functionality:

1. **Login & Dashboard**
   - Navigate to http://localhost:5001
   - Login with `admin` / `admin123`
   - Verify dashboard loads with statistics

2. **Accounts Management** (`/accounts`)
   - Click "Reset Circuit" on any account → Verify success toast
   - Click "Test" → Verify SMTP/IMAP connection test passes
   - Click "Start" → Verify watcher starts (header shows "WATCHERS: 1")

3. **Email Management** (`/emails-unified`)
   - Verify email list loads
   - Check action buttons are properly spaced (Edit, Release, Discard)
   - Click any email to view details

4. **Compose** (`/compose`)
   - Verify textarea has proper height (~16rem)
   - Test sending an email through SMTP proxy

5. **API Health Checks**
   ```bash
   # Health check
   curl http://localhost:5001/healthz

   # Should return: {"ok": true, "db": "ok"}
   ```

For detailed testing procedures, see [docs/USER_GUIDE.md](docs/USER_GUIDE.md) and [.taskmaster/TASK_PROGRESS.md](.taskmaster/TASK_PROGRESS.md).

## 💻 Management Options

### Using Batch Scripts

```batch
# Initial setup
setup.bat

# Start application
start.bat

# Stop application (Ctrl+C in the console)
```

### Using PowerShell (Advanced)

```powershell
# View status
.\manage.ps1 status

# Start application
.\manage.ps1 start

# Stop application
.\manage.ps1 stop

# Restart application
.\manage.ps1 restart

# Create backup
.\manage.ps1 backup

# Restore from backup
.\manage.ps1 restore

# View logs
.\manage.ps1 logs

# Edit configuration
.\manage.ps1 config
```

### Windows Service Installation (Optional)

For production deployment, install as a Windows service:

```powershell
# Run PowerShell as Administrator

# Install service
.\manage.ps1 install

# Uninstall service
.\manage.ps1 uninstall
```

## 📁 Project Structure

```
Email Management Tool/
├── app/                    # Application modules
│   ├── models/            # Data models (unused - uses raw sqlite3)
│   ├── routes/            # Flask routes
│   └── services/          # Business logic
├── config/                # Configuration files
│   └── config.ini         # Main configuration
├── data/                  # SQLite database
├── logs/                  # Application logs
├── templates/             # HTML templates
├── static/                # CSS, JS, images
├── venv/                  # Virtual environment
├── backups/               # Database backups
├── setup.bat              # Windows setup script
├── start.bat              # Application launcher
├── manage.ps1             # PowerShell management
├── simple_app.py          # Main application file
└── requirements.txt       # Python dependencies
```

## 🔐 Security Features

- Password hashing with bcrypt
- Session management with Flask-Login
- CSRF protection
- SQL injection prevention via parameterized queries
- Rate limiting on login attempts
- Secure session cookies
- Audit logging of all actions

## 📧 Email Configuration

### Configure Email Client

Set your email client (Outlook, Thunderbird, etc.) to use:

- **SMTP Server**: `localhost` or `127.0.0.1`
- **Port**: `8587`
- **Security**: None (proxy handles encryption to relay)
- **Authentication**: Not required for proxy

### Moderation Rules

Default rules check for:

- Keywords (invoice, payment, urgent)
- Attachments (PDF, DOC, XLS)
- External recipients
- Custom regex patterns

Edit rules in the web dashboard under Settings → Moderation Rules.

## 🎯 Dashboard Features

- **Statistics Overview**: Total, pending, approved, rejected emails
- **Real-time Charts**: Email flow visualization
- **Email Queue**: List of pending emails with filtering
- **Email Details**: View full email content and headers
- **Email Editor**: Modify email content before sending
- **Audit Logs**: Track all system actions
- **User Management**: Add/edit/delete users
- **Settings**: Configure system parameters

## 🛠️ Troubleshooting

### Application Won't Start

1. Ensure Python 3.9+ is installed: `python --version`
2. Run setup.bat to install dependencies
3. Check if ports 5001 and 8587 are available
4. Review logs in `logs\email_moderation.log`

### Cannot Access Dashboard

1. Check firewall settings for port 5001
2. Try http://127.0.0.1:5001 instead of localhost
3. Ensure application is running (check with `manage.ps1 status`)

### Emails Not Being Intercepted

1. Verify email client SMTP settings point to localhost:8587
2. Check moderation rules are active
3. Review SMTP proxy logs for connection attempts

### Database Issues

1. Create backup: `manage.ps1 backup`
2. Check database file exists in `data\`
3. Verify write permissions on data directory

## 📊 Performance

- Handles 1000+ emails per hour
- SQLite database supports up to 100GB
- Web dashboard supports 50+ concurrent users
- SMTP proxy processes emails in <100ms
- Memory usage: ~50-100MB typical

## 🔄 Backup and Recovery

### Automatic Backups

Configure in `config\config.ini`:

```ini
[BACKUP]
auto_backup = true
backup_interval = daily
backup_retention = 30
```

### Manual Backup

```powershell
# Create backup
.\manage.ps1 backup

# Restore from backup
.\manage.ps1 restore
```

## 📝 Logging

Logs are stored in `logs\email_moderation.log` with automatic rotation:

- Max file size: 10MB
- Backup count: 5
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

View recent logs:

```powershell
.\manage.ps1 logs
```

## 🚦 Monitoring

### Health & Interception Metrics

```
GET /healthz
```

Returns JSON including held inbound count, releases in last 24h, median interception latency, and worker heartbeats (when active).

Example:

```json
{
  "ok": true,
  "held_count": 2,
  "released_24h": 14,
  "median_latency_ms": 187,
  "workers": [
    { "worker": "acct-1", "last_heartbeat_sec": 3.14, "status": "ok" }
  ],
  "timestamp": "2025-09-30T12:10:05Z"
}
```

---

## ✂️ Inbound Interception & Release Flow

Goal: Intercept inbound messages (hold-before-read) using only mailbox credentials (no MX / DNS changes) with sub‑second dwell.

1. Rapid IMAP worker detects new UID via UIDNEXT delta or IDLE.
2. Message is immediately COPIED into the local quarantine representation (DB row) and flagged \Deleted + EXPUNGE in source mailbox (kept safely in local raw file for review).
3. Raw RFC822 bytes are fetched asynchronously and stored under `data/inbound_raw/<id>.eml` (path recorded as `raw_path`).
4. Dashboard (Held view) lists HELD messages with preview snippet extracted from the raw file.
5. Reviewer optionally edits subject and/or body via JSON edit endpoint.
6. Release endpoint reconstructs (edited) MIME and APPENDs it back to the original mailbox (INBOX or specified folder) preserving (approximate) original internal date when available.
7. Message row marked `RELEASED`; latency persisted (capture to hold time) for metrics.

### Key Columns

| Column              | Purpose                                            |
| ------------------- | -------------------------------------------------- | -------- | --------- |
| direction           | 'inbound' for intercepted path                     |
| interception_status | HELD                                               | RELEASED | DISCARDED |
| raw_path            | Filesystem path to stored RFC822                   |
| latency_ms          | Milliseconds from detection to DB record persisted |
| edited_message_id   | Message-ID of released (possibly edited) version   |

### Core Endpoints

| Method | Endpoint                       | Description                                                  |
| ------ | ------------------------------ | ------------------------------------------------------------ |
| GET    | /api/interception/held         | List last 200 HELD inbound messages + stats                  |
| GET    | /api/interception/held/<id>    | Detailed JSON with preview snippet                           |
| POST   | /api/email/<id>/edit           | Edit subject/body_text/body_html (HELD only)                 |
| POST   | /api/interception/release/<id> | Release (optionally with JSON {edited_subject, edited_body}) |
| POST   | /api/interception/discard/<id> | Discard HELD message                                         |
| GET    | /api/inbox                     | Unified inbox view (filters: status, q)                      |
| GET    | /healthz                       | Health & metrics (5s cache)                                  |

### Edit Before Release (Client Flow)

1. GET `/api/interception/held` → choose message id.
2. (Optional) GET `/api/interception/held/<id>` for full preview.
3. POST `/api/email/<id>/edit` JSON:

```json
{ "subject": "Revised Subject", "body_text": "Cleaned body" }
```

4. POST `/api/interception/release/<id>` JSON (optional overrides during release):

```json
{ "edited_subject": "Revised Subject FINAL", "edited_body": "Final text" }
```

5. UI refresh or polling picks up `interception_status=RELEASED`.

### Example Release JSON Response

```json
{ "ok": true, "released_to": "INBOX" }
```

---

## 🧪 Testing Strategy

| Test File                                    | Purpose                                   |
| -------------------------------------------- | ----------------------------------------- |
| tests/interception/test_rapid_copy_purge.py  | Worker class import & instantiation       |
| tests/interception/test_release_append.py    | MIME build & append helper structure      |
| tests/interception/test_live_integration.py  | Optional live IMAP roundtrip (env gated)  |
| tests/interception/test_edit_release_flow.py | DB-level edit → release E2E (IMAP mocked) |

Run all interception tests:

```powershell
pytest -q tests/interception
```

---

## 📂 Archived Historical Docs

Legacy deep-dive and diagnostic markdown files were tagged with `ARCHIVED_AT` and may be moved under `archive/root_docs_20250930/` to declutter the root. The main `README.md` now serves as the authoritative operational guide.

---

## 🔌 Endpoint Quick Reference

| Area    | Endpoint                            | Notes                                  |
| ------- | ----------------------------------- | -------------------------------------- |
| Health  | GET /healthz                        | Cached 5s, latency + worker heartbeats |
| Held    | GET /api/interception/held          | Stats + list                           |
| Held    | GET /api/interception/held/<id>     | Detailed + snippet                     |
| Edit    | POST /api/email/<id>/edit           | Subject/body updates                   |
| Release | POST /api/interception/release/<id> | Append back to mailbox                 |
| Discard | POST /api/interception/discard/<id> | Mark discarded                         |
| Inbox   | GET /api/inbox                      | Unified + search & status filter       |

---

## 🗺️ Future Enhancements (Roadmap)

| Item                  | Description                                          |
| --------------------- | ---------------------------------------------------- |
| Attachment Scrubbing  | Strip or replace risky attachments before release    |
| DKIM Re-Sign          | Optionally re-sign edited outbound releases          |
| Rate / Burst Controls | Throttle release operations per account              |
| Multi-Worker Registry | Persist worker heartbeats for distributed deployment |
| UI Inline Diff        | Present diff of edits before release                 |

Returns:

```json
{
  "status": "healthy",
  "smtp_proxy": "running",
  "database": "connected",
  "uptime": "2h 15m"
}
```

### Metrics Endpoint

```
GET http://localhost:5001/api/metrics
```

## 🤝 API Integration

RESTful API available for integration:

```python
# Example: Approve email via API
import requests

response = requests.post(
    'http://localhost:5001/api/emails/approve',
    json={'message_id': 'msg-123'},
    headers={'Authorization': 'Bearer YOUR_API_TOKEN'}
)
```

## 📖 Development

### Run in Development Mode

```python
# Set debug mode in config.ini
[WEB_INTERFACE]
debug = true

# Run with auto-reload
python simple_app.py
```

### Run Tests

```batch
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/
```

## 📄 License

MIT License - See LICENSE file for details

## 🆘 Support

- GitHub Issues: [Report bugs or request features]
- Documentation: See `/docs` folder
- Email: support@yourdomain.com

## 🔄 Version History

- **v1.0.0** (2025-08-30): Initial release with full Windows support
  - Native Windows deployment (no Docker required)
  - PowerShell management scripts
  - Windows service support
  - Automatic setup and configuration

## ⚡ Quick Commands Reference

| Action          | Command                                  |
| --------------- | ---------------------------------------- |
| Setup           | `setup.bat`                              |
| Start           | `start.bat`                              |
| Stop            | `Ctrl+C` in console                      |
| Status          | `powershell .\manage.ps1 status`         |
| Backup          | `powershell .\manage.ps1 backup`         |
| View Logs       | `powershell .\manage.ps1 logs`           |
| Install Service | `powershell -Admin .\manage.ps1 install` |

---

**Built with ❤️ for Windows** - No Docker, No Containers, Just Pure Python!
