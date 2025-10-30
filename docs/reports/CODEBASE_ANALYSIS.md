# Comprehensive Codebase Analysis
# Email Management Tool - Full Architecture & Implementation Review

**Generated**: October 18, 2025  
**Version**: 2.8  
**Status**: ✅ Production-Ready (138/138 tests passing, 36% coverage)

---

## 1. Project Overview

### 1.1 Project Type & Purpose
**Email Management Tool** is a **local email interception and moderation gateway** built as a Flask web application. It operates as middleware between email clients and mail servers, providing hold-before-send and hold-before-read capabilities for email security and compliance.

### 1.2 Tech Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Runtime** | Python | 3.9+ (tested on 3.13) | Core language |
| **Web Framework** | Flask | 3.0.0+ | HTTP server & routing |
| **Authentication** | Flask-Login | 0.6.3+ | Session management |
| **Database** | SQLite 3 | Native | Persistent storage (WAL mode) |
| **SMTP Proxy** | aiosmtpd | 1.4.4+ | Outbound interception |
| **IMAP Client** | imapclient | 3.0.0+ | Inbound monitoring |
| **Encryption** | cryptography (Fernet) | 41.0.7+ | Credential encryption |
| **Testing** | pytest | 7.4.3+ | Test framework |
| **Frontend** | Bootstrap 5.3 | CDN | UI framework |
| **Security** | Flask-WTF (CSRF) | 1.2.1+ | Token protection |
| **Rate Limiting** | Flask-Limiter | 3.5.0+ | DoS prevention |

### 1.3 Architecture Pattern
**Modular Blueprint Architecture** with service layer separation:
- **MVC-inspired structure**: Routes (controllers) → Services → Models → Database
- **Blueprint-based routing**: 13 separate route blueprints for modularity
- **Daemon thread architecture**: Background workers for SMTP/IMAP monitoring
- **Event-driven updates**: Server-Sent Events (SSE) for real-time dashboard

### 1.4 Language & Versions
- **Primary Language**: Python 3.9+ (type hints throughout)
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3
- **Platform**: Windows 10/11 (batch scripts), Linux/Mac compatible (shell scripts)

---

## 2. Detailed Directory Structure Analysis

### 2.1 Root Directory Structure
```
Email-Management-Tool/
├── simple_app.py              # Main application entry point (918 lines)
├── app/                       # Application package
│   ├── routes/               # Blueprint route handlers (13 modules)
│   ├── services/             # Business logic layer
│   ├── models/               # Data models
│   ├── utils/                # Shared utilities
│   ├── workers/              # Background thread managers
│   └── extensions.py         # Flask extension instances
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS, JS, assets
├── tests/                     # Pytest test suite (138 tests)
├── docs/                      # Comprehensive documentation
├── scripts/                   # Utility scripts
├── config/                    # Configuration files (gitignored)
├── data/                      # SQLite database (gitignored)
├── logs/                      # Application logs (gitignored)
├── database_backups/          # Automated backups
├── emergency_email_backup/    # Email safety backup
└── archive/                   # Historical files (gitignored)
```

### 2.2 Core Application Directory (`app/`)

#### **`app/routes/` - Blueprint Modules**
13 route blueprints implementing clean separation of concerns:

| Blueprint | File | Routes | Purpose |
|-----------|------|--------|---------|
| `auth_bp` | auth.py | /, /login, /logout | Authentication & session management |
| `dashboard_bp` | dashboard.py | /dashboard, /dashboard/<tab> | Main UI dashboard |
| `stats_bp` | stats.py | /api/stats, /stream/stats | Real-time statistics API |
| `bp_interception` | interception.py | /api/interception/* | Email hold/release/edit operations |
| `emails_bp` | emails.py | /emails, /email/<id> | Email queue & viewer |
| `accounts_bp` | accounts.py | /accounts, /accounts/add | Account management |
| `inbox_bp` | inbox.py | /inbox | Unified inbox view |
| `compose_bp` | compose.py | /compose | Email composition |
| `moderation_bp` | moderation.py | /rules | Moderation rule management |
| `diagnostics_bp` | diagnostics.py | /diagnostics | Health checks & testing |
| `legacy_bp` | legacy.py | /api/legacy/* | Backward compatibility |
| `styleguide_bp` | styleguide.py | /styleguide | UI component showcase |
| `watchers_bp` | watchers.py | /watchers, /settings | IMAP watcher control |

#### **`app/services/` - Business Logic Layer**
Core services implementing application logic:

- **`audit.py`**: Audit logging (`log_action()`, `get_recent_logs()`)
- **`stats.py`**: Metrics aggregation with TTL caching
- **`imap_watcher.py`**: IMAP IDLE/polling hybrid worker (920 lines)
- **`mail_redeliver.py`**: Email re-delivery via IMAP APPEND
- **`interception/`**: Inbound interception subsystem
  - `rapid_imap_copy_purge.py`: Fast COPY→EXPUNGE workflow
  - `release_editor.py`: MIME reconstruction for edited releases

#### **`app/models/` - Data Models**
Lightweight models (no ORM - raw sqlite3):

- **`simple_user.py`**: Flask-Login user model
- **`account.py`, `email.py`, `rule.py`**: Schema definitions (documentation only)
- **`base.py`**: Shared model utilities

#### **`app/utils/` - Shared Utilities**
Cross-cutting concerns and helpers:

- **`db.py`**: Database connection manager (`get_db()` context manager)
- **`crypto.py`**: Fernet encryption/decryption for credentials
- **`email_helpers.py`**: SMTP/IMAP smart detection, connection testing
- **`imap_helpers.py`**: IMAP operations (connect, quarantine, move)
- **`rule_engine.py`**: Moderation rule evaluation
- **`logging.py`**: Application logging setup
- **`metrics.py`**: Prometheus metrics (optional)
- **`rate_limit.py`**: Rate limiter configuration

#### **`app/workers/` - Background Workers**
Thread management and startup:

- **`imap_startup.py`**: Auto-start IMAP watchers for active accounts

#### **`app/extensions.py`** - Flask Extensions
Singleton extension instances shared across app:
```python
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
```

### 2.3 Templates Directory (`templates/`)
19 Jinja2 templates with Bootstrap 5.3:

| Template | Purpose |
|----------|---------|
| `base.html` | Master template with nav, CSRF, dark theme |
| `login.html` | Authentication form |
| `dashboard_unified.html` | Main dashboard with stats |
| `emails_unified.html` | Email queue with filters |
| `email_viewer.html` | Single email detail view |
| `email_editor_modal.html` | Edit email before release |
| `inbox.html` | Unified inbox across accounts |
| `compose.html` | Email composition form |
| `accounts.html` | Account management UI |
| `add_account.html` | Add account wizard |
| `rules.html` | Moderation rule editor |
| `watchers.html` | IMAP watcher status |
| `settings.html` | Application settings |
| `styleguide.html` | UI component showcase |

**Key Features**:
- Dark theme by default (`background-attachment: fixed`)
- Bootstrap 5.3 toasts (no browser alerts)
- CSRF token injection in all forms
- `.input-modern` class for consistent inputs
- SSE-powered real-time updates

### 2.4 Static Assets (`static/`)
```
static/
├── css/
│   ├── main.css           # Core styles (dark theme, utilities)
│   └── theme-dark.css     # Dark mode palette
├── js/
│   ├── app.js             # Main application JS (SSE, toasts, filters)
│   └── email_editor.js    # Email editing modal logic
└── favicon.svg            # App icon
```

**JavaScript Architecture**:
- Vanilla ES6+ (no framework dependencies)
- EventSource API for SSE streaming
- Bootstrap Toast API for notifications
- Fetch API for AJAX operations

### 2.5 Tests Directory (`tests/`)
138 passing tests organized by layer:

```
tests/
├── conftest.py                    # Pytest fixtures (Flask app, test client, DB)
├── routes/                        # Route/integration tests
│   ├── test_dashboard_view.py    # Dashboard rendering
│   ├── test_interception_*.py    # Interception flow tests (3 files)
│   ├── test_error_logging.py     # Error handler tests
│   └── test_manual_intercept_logic.py  # Manual intercept tests
├── services/                      # Service layer tests
│   ├── test_imap_watcher_*.py    # IMAP watcher tests (3 files)
│   └── test_interception_comprehensive.py  # Full interception suite
├── utils/                         # Utility tests
│   ├── test_db_utils.py          # Database utilities
│   ├── test_email_helpers_unit.py # Email helper functions
│   ├── test_rule_engine_schemas.py # Rule validation
│   ├── test_json_logging.py      # Logging tests
│   ├── test_prometheus_metrics.py # Metrics tests
│   └── test_rate_limiting.py     # Rate limiter tests
└── live/                          # Live integration tests (env-gated)
    └── test_quarantine_flow_e2e.py # End-to-end IMAP test
```

**Coverage**: 36% (138/138 passing, target: 50%+)

### 2.6 Documentation Directory (`docs/`)
30+ comprehensive markdown files:

**Architecture & Design**:
- `ARCHITECTURE.md` - System architecture (153 lines)
- `DATABASE_SCHEMA.md` - Full schema documentation (211 lines)
- `TECHNICAL_DEEP_DIVE.md` - Implementation details
- `HYBRID_IMAP_STRATEGY.md` - IDLE+polling approach

**Operations**:
- `DEPLOYMENT.md` - Production deployment guide
- `DEVELOPMENT.md` - Developer onboarding
- `TESTING.md` - Test strategy & execution
- `TROUBLESHOOTING.md` - Common issues & solutions

**Security**:
- `SECURITY.md` - Security configuration & validation
- `PRODUCTION_READINESS_ANALYSIS.md` - Security audit

**Setup Guides**:
- `setup/GMAIL_SETUP_GUIDE.md` - Gmail configuration
- `setup/HOSTINGER_SETUP.md` - Hostinger configuration
- `setup/INSTALL_WINDOWS.md` - Windows installation

**Reports** (35 analysis documents in `docs/reports/`):
- Test results, debugging sessions, improvement summaries

---

## 3. File-by-File Breakdown

### 3.1 Core Application Files

#### **`simple_app.py`** - Main Entry Point (918 lines)
**Purpose**: Application bootstrap, service initialization, Flask app configuration

**Key Components**:
```python
# Application initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret')
app.config['IMAP_ONLY'] = bool(os.environ.get('IMAP_ONLY', '0'))

# Security extensions
from app.extensions import csrf, limiter
csrf.init_app(app)
limiter.init_app(app)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# Blueprint registration (13 blueprints)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
# ... 11 more blueprints

# Background services
def run_smtp_proxy():  # aiosmtpd on port 8587
def monitor_imap_account(account_id):  # IMAP watcher thread
```

**Functions**:
- `check_port_available()`: Port conflict detection & cleanup
- `init_database()`: SQLite schema initialization
- `start_imap_watcher_for_account()`: Launch IMAP monitor
- `stop_imap_watcher_for_account()`: Graceful shutdown
- `EmailModerationHandler.handle_DATA()`: SMTP proxy message handler
- Error handlers: `handle_csrf_exception()`, `ratelimit_error()`

**Thread Architecture**:
```python
# SMTP proxy thread
smtp_thread = threading.Thread(target=run_smtp_proxy, daemon=True)
smtp_thread.start()

# IMAP monitor threads (one per active account)
for account_id in active_accounts:
    thread = threading.Thread(target=monitor_imap_account, args=(account_id,), daemon=True)
    imap_threads[account_id] = thread
    thread.start()
```

#### **`app/routes/interception.py`** - Interception API (Primary Feature)
**Routes**:
- `GET /healthz` - Health check with metrics
- `GET /api/interception/held` - List HELD messages
- `GET /api/interception/held/<id>` - Message details
- `POST /api/interception/release/<id>` - Release to inbox
- `POST /api/interception/discard/<id>` - Discard message
- `POST /api/email/<id>/edit` - Edit subject/body
- `POST /api/email/<id>/strip-attachments` - Remove attachments
- `GET /api/inbox` - Unified inbox (all accounts)

**Key Implementation**:
```python
@bp_interception.route('/api/interception/release/<int:msg_id>', methods=['POST'])
@login_required
def release_email_to_inbox(msg_id):
    # 1. Load message from DB (HELD status)
    # 2. Decrypt IMAP credentials
    # 3. Reconstruct MIME (with edits if present)
    # 4. IMAP APPEND to original folder
    # 5. Update status to RELEASED
    # 6. Log action to audit trail
    # 7. Return success with metrics
```

#### **`app/services/imap_watcher.py`** - IMAP Monitoring Worker (920 lines)
**Purpose**: Hybrid IDLE+polling email interceptor

**Architecture**:
```python
class ImapWatcher:
    def __init__(self, config: AccountConfig):
        self.imap_host = config.imap_host
        self.idle_timeout = config.idle_timeout  # Default: 25 min
        self.idle_ping_interval = config.idle_ping_interval  # Default: 14 min
        
    def run_forever(self):
        """Main loop with auto-reconnect"""
        while True:
            try:
                self._connect()
                self._watch_inbox()  # IDLE with keepalive
            except Exception:
                self._backoff_sleep()
    
    def _watch_inbox(self):
        """Hybrid IDLE+polling strategy"""
        self.client.idle()  # Enter IDLE mode
        while self.client.idle_check(timeout=self.idle_ping_interval):
            # Process new messages
            new_uids = self._check_for_new()
            for uid in new_uids:
                self._intercept_message(uid)
        self.client.idle_done()  # Exit IDLE, send NOOP
```

**Interception Flow**:
1. **Detect**: IDLE notification or UIDNEXT delta
2. **Fetch**: Retrieve full RFC822 message
3. **Evaluate**: Apply moderation rules
4. **Quarantine**: COPY to Quarantine folder, EXPUNGE from INBOX
5. **Store**: Insert into `email_messages` table (status=HELD)
6. **Metrics**: Record latency_ms for /healthz endpoint

**Resilience Features**:
- Exponential backoff (5s → 30s max)
- Jittered retry delays
- Circuit breaker pattern (configurable threshold)
- Graceful reconnection on network failures

### 3.2 Configuration Files

#### **`requirements.txt`** - Production Dependencies
**Core Dependencies** (20 packages after cleanup):
```
# Web Framework
Flask>=3.0.0
Flask-Login>=0.6.3
Flask-WTF>=1.2.1
Flask-Limiter>=3.5.0
Werkzeug>=3.0.1

# Email Processing
aiosmtpd>=1.4.4.post2
imapclient>=3.0.0
python-dateutil>=2.8.2

# Security
cryptography>=41.0.7
python-dotenv>=1.0.0

# Testing
pytest>=7.4.3
pytest-flask>=1.3.0
pytest-asyncio>=0.21.1
faker>=20.1.0

# Development
black>=23.12.0
pylint>=3.0.3
mypy>=1.7.1
pre-commit>=3.6.0
```

**Removed Dependencies** (20+ unused packages):
- SQLAlchemy (using raw sqlite3)
- Flask-RESTX, Flask-JWT-Extended (no REST framework)
- Celery, Redis (no background tasks)
- bcrypt (using werkzeug.security)
- Sentry, Locust (no monitoring/load testing)

#### **`.env.example`** - Environment Template
```bash
# Flask Configuration
FLASK_SECRET_KEY=<generate-with-secrets.token_hex(32)>
FLASK_DEBUG=0  # Set to 1 for development
FLASK_HOST=127.0.0.1
FLASK_PORT=5000

# SMTP Proxy
SMTP_PROXY_HOST=127.0.0.1
SMTP_PROXY_PORT=8587

# IMAP Configuration
IMAP_ONLY=0  # Set to 1 to disable SMTP proxy
IMAP_IDLE_TIMEOUT=1500  # 25 minutes
IMAP_IDLE_PING_INTERVAL=840  # 14 minutes

# Test Account Credentials (DO NOT COMMIT)
GMAIL_ADDRESS=ndayijecika@gmail.com
GMAIL_PASSWORD=<app-password-with-spaces>
HOSTINGER_ADDRESS=mcintyre@corrinbox.com
HOSTINGER_PASSWORD=<password>

# Security
REQUIRE_LIVE_CREDENTIALS=0  # Set to 1 to enforce env credentials
```

#### **`.gitignore`** - Exclusions (188 lines)
Key exclusions:
```
# Sensitive data
.env, .env.local, .env.production
key.txt  # Fernet encryption key
config/secrets.ini
*.key, *.pem, *.crt

# Database & logs
*.db, *.sqlite, *.sqlite3
data/, logs/, *.log

# MCP configurations (API keys)
.mcp.json, mcp.json, *.mcp.json
.serena/, .playwright-mcp/, .kilocode/

# Backups & temporary
archive/, database_backups/
*.backup, *.backup-*, *.md.tmp

# Python
__pycache__/, *.py[cod], .venv/, venv/

# IDE
.vscode/, .idea/, .claude/
```

### 3.3 Data Layer

#### **`app/utils/db.py`** - Database Manager
**Purpose**: Thread-safe SQLite connection management

```python
DB_PATH = "email_manager.db"

def get_db():
    """Context manager for SQLite connections with row_factory"""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row  # Dict-like access
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    conn.execute("PRAGMA busy_timeout=10000")  # 10s lock timeout
    try:
        yield conn
    finally:
        conn.close()

def table_exists(table_name):
    """Check if table exists in database"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cur.fetchone() is not None

def fetch_counts():
    """Optimized count query with single scan"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN interception_status='HELD' THEN 1 ELSE 0 END) as held,
                SUM(CASE WHEN interception_status='RELEASED' THEN 1 ELSE 0 END) as released
            FROM email_messages
        """)
        return cur.fetchone()
```

**Database Initialization** (`simple_app.py:init_database()`):
```python
def init_database():
    """Create all tables if not exist"""
    conn = get_db()
    cur = conn.cursor()
    
    # Users table (bcrypt password hashing)
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT DEFAULT 'admin',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    
    # Email accounts (encrypted credentials)
    cur.execute("""CREATE TABLE IF NOT EXISTS email_accounts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_address TEXT,
        imap_host TEXT, imap_port INTEGER,
        imap_username TEXT, imap_password TEXT,  # Fernet encrypted
        smtp_host TEXT, smtp_port INTEGER,
        smtp_username TEXT, smtp_password TEXT,  # Fernet encrypted
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    
    # Email messages (full interception tracking)
    cur.execute("""CREATE TABLE IF NOT EXISTS email_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT,
        account_id INTEGER,
        direction TEXT,  # 'inbound' or 'outbound'
        status TEXT DEFAULT 'PENDING',
        interception_status TEXT,  # HELD/RELEASED/DISCARDED
        sender TEXT, recipients TEXT,
        subject TEXT, body_text TEXT, body_html TEXT,
        raw_content TEXT,  # Full MIME message
        raw_path TEXT,  # Path to .eml file
        original_uid INTEGER,  # IMAP UID in Quarantine
        edited_message_id TEXT,  # Message-ID after editing
        risk_score INTEGER DEFAULT 0,
        keywords_matched TEXT,
        latency_ms INTEGER,  # Interception latency
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        processed_at TEXT, action_taken_at TEXT
    )""")
    
    # Moderation rules
    cur.execute("""CREATE TABLE IF NOT EXISTS moderation_rules(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_name TEXT,
        keyword TEXT,
        action TEXT DEFAULT 'REVIEW',
        priority INTEGER DEFAULT 5,
        is_active INTEGER DEFAULT 1
    )""")
    
    # Audit log
    cur.execute("""CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT, user_id INTEGER, target_id INTEGER,
        details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    
    # Performance indices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_email_messages_status ON email_messages(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_email_messages_interception_status ON email_messages(interception_status)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_email_messages_msgid_unique ON email_messages(message_id) WHERE message_id IS NOT NULL")
    
    # Default admin user
    from werkzeug.security import generate_password_hash
    cur.execute("SELECT id FROM users WHERE username='admin'")
    if not cur.fetchone():
        admin_hash = generate_password_hash('admin123')
        cur.execute("INSERT INTO users(username, password_hash, role) VALUES('admin', ?, 'admin')", (admin_hash,))
    
    conn.commit()
    conn.close()
```

**Schema Indices** (Performance optimization):
```sql
-- Fast status filtering
CREATE INDEX idx_email_messages_status ON email_messages(status);
CREATE INDEX idx_email_messages_interception_status ON email_messages(interception_status);

-- Multi-column for complex queries
CREATE INDEX idx_email_messages_account_status ON email_messages(account_id, status);
CREATE INDEX idx_email_messages_direction_status ON email_messages(direction, interception_status);

-- IMAP operations
CREATE INDEX idx_email_messages_original_uid ON email_messages(original_uid);

-- Unique constraint on Message-ID
CREATE UNIQUE INDEX idx_email_messages_msgid_unique ON email_messages(message_id) WHERE message_id IS NOT NULL;
```

#### **`app/utils/crypto.py`** - Credential Encryption
**Purpose**: Fernet symmetric encryption for database credentials

```python
from cryptography.fernet import Fernet

KEY_FILE = "key.txt"

def get_encryption_key():
    """Load or generate Fernet key"""
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
        return key
    with open(KEY_FILE, 'rb') as f:
        return f.read()

FERNET_KEY = get_encryption_key()
fernet = Fernet(FERNET_KEY)

def encrypt_credential(plaintext):
    """Encrypt credential for database storage"""
    if not plaintext:
        return None
    return fernet.encrypt(plaintext.encode()).decode()

def decrypt_credential(ciphertext):
    """Decrypt credential from database"""
    if not ciphertext:
        return None
    return fernet.decrypt(ciphertext.encode()).decode()
```

**Security Notes**:
- `key.txt` is gitignored (never commit)
- Fernet uses AES-128-CBC with HMAC-SHA256
- All IMAP/SMTP passwords encrypted at rest
- Key rotation requires re-encryption of all credentials

### 3.4 Frontend/UI Files

#### **`static/js/app.js`** - Main Application JavaScript
**Features**:
1. **Server-Sent Events (SSE)**: Real-time stats updates
2. **Toast Notifications**: Bootstrap 5.3 toast API
3. **Email Queue Filtering**: Client-side search/filter
4. **Account Management**: Add/edit/delete with AJAX

**SSE Implementation**:
```javascript
// Real-time stats streaming
const eventSource = new EventSource('/stream/stats');
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    updateDashboardStats(data);
};

function updateDashboardStats(stats) {
    document.getElementById('total-count').textContent = stats.total;
    document.getElementById('pending-count').textContent = stats.pending;
    document.getElementById('held-count').textContent = stats.held;
    // ... update charts
}
```

**Toast Notifications**:
```javascript
function showToast(message, type = 'info') {
    const toastHTML = `
        <div class="toast align-items-center text-bg-${type}" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>`;
    const container = document.getElementById('toast-container');
    container.insertAdjacentHTML('beforeend', toastHTML);
    const toastElement = container.lastElementChild;
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
}
```

**Email Filtering**:
```javascript
function filterEmails() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const status = document.getElementById('status-filter').value;
    
    document.querySelectorAll('.email-row').forEach(row => {
        const matchesSearch = row.textContent.toLowerCase().includes(query);
        const matchesStatus = !status || row.dataset.status === status;
        row.style.display = (matchesSearch && matchesStatus) ? '' : 'none';
    });
}
```

#### **`static/js/email_editor.js`** - Email Editing Modal
**Purpose**: Edit email subject/body before release

```javascript
class EmailEditor {
    constructor(emailId) {
        this.emailId = emailId;
        this.originalSubject = '';
        this.originalBody = '';
        this.loadEmailData();
    }
    
    async loadEmailData() {
        const response = await fetch(`/api/interception/held/${this.emailId}`);
        const data = await response.json();
        this.originalSubject = data.subject;
        this.originalBody = data.body_text;
        this.renderEditor();
    }
    
    async saveChanges() {
        const newSubject = document.getElementById('edit-subject').value;
        const newBody = document.getElementById('edit-body').value;
        
        const response = await fetch(`/api/email/${this.emailId}/edit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                subject: newSubject,
                body_text: newBody
            })
        });
        
        if (response.ok) {
            showToast('Email updated successfully', 'success');
            this.showDiff(newSubject, newBody);
        }
    }
    
    showDiff(newSubject, newBody) {
        // Highlight differences between original and edited
        const diffHTML = this.generateDiff(this.originalSubject, newSubject);
        document.getElementById('diff-preview').innerHTML = diffHTML;
    }
}
```

#### **`static/css/main.css`** - Core Styles
**Key Features**:
- **Dark theme by default**: `background: #1a1a1a`
- **Fixed backgrounds**: Prevent white flash on scroll
- **Modern inputs**: `.input-modern` class for consistent styling
- **Responsive grid**: Bootstrap 5.3 grid system
- **Custom scrollbars**: Dark-themed scrollbars

```css
/* Dark theme base */
body {
    background-color: #1a1a1a;
    background-attachment: fixed;  /* Prevent white flash */
    color: #e0e0e0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* Modern input styling */
.input-modern {
    background-color: #2a2a2a;
    border: 1px solid #444;
    color: #e0e0e0;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
}

.input-modern:focus {
    background-color: #333;
    border-color: #0d6efd;
    box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25);
}

/* Email status badges */
.badge-pending { background-color: #ffc107; color: #000; }
.badge-held { background-color: #dc3545; color: #fff; }
.badge-released { background-color: #198754; color: #fff; }
.badge-discarded { background-color: #6c757d; color: #fff; }
```

### 3.5 Testing Files

#### **`tests/conftest.py`** - Pytest Fixtures
**Purpose**: Shared test fixtures and configuration

```python
import pytest
import tempfile
import os
from simple_app import app as flask_app, init_database

@pytest.fixture
def app():
    """Create Flask app for testing with temporary database"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    flask_app.config['TESTING'] = True
    flask_app.config['DATABASE'] = db_path
    flask_app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for tests
    
    # Initialize test database
    with flask_app.app_context():
        init_database()
    
    yield flask_app
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """Test client for making requests"""
    return app.test_client()

@pytest.fixture
def auth_client(client):
    """Authenticated test client"""
    client.post('/login', data={
        'username': 'admin',
        'password': 'admin123'
    })
    return client

@pytest.fixture
def sample_email():
    """Sample email message for testing"""
    return {
        'sender': 'test@example.com',
        'recipients': ['user@example.com'],
        'subject': 'Test Subject',
        'body_text': 'Test body content',
        'direction': 'inbound',
        'status': 'PENDING'
    }
```

#### **`tests/routes/test_interception_release_flow.py`** - Key Integration Test
```python
def test_full_release_flow(auth_client, sample_email):
    """Test complete interception → edit → release workflow"""
    # 1. Create intercepted email
    response = auth_client.post('/api/email/intercept', json=sample_email)
    assert response.status_code == 200
    email_id = response.json['id']
    
    # 2. Verify email is HELD
    response = auth_client.get(f'/api/interception/held/{email_id}')
    assert response.json['interception_status'] == 'HELD'
    
    # 3. Edit email
    response = auth_client.post(f'/api/email/{email_id}/edit', json={
        'subject': 'Edited Subject',
        'body_text': 'Edited body'
    })
    assert response.status_code == 200
    
    # 4. Release to inbox
    response = auth_client.post(f'/api/interception/release/{email_id}')
    assert response.status_code == 200
    assert response.json['ok'] is True
    
    # 5. Verify status changed to RELEASED
    response = auth_client.get(f'/api/interception/held/{email_id}')
    assert response.json['interception_status'] == 'RELEASED'
    
    # 6. Check audit log
    response = auth_client.get('/api/audit-log')
    logs = response.json
    assert any(log['action'] == 'RELEASE' and log['target_id'] == email_id for log in logs)
```

### 3.6 DevOps Files

#### **`EmailManager.bat`** - Professional Windows Launcher
```batch
@echo off
setlocal enabledelayedexpansion

:menu
cls
echo ========================================
echo   EMAIL MANAGEMENT TOOL - LAUNCHER
echo ========================================
echo.
echo 1. Start Application
echo 2. Run Tests
echo 3. View Logs
echo 4. Database Backup
echo 5. Check Dependencies
echo 6. Exit
echo.
set /p choice="Enter choice (1-6): "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto test
if "%choice%"=="3" goto logs
if "%choice%"=="4" goto backup
if "%choice%"=="5" goto deps
if "%choice%"=="6" goto exit

:start
echo Starting application...
python simple_app.py
goto menu

:test
echo Running tests...
python -m pytest tests/ -v
pause
goto menu

:logs
echo Recent logs:
type logs\app.log | more
pause
goto menu

:backup
echo Creating database backup...
python scripts\backup_database.py
pause
goto menu

:deps
echo Checking dependencies...
pip list
pause
goto menu

:exit
exit
```

#### **`manage.ps1`** - PowerShell Management Script
```powershell
param(
    [Parameter(Position=0)]
    [ValidateSet('start', 'stop', 'restart', 'status', 'backup', 'restore', 'logs', 'config', 'install', 'uninstall')]
    [string]$Command
)

function Start-Application {
    Write-Host "Starting Email Management Tool..." -ForegroundColor Green
    Start-Process python -ArgumentList "simple_app.py" -NoNewWindow
}

function Stop-Application {
    Write-Host "Stopping application..." -ForegroundColor Yellow
    Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -like "*Email Management*"
    } | Stop-Process -Force
}

function Get-Status {
    $process = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -like "*Email Management*"
    }
    if ($process) {
        Write-Host "Status: RUNNING (PID: $($process.Id))" -ForegroundColor Green
    } else {
        Write-Host "Status: STOPPED" -ForegroundColor Red
    }
}

function Backup-Database {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupPath = "database_backups\email_manager_$timestamp.db"
    Copy-Item "email_manager.db" $backupPath
    Write-Host "Database backed up to: $backupPath" -ForegroundColor Green
}

function Show-Logs {
    Get-Content "logs\app.log" -Tail 50 | Write-Host
}

# Execute command
switch ($Command) {
    'start' { Start-Application }
    'stop' { Stop-Application }
    'restart' { Stop-Application; Start-Sleep -Seconds 2; Start-Application }
    'status' { Get-Status }
    'backup' { Backup-Database }
    'logs' { Show-Logs }
    default { Write-Host "Usage: .\manage.ps1 [start|stop|restart|status|backup|logs]" }
}
```

---

## 4. API Endpoints Analysis

### 4.1 API Endpoint Inventory

#### **Authentication Endpoints** (`app/routes/auth.py`)
| Method | Endpoint | Purpose | Rate Limit |
|--------|----------|---------|------------|
| GET | `/` | Redirect to login/dashboard | None |
| GET | `/login` | Login form | None |
| POST | `/login` | Authenticate user | 5/minute |
| GET | `/logout` | End session | None |

#### **Dashboard Endpoints** (`app/routes/dashboard.py`)
| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| GET | `/dashboard` | Main dashboard (default tab) | Required |
| GET | `/dashboard/<tab>` | Dashboard with specific tab | Required |
| GET | `/test-dashboard` | Test/debug dashboard | Required |

#### **Statistics API** (`app/routes/stats.py`)
| Method | Endpoint | Cache | Purpose |
|--------|----------|-------|---------|
| GET | `/api/stats` | 5s | Basic counts (total, pending, held) |
| GET | `/api/unified-stats` | 2s | Full stats with latency metrics |
| GET | `/api/latency-stats` | 2s | Median latency calculation |
| GET | `/stream/stats` | SSE | Real-time stats streaming |
| GET | `/api/events` | SSE | Legacy SSE endpoint (redirect) |

#### **Interception API** (`app/routes/interception.py`)
| Method | Endpoint | Purpose | Critical |
|--------|----------|---------|----------|
| GET | `/healthz` | Health check + metrics | ✅ Monitoring |
| GET | `/api/interception/held` | List HELD messages (last 200) | ✅ Core feature |
| GET | `/api/interception/held/<id>` | Message details + preview | ✅ Core feature |
| POST | `/api/interception/release/<id>` | Release to inbox (with edits) | ✅ Core feature |
| POST | `/api/interception/discard/<id>` | Discard message | ✅ Core feature |
| POST | `/api/email/<id>/edit` | Edit subject/body | ✅ Core feature |
| POST | `/api/email/<id>/strip-attachments` | Remove attachments | Optional |
| GET | `/api/inbox` | Unified inbox view | ✅ Core feature |

**Interception Flow Example**:
```bash
# 1. List held messages
GET /api/interception/held
Response: {
  "stats": {"held_count": 5, "released_24h": 12},
  "messages": [
    {"id": 123, "subject": "Test", "sender": "test@example.com", "status": "HELD"}
  ]
}

# 2. Get message details
GET /api/interception/held/123
Response: {
  "id": 123,
  "subject": "Test",
  "preview_snippet": "First 500 chars...",
  "attachments": ["file.pdf"],
  "risk_score": 75
}

# 3. Edit message
POST /api/email/123/edit
Body: {"subject": "Reviewed: Test", "body_text": "Updated content"}
Response: {"ok": true}

# 4. Release to inbox
POST /api/interception/release/123
Body: {"edited_subject": "Final Subject"}  # Optional override
Response: {"ok": true, "released_to": "INBOX"}
```

#### **Email Management** (`app/routes/emails.py`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/emails` | Email queue page |
| GET | `/email/<id>` | Email viewer page |
| POST | `/email/<id>/action` | Approve/reject action |
| GET | `/email/<id>/full` | Full email raw view |
| GET | `/api/fetch-emails` | Fetch from IMAP |
| POST | `/api/email/<id>/reply-forward` | Reply/forward helper |
| GET | `/api/email/<id>/download` | Download .eml file |

#### **Account Management** (`app/routes/accounts.py`)
| Method | Endpoint | Purpose | Features |
|--------|----------|---------|----------|
| GET | `/accounts` | Account list page | Table view |
| GET | `/accounts/add` | Add account wizard | Smart detection |
| POST | `/api/accounts` | Create account | Validation |
| GET | `/api/accounts` | List accounts (JSON) | API |
| GET | `/api/accounts/<id>` | Get account details | API |
| PUT | `/api/accounts/<id>` | Update account | API |
| DELETE | `/api/accounts/<id>` | Delete account | API |
| GET | `/api/accounts/<id>/health` | Health check | Connectivity |
| POST | `/api/accounts/<id>/test` | Test connection | IMAP/SMTP |
| POST | `/api/accounts/<id>/monitor/start` | Start IMAP watcher | Background |
| POST | `/api/accounts/<id>/monitor/stop` | Stop IMAP watcher | Graceful shutdown |
| GET | `/api/accounts/export` | Export accounts JSON | Backup |
| POST | `/api/test-connection/<type>` | Test IMAP/SMTP | Diagnostics |
| POST | `/api/detect-email-settings` | Auto-detect settings | Gmail/Hostinger/generic |
| GET | `/diagnostics` | Diagnostics page | Redirect to accounts |
| GET | `/diagnostics/<id>` | Account diagnostics | Connectivity tests |

**Smart Email Detection Example**:
```bash
POST /api/detect-email-settings
Body: {"email": "user@gmail.com"}
Response: {
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "imap_use_ssl": true,
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_use_ssl": false  # Uses STARTTLS
}
```

#### **Compose & Inbox** (`app/routes/compose.py`, `app/routes/inbox.py`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/compose` | Email composition form |
| POST | `/compose` | Send email via SMTP |
| GET | `/inbox` | Unified inbox view |

#### **Moderation Rules** (`app/routes/moderation.py`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/rules` | Rule management page (admin only) |
| POST | `/rules/add` | Create new rule |
| PUT | `/rules/<id>` | Update rule |
| DELETE | `/rules/<id>` | Delete rule |

#### **Diagnostics** (`app/routes/diagnostics.py`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/test/cross-account` | Multi-account test |
| GET | `/api/test-status` | Test status API |

#### **Legacy Compatibility** (`app/routes/legacy.py`)
| Method | Endpoint | Redirect To |
|--------|----------|-------------|
| GET | `/api/events` | `/stream/stats` |
| GET | `/old/dashboard` | `/dashboard` |

### 4.2 Authentication & Authorization

**Flask-Login Integration**:
```python
from flask_login import login_required, current_user

@app.route('/dashboard')
@login_required  # Redirect to /login if not authenticated
def dashboard():
    # current_user is SimpleUser instance
    username = current_user.username
    user_id = current_user.id
    # ...
```

**Session Management**:
- **Storage**: Secure server-side Flask sessions
- **Cookie**: `session` cookie (HTTP-only, secure in production)
- **Timeout**: Session expires on browser close
- **CSRF Protection**: Token validation on all POST/PUT/DELETE

**Role-Based Access** (Basic implementation):
```python
# Admin-only routes
@moderation_bp.route('/rules')
@login_required
def rules():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard.dashboard'))
    # ...
```

### 4.3 Request/Response Formats

**Standard JSON Response**:
```json
{
  "ok": true,
  "data": { /* payload */ },
  "message": "Success message",
  "timestamp": "2025-10-18T12:00:00Z"
}
```

**Error Response**:
```json
{
  "ok": false,
  "error": "Error description",
  "code": "ERROR_CODE",
  "details": { /* optional debug info */ }
}
```

**Pagination** (List endpoints):
```json
{
  "items": [ /* array of objects */ ],
  "total": 150,
  "page": 1,
  "per_page": 50,
  "pages": 3
}
```

### 4.4 API Versioning Strategy
**Current Approach**: No versioning (v1 implied)
**Future**: Prefix routes with `/api/v1/` when breaking changes needed

---

## 5. Architecture Deep Dive

### 5.1 Overall Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  Email Client (Outlook, Thunderbird)  │  Web Browser            │
│  SMTP: localhost:8587                 │  http://localhost:5000  │
└──────────────┬─────────────────────────┴────────────┬───────────┘
               │                                       │
               ▼                                       ▼
┌──────────────────────────┐           ┌──────────────────────────┐
│   SMTP PROXY SERVER      │           │   FLASK WEB SERVER       │
│   (aiosmtpd thread)      │           │   (Werkzeug/Flask)       │
│   Port: 8587             │           │   Port: 5000             │
└──────────────┬───────────┘           └──────────┬───────────────┘
               │                                   │
               │ Intercept outbound               │ HTTP requests
               │ emails                           │
               ▼                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
├──────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Blueprints │  │   Services   │  │  Background Workers     │ │
│  │  (Routes)   │  │              │  │                         │ │
│  ├─────────────┤  ├──────────────┤  ├─────────────────────────┤ │
│  │ auth        │  │ audit        │  │ IMAP Watcher (thread)   │ │
│  │ dashboard   │  │ stats        │  │ └─ IDLE monitoring      │ │
│  │ interception│  │ imap_watcher │  │ └─ Auto-reconnect       │ │
│  │ emails      │  │ mail_redeliver│ │ └─ Quarantine flow      │ │
│  │ accounts    │  │ rule_engine  │  │                         │ │
│  │ compose     │  │              │  │ SMTP Proxy (thread)     │ │
│  │ inbox       │  │              │  │ └─ Message handler      │ │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                             │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │  SQLite DB       │  │  Encrypted   │  │  Raw Email Files   │ │
│  │  (WAL mode)      │  │  key.txt     │  │  data/inbound_raw/ │ │
│  ├──────────────────┤  │  (Fernet)    │  │  *.eml files       │ │
│  │ users            │  └──────────────┘  └────────────────────┘ │
│  │ email_accounts   │                                            │
│  │ email_messages   │                                            │
│  │ moderation_rules │                                            │
│  │ audit_log        │                                            │
│  └──────────────────┘                                            │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐      ┌──────────────────────────┐   │
│  │  Gmail IMAP/SMTP       │      │  Hostinger IMAP/SMTP     │   │
│  │  imap.gmail.com:993    │      │  imap.hostinger.com:993  │   │
│  │  smtp.gmail.com:587    │      │  smtp.hostinger.com:465  │   │
│  └────────────────────────┘      └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Data Flow & Request Lifecycle

#### **Inbound Email Interception (IMAP Watcher)**
```
1. IMAP Watcher Detects New Message
   └─ IDLE notification or UIDNEXT delta
   
2. Fetch Full Message
   └─ FETCH uid RFC822
   
3. Evaluate Moderation Rules
   └─ rule_engine.evaluate_rules(subject, body, sender)
   └─ Calculate risk_score
   └─ Match keywords
   
4. Quarantine Decision
   ├─ If should_hold = True:
   │  ├─ COPY uid to Quarantine folder
   │  ├─ EXPUNGE from INBOX
   │  └─ Store raw email to data/inbound_raw/<id>.eml
   └─ Else: Leave in INBOX
   
5. Store in Database
   └─ INSERT INTO email_messages (
        status='PENDING',
        interception_status='HELD',
        raw_path='data/inbound_raw/123.eml',
        latency_ms=<time_delta>
      )
   
6. Record Metrics
   └─ Update worker heartbeat
   └─ Store latency for /healthz
```

#### **Outbound Email Interception (SMTP Proxy)**
```
1. Email Client Sends to localhost:8587
   └─ SMTP EHLO, MAIL FROM, RCPT TO, DATA
   
2. SMTP Proxy Receives Message
   └─ EmailModerationHandler.handle_DATA(envelope)
   
3. Parse MIME Message
   └─ email.message_from_bytes(envelope.content)
   
4. Extract Components
   ├─ Sender: envelope.mail_from
   ├─ Recipients: envelope.rcpt_tos
   ├─ Subject: email_msg.get('Subject')
   └─ Body: parse multipart (text/html)
   
5. Evaluate Rules
   └─ rule_engine.check_rules(subject, body, sender, recipients)
   
6. Store in Database
   └─ INSERT INTO email_messages (
        direction='outbound',
        status='PENDING',
        interception_status='HELD',
        raw_content=<full_mime>
      )
   
7. Return 250 OK
   └─ Email client thinks message sent
   └─ Actually held in database for review
```

#### **Email Release Flow**
```
1. Admin Requests Release
   └─ POST /api/interception/release/<id>
   
2. Load Email from Database
   └─ SELECT * FROM email_messages WHERE id=<id>
   └─ Verify interception_status='HELD'
   
3. Decrypt Account Credentials
   └─ crypto.decrypt_credential(account.imap_password)
   
4. Connect to IMAP
   └─ imap_helpers._imap_connect_account(host, port, user, pass)
   
5. Reconstruct MIME Message
   ├─ If edited: Apply subject/body changes
   ├─ Preserve headers (Message-ID, Date, From, To)
   └─ Build new MIME message
   
6. APPEND to Mailbox
   └─ client.append(folder='INBOX', msg=<mime_bytes>, flags=['\\Seen'])
   └─ Preserve original INTERNALDATE if possible
   
7. Update Database
   └─ UPDATE email_messages SET
        interception_status='RELEASED',
        action_taken_at=datetime('now')
      WHERE id=<id>
   
8. Log Audit Trail
   └─ INSERT INTO audit_log (action='RELEASE', user_id=<admin_id>, target_id=<id>)
   
9. Return Success
   └─ {"ok": true, "released_to": "INBOX"}
```

#### **Dashboard Real-Time Updates (SSE)**
```
1. Browser Opens SSE Connection
   └─ const eventSource = new EventSource('/stream/stats');
   
2. Flask SSE Generator
   └─ @stats_bp.route('/stream/stats')
      def stream_stats():
          def generate():
              while True:
                  yield f"data: {json.dumps(get_current_stats())}\n\n"
                  time.sleep(2)
          return Response(generate(), mimetype='text/event-stream')
   
3. Stats Calculation (with caching)
   └─ Check cache (TTL=2s)
   ├─ If fresh: Return cached value
   └─ Else:
      ├─ Query database for counts
      ├─ Calculate latency metrics
      ├─ Update cache
      └─ Return new stats
   
4. Browser Receives Update
   └─ eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateDashboard(data);
      }
```

### 5.3 Key Design Patterns

#### **Singleton Pattern** - Flask Extensions
```python
# app/extensions.py
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter

csrf = CSRFProtect()  # Single instance
limiter = Limiter()   # Single instance

# simple_app.py
from app.extensions import csrf, limiter

csrf.init_app(app)
limiter.init_app(app)
```

#### **Repository Pattern** - Database Access
```python
# app/utils/db.py
def get_db():
    """Central database access point"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Usage in services
from app.utils.db import get_db

with get_db() as conn:
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM users").fetchall()
```

#### **Strategy Pattern** - Email Provider Detection
```python
# app/utils/email_helpers.py
def detect_email_settings(email_address):
    """Provider-specific configuration strategy"""
    domain = email_address.split('@')[-1].lower()
    
    # Strategy selection based on domain
    if domain == 'gmail.com':
        return GMAIL_SETTINGS
    elif 'hostinger' in domain or domain == 'corrinbox.com':
        return HOSTINGER_SETTINGS
    else:
        return generic_imap_settings(domain)

GMAIL_SETTINGS = {
    'imap_host': 'imap.gmail.com',
    'imap_port': 993,
    'smtp_host': 'smtp.gmail.com',
    'smtp_port': 587  # STARTTLS
}

HOSTINGER_SETTINGS = {
    'imap_host': 'imap.hostinger.com',
    'imap_port': 993,
    'smtp_host': 'smtp.hostinger.com',
    'smtp_port': 465  # SSL
}
```

#### **Observer Pattern** - SSE Event Streaming
```python
# Server-side (producer)
def stream_stats():
    def generate():
        while True:
            stats = get_current_stats()
            yield f"data: {json.dumps(stats)}\n\n"
            time.sleep(2)
    return Response(generate(), mimetype='text/event-stream')

# Client-side (observer)
const eventSource = new EventSource('/stream/stats');
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateDashboard(data);  // React to state changes
};
```

#### **Factory Pattern** - IMAP Watcher Creation
```python
# app/services/imap_watcher.py
@dataclass
class AccountConfig:
    imap_host: str
    imap_port: int
    username: str
    password: str
    # ...

class ImapWatcher:
    def __init__(self, config: AccountConfig):
        self.config = config
        self.client = None
    
    @classmethod
    def create_from_account_id(cls, account_id):
        """Factory method to create watcher from DB account"""
        with get_db() as conn:
            account = conn.execute("SELECT * FROM email_accounts WHERE id=?", (account_id,)).fetchone()
        
        config = AccountConfig(
            imap_host=account['imap_host'],
            imap_port=account['imap_port'],
            username=account['imap_username'],
            password=decrypt_credential(account['imap_password'])
        )
        return cls(config)
```

#### **Decorator Pattern** - Route Protection
```python
from functools import wraps
from flask_login import current_user
from flask import abort

def admin_required(f):
    """Decorator to restrict route to admin users"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/users')
@admin_required
def manage_users():
    # Only admins can access
```

### 5.4 Dependencies Between Modules

```
simple_app.py
├── app.routes.* (all blueprints)
│   ├── app.services.audit
│   ├── app.services.stats
│   ├── app.utils.db
│   ├── app.utils.crypto
│   └── app.models.simple_user
├── app.services.imap_watcher
│   ├── app.utils.db
│   ├── app.utils.crypto
│   ├── app.utils.imap_helpers
│   └── app.utils.rule_engine
├── app.workers.imap_startup
│   └── app.utils.db
└── app.extensions (csrf, limiter)

Shared Dependencies (used everywhere):
├── app.utils.db (database access)
├── app.utils.crypto (credential encryption)
└── app.utils.logging (application logging)
```

**Dependency Injection Pattern**:
```python
# Services receive dependencies as parameters
def start_imap_watcher_for_account(account_id: int, monitor_func: Callable):
    """Inject monitoring function for testability"""
    thread = threading.Thread(target=monitor_func, args=(account_id,), daemon=True)
    thread.start()
    return thread

# Testing with mock
def test_imap_watcher():
    mock_monitor = MagicMock()
    start_imap_watcher_for_account(1, mock_monitor)
    mock_monitor.assert_called_once_with(1)
```

---

## 6. Environment & Setup Analysis

### 6.1 Required Environment Variables

**Critical Variables**:
```bash
# Security (REQUIRED for production)
FLASK_SECRET_KEY=<32+ char random string>  # For session signing
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"

# Database
DATABASE_PATH=email_manager.db  # Default: email_manager.db

# Server Configuration
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=0  # NEVER set to 1 in production

# SMTP Proxy
SMTP_PROXY_HOST=127.0.0.1
SMTP_PROXY_PORT=8587

# IMAP Configuration
IMAP_ONLY=0  # Set to 1 to disable SMTP proxy (IMAP-only mode)
IMAP_IDLE_TIMEOUT=1500  # 25 minutes (max before server disconnect)
IMAP_IDLE_PING_INTERVAL=840  # 14 minutes (keepalive NOOP)
IMAP_MARK_SEEN_QUARANTINE=1  # Mark messages as read after quarantine

# Rate Limiting
RATELIMIT_STORAGE_URL=memory://  # Default: in-memory
# Production: RATELIMIT_STORAGE_URL=redis://localhost:6379
```

**Test Account Variables** (Development only - NEVER commit):
```bash
# Gmail Test Account
GMAIL_ADDRESS=ndayijecika@gmail.com
GMAIL_PASSWORD=<app-password-with-spaces>

# Hostinger Test Account
HOSTINGER_ADDRESS=mcintyre@corrinbox.com
HOSTINGER_PASSWORD=<password>

# Security
REQUIRE_LIVE_CREDENTIALS=0  # Set to 1 to enforce env credentials at startup
```

**Optional Variables**:
```bash
# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=logs/app.log

# Metrics
ENABLE_PROMETHEUS=0  # Set to 1 to enable /metrics endpoint

# Feature Flags
ENABLE_ATTACHMENT_STRIPPING=1
ENABLE_SIEVE_SUPPORT=0  # Deprecated
```

### 6.2 Installation Process

#### **Windows Installation**
```batch
REM 1. Prerequisites
REM    - Python 3.9+ installed
REM    - pip available in PATH

REM 2. Clone repository
git clone https://github.com/yourusername/Email-Management-Tool.git
cd Email-Management-Tool

REM 3. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

REM 4. Install dependencies
pip install -r requirements.txt

REM 5. Create configuration
copy .env.example .env
notepad .env  REM Edit with your settings

REM 6. Initialize database
python -c "from simple_app import init_database; init_database()"

REM 7. Run application
python simple_app.py

REM OR use launcher
EmailManager.bat
```

#### **Linux/Mac Installation**
```bash
# 1. Prerequisites
sudo apt-get install python3 python3-pip python3-venv  # Ubuntu/Debian
# OR
brew install python  # macOS

# 2. Clone repository
git clone https://github.com/yourusername/Email-Management-Tool.git
cd Email-Management-Tool

# 3. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create configuration
cp .env.example .env
nano .env  # Edit with your settings

# 6. Initialize database
python -c "from simple_app import init_database; init_database()"

# 7. Run application
python simple_app.py

# OR use launcher
./launch.sh
```

### 6.3 Development Workflow

#### **Local Development Setup**
```bash
# 1. Install dev dependencies
pip install -r requirements-dev.txt

# 2. Install pre-commit hooks
pre-commit install

# 3. Run in debug mode
export FLASK_DEBUG=1  # Linux/Mac
set FLASK_DEBUG=1     # Windows
python simple_app.py

# 4. Run tests with coverage
pytest tests/ -v --cov=app --cov-report=html

# 5. View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov\index.html  # Windows

# 6. Format code
black simple_app.py app/ tests/

# 7. Lint code
pylint simple_app.py app/

# 8. Type checking
mypy simple_app.py app/
```

#### **Database Migrations**
Since using raw SQLite (no ORM), migrations are manual:

```python
# scripts/migrate_add_column.py
import sqlite3

def migrate():
    conn = sqlite3.connect('email_manager.db')
    cursor = conn.cursor()
    
    # Add new column
    cursor.execute("ALTER TABLE email_messages ADD COLUMN reviewed_at TEXT")
    
    # Add index
    cursor.execute("CREATE INDEX idx_reviewed_at ON email_messages(reviewed_at)")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
```

#### **Testing Workflow**
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/routes/test_interception_release_flow.py -v

# Run tests with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run only unit tests (fast)
pytest tests/utils/ tests/services/ -v

# Run integration tests
pytest tests/routes/ -v

# Run live tests (requires credentials in .env)
pytest tests/live/ -v

# Watch mode (re-run on file changes)
pytest-watch tests/
```

### 6.4 Production Deployment Strategy

#### **Pre-Deployment Checklist**
- [ ] `FLASK_SECRET_KEY` set to strong random value (32+ chars)
- [ ] `FLASK_DEBUG=0` (disable debug mode)
- [ ] `WTF_CSRF_SSL_STRICT=True` (enforce HTTPS)
- [ ] Database backups enabled (automated daily)
- [ ] Encryption `key.txt` backed up securely
- [ ] Test accounts removed from `.env`
- [ ] Logs rotated (max 10MB, keep 5 files)
- [ ] Firewall configured (allow only 5000, 8587)
- [ ] SSL certificate configured (if public-facing)
- [ ] Rate limiting enabled (Redis recommended)
- [ ] Health check endpoint monitored (`/healthz`)

#### **Production Configuration**
```bash
# .env.production
FLASK_SECRET_KEY=<64-char-hex-from-secrets.token_hex(32)>
FLASK_DEBUG=0
FLASK_HOST=0.0.0.0  # Listen on all interfaces
FLASK_PORT=5000

# Use Redis for rate limiting
RATELIMIT_STORAGE_URL=redis://localhost:6379

# Strict security
WTF_CSRF_SSL_STRICT=True
WTF_CSRF_TIME_LIMIT=7200  # 2 hours

# No test credentials
# GMAIL_ADDRESS and HOSTINGER_ADDRESS should be removed
```

#### **Windows Service Installation**
```powershell
# Run as Administrator
.\manage.ps1 install

# Service will:
# - Start on boot
# - Auto-restart on failure
# - Run as NETWORK SERVICE
# - Log to Windows Event Log
```

#### **Monitoring & Health Checks**
```bash
# Health check endpoint
curl http://localhost:5000/healthz

# Expected response:
{
  "ok": true,
  "held_count": 5,
  "released_24h": 42,
  "median_latency_ms": 187,
  "workers": [
    {"worker": "acct-1", "last_heartbeat_sec": 3.14, "status": "ok"}
  ],
  "timestamp": "2025-10-18T12:00:00Z"
}

# Set up monitoring (e.g., Prometheus + Grafana)
# 1. Enable Prometheus metrics
export ENABLE_PROMETHEUS=1

# 2. Scrape /metrics endpoint
curl http://localhost:5000/metrics
```

---

## 7. Technology Stack Breakdown

### 7.1 Runtime Environment
- **Python 3.9+** (tested on 3.13)
  - Type hints throughout (PEP 484, 526)
  - Async support (asyncio for SMTP proxy)
  - Standard library: sqlite3, threading, email, smtplib, imaplib

### 7.2 Web Framework & Extensions
| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.0+ | WSGI web framework |
| Werkzeug | 3.0.1+ | WSGI utility library |
| Jinja2 | (via Flask) | Template engine |
| Flask-Login | 0.6.3+ | Session management |
| Flask-WTF | 1.2.1+ | CSRF protection |
| Flask-Limiter | 3.5.0+ | Rate limiting |

### 7.3 Database & Storage
- **SQLite 3**: Embedded SQL database
  - **WAL mode**: Write-Ahead Logging for concurrency
  - **Busy timeout**: 10s to handle lock contention
  - **Row factory**: Dict-like row access
  - **Indices**: 8 performance indices (see Database Schema)

### 7.4 Email Processing
| Package | Version | Purpose |
|---------|---------|---------|
| aiosmtpd | 1.4.4.post2 | SMTP proxy server (async) |
| imapclient | 3.0.0+ | IMAP client library |
| email | (stdlib) | MIME parsing/generation |
| python-dateutil | 2.8.2+ | Email date parsing |

### 7.5 Security & Encryption
| Package | Version | Purpose |
|---------|---------|---------|
| cryptography | 41.0.7+ | Fernet symmetric encryption |
| werkzeug.security | (via Werkzeug) | bcrypt password hashing |
| python-dotenv | 1.0.0+ | Environment variable loading |

### 7.6 Testing Framework
| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 7.4.3+ | Test framework |
| pytest-flask | 1.3.0+ | Flask testing utilities |
| pytest-asyncio | 0.21.1+ | Async test support |
| faker | 20.1.0+ | Test data generation |
| pytest-cov | (plugin) | Coverage reporting |

### 7.7 Development Tools
| Package | Version | Purpose |
|---------|---------|---------|
| black | 23.12.0+ | Code formatter |
| pylint | 3.0.3+ | Static analysis |
| mypy | 1.7.1+ | Type checking |
| pre-commit | 3.6.0+ | Git hooks |

### 7.8 Frontend Technologies
- **Bootstrap 5.3**: UI framework (CDN)
- **Vanilla JavaScript**: ES6+ (no framework)
  - EventSource API (SSE)
  - Fetch API (AJAX)
  - Bootstrap Toast API
- **HTML5**: Semantic markup
- **CSS3**: Custom properties, flexbox, grid

### 7.9 Deployment Technologies
- **Windows Batch Scripts**: `.bat` launchers
- **PowerShell**: `manage.ps1` automation
- **Bash Scripts**: Linux/Mac support
- **systemd** (Linux): Service management
- **Windows Services**: Production deployment

---

## 8. Visual Architecture Diagram (ASCII)

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            EMAIL MANAGEMENT TOOL                          │
│                        Interception & Moderation Gateway                  │
└───────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  CLIENT LAYER                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐         ┌─────────────────────────────────────┐   │
│  │  Email Client       │         │  Web Browser                        │   │
│  │  (Outlook, etc.)    │         │  (Chrome, Firefox, Edge)            │   │
│  │                     │         │                                     │   │
│  │  SMTP Config:       │         │  URL: http://localhost:5000         │   │
│  │  Host: localhost    │         │  Login: admin / admin123            │   │
│  │  Port: 8587         │         │                                     │   │
│  └──────────┬──────────┘         └──────────────┬──────────────────────┘   │
│             │                                    │                          │
└─────────────┼────────────────────────────────────┼──────────────────────────┘
              │                                    │
              │ SMTP Protocol                      │ HTTP/HTTPS
              ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NETWORK LAYER                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────┐   ┌─────────────────────────────────────┐ │
│  │  SMTP Proxy Server          │   │  Flask HTTP Server                  │ │
│  │  (aiosmtpd)                 │   │  (Werkzeug/WSGI)                    │ │
│  │                             │   │                                     │ │
│  │  Bind: 127.0.0.1:8587       │   │  Bind: 127.0.0.1:5000               │ │
│  │  Handler: async def         │   │  App: Flask(__name__)               │ │
│  │    handle_DATA()            │   │  Debug: False (production)          │ │
│  │                             │   │                                     │ │
│  │  Thread: smtp_thread        │   │  Extensions:                        │ │
│  │  Daemon: True               │   │  - CSRFProtect()                    │ │
│  └──────────┬──────────────────┘   │  - Limiter(5/min login)             │ │
│             │                      │  - LoginManager()                   │ │
│             │ Intercept            └──────────────┬──────────────────────┘ │
└─────────────┼───────────────────────────────────┼──────────────────────────┘
              │                                    │
              │ Parse & store                      │ Route dispatch
              ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  APPLICATION LAYER                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  BLUEPRINTS (Route Handlers)                                        │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────┐ ┌─────────────────┐  │   │
│  │  │  auth    │ │ dashboard │ │ interception │ │     emails      │  │   │
│  │  │  /login  │ │ /dashboard│ │ /api/inter-  │ │  /emails        │  │   │
│  │  │ /logout  │ │ /dash/<t> │ │  ception/*   │ │  /email/<id>    │  │   │
│  │  └──────────┘ └───────────┘ └──────────────┘ └─────────────────┘  │   │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────┐ ┌─────────────────┐  │   │
│  │  │ accounts │ │  compose  │ │    inbox     │ │   moderation    │  │   │
│  │  │ /accounts│ │ /compose  │ │  /inbox      │ │  /rules         │  │   │
│  │  │ /accts/+ │ │ (POST)    │ │              │ │  (admin only)   │  │   │
│  │  └──────────┘ └───────────┘ └──────────────┘ └─────────────────┘  │   │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────┐ ┌─────────────────┐  │   │
│  │  │  stats   │ │diagnostics│ │   legacy     │ │   styleguide    │  │   │
│  │  │/api/stats│ │  /test/*  │ │/api/events   │ │  /styleguide    │  │   │
│  │  │/stream/* │ │           │ │(redirects)   │ │  (UI docs)      │  │   │
│  │  └──────────┘ └───────────┘ └──────────────┘ └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SERVICES (Business Logic)                                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────────────┐  │   │
│  │  │   audit.py  │ │   stats.py   │ │    imap_watcher.py          │  │   │
│  │  │             │ │              │ │    (920 lines)              │  │   │
│  │  │ log_action()│ │ TTL caching  │ │ ┌─────────────────────────┐ │  │   │
│  │  │ get_logs()  │ │ (2s-5s)      │ │ │ class ImapWatcher:      │ │  │   │
│  │  │             │ │              │ │ │   run_forever()         │ │  │   │
│  │  └─────────────┘ └──────────────┘ │ │   _watch_inbox()        │ │  │   │
│  │                                    │ │   _intercept_message()  │ │  │   │
│  │  ┌─────────────────────────────┐  │ │                         │ │  │   │
│  │  │  interception/              │  │ │ IDLE + polling hybrid   │ │  │   │
│  │  │  - rapid_imap_copy_purge.py │  │ │ Auto-reconnect          │ │  │   │
│  │  │  - release_editor.py        │  │ │ Circuit breaker         │ │  │   │
│  │  └─────────────────────────────┘  │ └─────────────────────────┘ │  │   │
│  │                                    └─────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  UTILITIES (Shared Functions)                                       │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌─────────────────┐    │   │
│  │  │  db.py   │ │crypto.py │ │email_helpers │ │  rule_engine    │    │   │
│  │  │          │ │          │ │              │ │                 │    │   │
│  │  │get_db()  │ │Fernet    │ │detect_email_ │ │evaluate_rules() │    │   │
│  │  │context   │ │encrypt() │ │  settings()  │ │risk_score()     │    │   │
│  │  │manager   │ │decrypt() │ │test_conn()   │ │                 │    │   │
│  │  └──────────┘ └──────────┘ └──────────────┘ └─────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PERSISTENCE LAYER                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SQLite Database (email_manager.db)                                 │   │
│  │  WAL Mode | 10s busy_timeout | Row Factory                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  Tables:                                                            │   │
│  │  ┌─────────────────┐ ┌────────────────┐ ┌──────────────────────┐  │   │
│  │  │ users           │ │ email_accounts │ │ email_messages       │  │   │
│  │  │ - id            │ │ - id           │ │ - id                 │  │   │
│  │  │ - username      │ │ - email_addr   │ │ - message_id         │  │   │
│  │  │ - password_hash │ │ - imap_host    │ │ - sender             │  │   │
│  │  │ - role          │ │ - imap_pass    │ │ - recipients         │  │   │
│  │  │                 │ │   (encrypted)  │ │ - subject            │  │   │
│  │  │ Default:        │ │ - smtp_host    │ │ - body_text          │  │   │
│  │  │ admin/admin123  │ │ - smtp_pass    │ │ - raw_content        │  │   │
│  │  │                 │ │   (encrypted)  │ │ - status             │  │   │
│  │  │                 │ │ - is_active    │ │ - interception_status│  │   │
│  │  │                 │ │                │ │ - risk_score         │  │   │
│  │  │                 │ │                │ │ - latency_ms         │  │   │
│  │  └─────────────────┘ └────────────────┘ └──────────────────────┘  │   │
│  │                                                                    │   │
│  │  ┌──────────────────┐ ┌──────────────┐                           │   │
│  │  │ moderation_rules │ │  audit_log   │                           │   │
│  │  │ - id             │ │  - id        │                           │   │
│  │  │ - rule_name      │ │  - action    │                           │   │
│  │  │ - keyword        │ │  - user_id   │                           │   │
│  │  │ - action         │ │  - target_id │                           │   │
│  │  │ - priority       │ │  - details   │                           │   │
│  │  │ - is_active      │ │  - timestamp │                           │   │
│  │  └──────────────────┘ └──────────────┘                           │   │
│  │                                                                    │   │
│  │  Indices (8 total):                                                │   │
│  │  - idx_email_messages_status                                       │   │
│  │  - idx_email_messages_interception_status                          │   │
│  │  - idx_email_messages_msgid_unique (UNIQUE)                        │   │
│  │  - idx_email_messages_account_status (composite)                   │   │
│  │  - idx_email_messages_original_uid                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Encryption Key (key.txt)                                           │   │
│  │  Fernet AES-128-CBC + HMAC-SHA256                                   │   │
│  │  GITIGNORED - Never commit!                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Raw Email Files (data/inbound_raw/)                                │   │
│  │  *.eml files (RFC822 format)                                        │   │
│  │  Referenced by email_messages.raw_path                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKGROUND WORKERS                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  IMAP Watcher Threads (one per active account)                      │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  Thread 1 (Gmail):                                                  │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │  imap_watcher = ImapWatcher(gmail_config)                     │  │   │
│  │  │  imap_watcher.run_forever()                                   │  │   │
│  │  │                                                               │  │   │
│  │  │  Loop:                                                         │  │   │
│  │  │  1. Connect: imap.gmail.com:993                               │  │   │
│  │  │  2. SELECT INBOX                                              │  │   │
│  │  │  3. IDLE (25 min timeout)                                     │  │   │
│  │  │  4. On EXISTS notification:                                   │  │   │
│  │  │     - FETCH new UID                                           │  │   │
│  │  │     - Evaluate rules                                          │  │   │
│  │  │     - If should_hold:                                         │  │   │
│  │  │       * COPY to Quarantine                                    │  │   │
│  │  │       * EXPUNGE from INBOX                                    │  │   │
│  │  │       * Store in DB (HELD)                                    │  │   │
│  │  │  5. NOOP keepalive (14 min)                                   │  │   │
│  │  │  6. On error: Backoff 5s→30s, reconnect                       │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │                                                                     │   │
│  │  Thread 2 (Hostinger): [Same structure]                            │   │
│  │  Thread N: [One per active account]                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SMTP Proxy Thread                                                  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  smtp_thread = threading.Thread(target=run_smtp_proxy, daemon=True) │   │
│  │                                                                     │   │
│  │  aiosmtpd.controller.Controller:                                    │   │
│  │  - Handler: EmailModerationHandler                                 │   │
│  │  - Hostname: 127.0.0.1                                              │   │
│  │  - Port: 8587                                                       │   │
│  │                                                                     │   │
│  │  async def handle_DATA(envelope):                                   │   │
│  │  1. Parse MIME message                                              │   │
│  │  2. Evaluate rules (keywords, risk_score)                           │   │
│  │  3. Store in DB (direction='outbound', status='PENDING')            │   │
│  │  4. Return '250 Message accepted'                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL SERVICES                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────────┐   ┌─────────────────────────────────┐  │
│  │  Gmail IMAP/SMTP               │   │  Hostinger IMAP/SMTP            │  │
│  ├────────────────────────────────┤   ├─────────────────────────────────┤  │
│  │  IMAP:                         │   │  IMAP:                          │  │
│  │  - imap.gmail.com:993 (SSL)    │   │  - imap.hostinger.com:993 (SSL) │  │
│  │  - Credentials: App Password   │   │  - Credentials: Email password  │  │
│  │  - Folders: INBOX, Quarantine  │   │  - Folders: INBOX, Quarantine   │  │
│  │                                │   │                                 │  │
│  │  SMTP:                         │   │  SMTP:                          │  │
│  │  - smtp.gmail.com:587          │   │  - smtp.hostinger.com:465       │  │
│  │  - STARTTLS                    │   │  - SSL (direct)                 │  │
│  │                                │   │                                 │  │
│  │  Test Account:                 │   │  Test Account:                  │  │
│  │  ndayijecika@gmail.com         │   │  mcintyre@corrinbox.com         │  │
│  └────────────────────────────────┘   └─────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA FLOW EXAMPLES                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INBOUND INTERCEPTION:                                                      │
│  Gmail Server → IMAP Watcher → Quarantine → DB (HELD) → Dashboard          │
│                                                                             │
│  OUTBOUND INTERCEPTION:                                                     │
│  Email Client → SMTP Proxy → Parse → Evaluate → DB (HELD) → Dashboard      │
│                                                                             │
│  EMAIL RELEASE:                                                             │
│  Dashboard → POST /api/interception/release → Reconstruct MIME →            │
│  IMAP APPEND to INBOX → Update DB (RELEASED) → Audit Log                   │
│                                                                             │
│  REAL-TIME STATS:                                                           │
│  Dashboard → SSE /stream/stats → stats.py (cache) → DB query →             │
│  JSON response → EventSource.onmessage → Update UI                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Key Insights & Recommendations

### 9.1 Code Quality Assessment

**Strengths**:
✅ **Modular Architecture**: Blueprint-based routing with clear separation of concerns
✅ **Comprehensive Testing**: 138/138 tests passing (36% coverage)
✅ **Security-Conscious**: CSRF protection, rate limiting, encrypted credentials
✅ **Production-Ready**: Pre-commit hooks, type hints, logging, error handling
✅ **Well-Documented**: 30+ markdown docs, inline comments, docstrings
✅ **Clean Dependencies**: Removed 20+ unused packages (was bloated, now lean)

**Areas for Improvement**:
⚠️ **Test Coverage**: 36% is good, but target should be 50%+ (add more integration tests)
⚠️ **Type Hints**: Inconsistent (some functions lack type annotations)
⚠️ **Error Messages**: Some user-facing errors could be more helpful
⚠️ **Logging**: Debug logs sometimes too verbose in production

### 9.2 Potential Improvements

#### **High Priority**
1. **Increase Test Coverage to 50%+**
   - Add integration tests for all blueprints
   - Test error paths and edge cases
   - Mock external IMAP/SMTP connections

2. **Add API Authentication** (JWT or API keys)
   - Currently only session-based auth
   - Enable programmatic access for automation

3. **Implement Database Migrations**
   - Use Alembic or custom migration framework
   - Version schema changes for easier upgrades

4. **Add Prometheus Metrics**
   - Already implemented but disabled by default
   - Enable with `ENABLE_PROMETHEUS=1`

#### **Medium Priority**
5. **Redis Backend for Rate Limiting**
   - In-memory limiter doesn't survive restarts
   - Use Redis for distributed rate limiting

6. **Email Search/Filtering**
   - Currently client-side only
   - Add server-side full-text search (SQLite FTS5)

7. **Attachment Preview**
   - Show attachment previews (images, PDFs)
   - Virus scanning integration (ClamAV)

8. **Batch Operations**
   - Select multiple emails for bulk release/discard
   - Improve UX for high-volume users

#### **Low Priority**
9. **Email Templates**
   - Predefined templates for common replies
   - Variable substitution

10. **Multi-User Support**
    - Currently single admin account
    - Add user roles (admin, moderator, viewer)

### 9.3 Security Considerations

**Current Security Posture**: ✅ **GOOD**
- ✅ CSRF protection enabled (Flask-WTF)
- ✅ Rate limiting on login (5/minute)
- ✅ Strong SECRET_KEY enforcement (production)
- ✅ Encrypted credentials at rest (Fernet)
- ✅ bcrypt password hashing (Werkzeug)
- ✅ SQL injection prevention (parameterized queries)
- ✅ Audit logging (all actions tracked)

**Security Recommendations**:
1. **HTTPS Enforcement** (Currently HTTP)
   - Use reverse proxy (nginx/Apache) with SSL
   - Set `WTF_CSRF_SSL_STRICT=True`

2. **Secure key.txt Backup**
   - If lost, all encrypted credentials are unrecoverable
   - Implement key rotation strategy

3. **Session Timeout**
   - Add `PERMANENT_SESSION_LIFETIME` config
   - Auto-logout after inactivity

4. **Input Validation**
   - Add stricter email address validation
   - Sanitize HTML in email bodies (bleach)

5. **Security Headers**
   - Add CSP, X-Frame-Options, HSTS
   - Use Flask-Talisman extension

### 9.4 Performance Optimization Opportunities

**Current Performance**: ✅ **GOOD**
- ✅ Database indices for fast queries
- ✅ Stats caching (2s-5s TTL)
- ✅ WAL mode for concurrent access
- ✅ SSE for push updates (no polling)

**Optimization Ideas**:
1. **Connection Pooling**
   - SQLite doesn't support pooling well
   - Consider PostgreSQL for high concurrency

2. **Async IMAP Operations**
   - Use aioimaplib for async IMAP
   - Parallelize multi-account monitoring

3. **CDN for Static Assets**
   - Serve Bootstrap/JS from CDN
   - Add cache headers

4. **Database Partitioning**
   - Archive old emails to separate table
   - Keep email_messages table lean

### 9.5 Maintainability Suggestions

**Current Maintainability**: ✅ **EXCELLENT**
- ✅ Clear file organization
- ✅ Comprehensive documentation
- ✅ Pre-commit hooks for consistency
- ✅ Type hints for IDE support

**Enhancement Ideas**:
1. **Add CHANGELOG.md**
   - Track version history
   - Document breaking changes

2. **Automated Dependency Updates**
   - Use Dependabot or Renovate
   - Keep dependencies current

3. **API Documentation**
   - Use Swagger/OpenAPI spec
   - Auto-generate from Flask routes

4. **Developer Onboarding Guide**
   - Step-by-step setup
   - Architecture walkthrough
   - Common tasks reference

### 9.6 Scalability Path

**Current Scale**: ✅ **GOOD** (handles 1000+ emails/hour)
- ✅ SQLite suitable for <100GB database
- ✅ Single-server architecture
- ✅ Thread-based concurrency

**Scaling Recommendations**:
- **Vertical Scaling**: Increase server CPU/RAM (easy)
- **Horizontal Scaling**: Requires architectural changes:
  1. Move to PostgreSQL (multi-reader support)
  2. Separate IMAP watchers into worker pool
  3. Use message queue (Celery + Redis)
  4. Load balance Flask instances (nginx)
  5. Shared session storage (Redis)

---

## 10. Conclusion

**Email Management Tool** is a **mature, production-ready application** with:
- ✅ Clean modular architecture (Blueprint-based)
- ✅ Comprehensive security (CSRF, rate limiting, encryption)
- ✅ Robust testing (138/138 tests passing)
- ✅ Excellent documentation (30+ markdown files)
- ✅ Lean dependencies (removed 20+ unused packages)

**Recommended Next Steps**:
1. **Increase test coverage** from 36% to 50%+
2. **Add API authentication** for programmatic access
3. **Enable HTTPS** with reverse proxy
4. **Implement database migrations** for easier upgrades
5. **Add Prometheus metrics** for production monitoring

**Overall Assessment**: ⭐⭐⭐⭐⭐ **5/5** - Well-architected, maintainable, production-ready

---

**Document End**
