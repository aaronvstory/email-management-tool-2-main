# Development Guide

## Prerequisites

- **Python**: 3.9+ (tested with 3.13)
- **Operating System**: Windows (batch scripts, path conventions)
- **Network**: Local SMTP/IMAP access (no firewall blocking ports 8587, 465, 587, 993)
- **Email Accounts**: Gmail App Passwords or provider-specific app passwords
- **Optional**: Modern browser (Chrome/Firefox/Edge) for dashboard

## Quick Start Commands

### Restarting After Port Conflicts

```bash
# Automatic cleanup and restart (recommended)
python cleanup_and_start.py

# Manual cleanup
tasklist | findstr python.exe
taskkill /F /PID <pid>
python simple_app.py
```

### Starting the Application

```bash
# Recommended: Professional launcher with menu
EmailManager.bat

# Quick start (auto-opens browser)
launch.bat

# Direct Python execution
python simple_app.py
```

**Access Points**:
- Web Dashboard: http://localhost:5001
- SMTP Proxy: localhost:8587
- Default Login: `admin` / `admin123`

## Development Commands

### Running Tests

```bash
# Fast, targeted path (recommended for local)
python -m pytest tests/test_intercept_flow.py -v

# Full suite (pending migration; may include quarantined tests)
python -m pytest tests/ -v --tb=short

# Test specific file
python -m pytest tests/test_intercept_flow.py -v

# Test single function
python -m pytest tests/test_intercept_flow.py::test_fetch_stores_uid_and_internaldate -v

# Run with detailed output
python -m pytest tests/ -v --tb=short

# Exclude broken imports (until Phase 1B migration complete)
python -m pytest tests/ -v --ignore=tests/integration --ignore=tests/performance --ignore=tests/unit/backend/test_smtp_proxy.py --ignore=tests/unit/test_account_management.py
```

### Database Operations

```bash
# Check schema
python -c "import sqlite3; conn = sqlite3.connect('email_manager.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(email_messages)'); print(cursor.fetchall())"

# Verify indices (Phase 0 DB Hardening)
python scripts/verify_indices.py

# Run migrations
python scripts/migrations/20251001_add_interception_indices.py

# Test account connections
python scripts/test_permanent_accounts.py  # No DB modification
python scripts/verify_accounts.py         # Check DB config
```

### Linting & Quality

```bash
# Format
black .

# Lint
pylint app simple_app.py

# Type check
mypy .
# (Optional) Pyright if installed
# pyright
```

## Development Workflow

### Adding New Features

1. **Consult docs/STYLEGUIDE.md first** if adding UI components
2. Update database schema if needed (with migration check)
3. Add route handler in `simple_app.py` or create blueprint
4. Create/update Jinja2 template in `templates/`
   - Use `.input-modern` for all inputs
   - Use gradient backgrounds for cards
   - Maintain dark theme consistency
5. Add JavaScript if interactive (inline in template)
   - Use Bootstrap 5.3 modal patterns
   - Include error handling with try-catch
   - **Use toast notifications** (see Toast Notifications section below for details)
6. Test UI checklist (see below)
7. Update this documentation

### Template Variable Injection

**Flask Context Processor** (lines 363-376 in simple_app.py):
All templates automatically receive `pending_count` for the navigation badge:

```python
@app.context_processor
def inject_pending_count():
    """Inject pending_count into all templates for the badge in navigation"""
    try:
        if current_user.is_authenticated:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            pending_count = cursor.execute("SELECT COUNT(*) FROM email_messages WHERE status = 'PENDING'").fetchone()[0]
            conn.close()
            return {'pending_count': pending_count}
    except:
        pass
    return {'pending_count': 0}
```

**Why This Matters**: All templates extending `base.html` need `pending_count` for the sidebar badge. The context processor automatically provides this, so individual routes don't need to pass it.

### Database Migrations

```python
# Always check for column existence first
cursor.execute('PRAGMA table_info(email_messages)')
columns = [col[1] for col in cursor.fetchall()]
if 'new_field' not in columns:
    cursor.execute('ALTER TABLE email_messages ADD COLUMN new_field TEXT')
    conn.commit()
```

### Database Access Pattern

**CRITICAL**: Always use `row_factory` for dict-like access:

```python
from app.utils.db import get_db

with get_db() as conn:
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM email_messages WHERE status=?", ('PENDING',)).fetchall()
    for row in rows:
        print(row['subject'])  # Dict access, not row[2]
```

## UI Development Guidelines

### Critical Requirements

**⚠️ ALWAYS consult `docs/STYLEGUIDE.md` before making ANY UI changes!**

### Common UI Patterns

**Input Fields**:
```html
<!-- Use .input-modern class for all inputs -->
<input type="text" class="input-modern" placeholder="Enter text..." />
<select class="input-modern">
  ...
</select>
<textarea class="input-modern" rows="5"></textarea>
```

**Buttons**:
```html
<!-- Standard button (42px height) -->
<button class="btn-modern btn-primary-modern">Action</button>
<button class="action-btn primary">Primary Action</button>

<!-- Small button (34px height) -->
<button class="btn-sm">Small Action</button>
```

**Cards**:
```html
<!-- Use gradient backgrounds -->
<div
  style="background: linear-gradient(145deg, #1a1a1a 0%, #1f1f1f 60%, #242424 100%);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 18px;
            padding: 20px;"
>
  Card content
</div>
```

**Toast Notifications** (NEW - v2.3):

```javascript
// Success notification (green)
showSuccess("Operation completed successfully");

// Error notification (red)
showError("Failed to process request");

// Warning notification (orange)
showWarning("Please select an account first");

// Info notification (blue)
showInfo("Processing your request...");

// Confirmation for critical actions (orange with Cancel/Confirm)
confirmToast(
  "Permanently discard this email?",
  () => {
    // User confirmed - execute action
    deleteEmail(id);
  },
  () => {
    // User cancelled (optional callback)
  }
);
```

**Toast Features**:
- Auto-dismiss after 4-5 seconds (configurable)
- Manual close button always available
- Top-right positioning with slide-in animation
- Dark theme matching docs/STYLEGUIDE.md
- Non-blocking user experience
- Only use `confirmToast()` for destructive actions (delete, discard)

**Modals**:
```html
<!-- Dark themed modal with red gradient header -->
<div
  class="modal-content"
  style="background: linear-gradient(145deg, #1a1a1a 0%, #1f1f1f 60%, #242424 100%);"
>
  <div
    class="modal-header"
    style="background: linear-gradient(135deg, #dc2626 0%, #991b1b 50%, #7f1d1d 100%);"
  >
    <h5 class="modal-title text-white">Title</h5>
  </div>
  <div class="modal-body" style="color: #fff;">Content</div>
</div>
```

### UI Testing Checklist

Before committing UI changes:

- [ ] Dark theme consistency maintained (no white backgrounds unless intentional)
- [ ] All inputs use `.input-modern` class or similar dark styling
- [ ] Buttons are consistent height (42px standard, 34px small, 50px large)
- [ ] Cards use gradient backgrounds, not solid colors
- [ ] Text is readable (white on dark, proper contrast)
- [ ] Hover states work and match theme
- [ ] Background doesn't show white on scroll (`background-attachment: fixed`)
- [ ] Modals use dark backgrounds with gradient headers
- [ ] **Toast notifications used** (not browser alerts) for all user feedback
- [ ] Responsive design tested (desktop, tablet, mobile)

## AI-Assisted Development with MCP Servers

This project leverages **Model Context Protocol (MCP)** servers for enhanced development capabilities. MCP provides specialized tools for code intelligence, file operations, research, and more.

### Active MCP Servers

**Primary Development Tools**:

1. **Serena** - Semantic Python code intelligence
   - **Dashboard**: http://127.0.0.1:24282/dashboard/index.html
   - **Capabilities**: Symbol-aware navigation, safe refactoring, dependency tracking
   - **When to use**: Finding functions/classes, analyzing imports, project-wide changes

2. **Desktop Commander** - File system and process management
   - **Capabilities**: File operations, directory search, process management, bulk operations
   - **When to use**: File I/O, search across files, system diagnostics

3. **Memory** - Knowledge graph for persistent project context
   - **Capabilities**: Store findings, create relationships, retrieve past learnings
   - **When to use**: Documenting complex decisions, tracking architectural patterns

4. **Sequential Thinking** - Complex multi-step analysis
   - **Capabilities**: Structured problem-solving, chain-of-thought reasoning
   - **When to use**: Debugging complex issues, planning refactorings

5. **Context7** - Library documentation lookup
   - **Capabilities**: Official docs for Flask, pytest, SQLite, etc.
   - **When to use**: Questions about library usage, best practices, API references

6. **Exa/Perplexity** - Web research and current information
   - **Capabilities**: Real-time web search, current best practices
   - **When to use**: New patterns, recent vulnerability info, latest framework features

**Disabled Servers** (to save 46k context tokens):
- ❌ **chrome-devtools** - Browser automation (enable manually when needed for E2E testing)
- ❌ **shadcn-ui** - React components (not applicable to Flask/Jinja2 project)

### `/sp` Command - SuperPower Orchestration

**Primary command** for intelligent task orchestration across all MCP servers.

```bash
/sp [task description]
```

**How it works**:
- Analyzes your task and automatically selects optimal MCP servers
- Spawns expert sub-agents for complex tasks
- Coordinates between servers intelligently
- Caches research findings to `.claude/research/` for reuse
- 87% token reduction through intelligent caching

### Usage Examples

#### Code Analysis with Serena

```bash
# Find all references to a function
/sp find all places where encrypt_credential is called

# Analyze SMTP authentication flow
/sp analyze the SMTP proxy authentication flow in simple_app.py

# Refactor with safety
/sp refactor IMAP watcher to use better error handling with backoff
```

**What happens**:
- Serena MCP activates automatically
- Symbol-aware search finds exact function references (not just text search)
- Shows call sites with context and file locations
- Suggests safe refactoring approaches

#### File Operations with Desktop Commander

```bash
# Search across all Python files
/sp find all SQL queries and check for injection risks

# Bulk file operations
/sp rename all test files from test_*.py to *_test.py format

# System diagnostics
/sp check why port 8587 is already in use
```

**What happens**:
- Desktop Commander handles file system operations
- Efficient pattern matching across large codebases
- Process management for system-level issues

#### Research with Context7 and Exa

```bash
# Library documentation
/sp how do I use pytest fixtures for Flask app testing?

# Best practices research
/sp what are current best practices for SQLite connection pooling in Flask?

# Security patterns
/sp find recent Flask CSRF protection patterns for AJAX requests
```

**What happens**:
- Context7 fetches official pytest/Flask documentation
- Exa searches for recent blog posts and patterns
- Synthesizes information from multiple sources
- Provides code examples with explanations

#### Complex Analysis with Sequential Thinking

```bash
# Multi-step debugging
/sp why are emails stuck in PENDING status after IMAP fetch?

# Performance analysis
/sp analyze database query performance and suggest optimizations

# Security audit
/sp comprehensive security review of authentication system
```

**What happens**:
- Sequential Thinking breaks down complex problems
- Coordinates with Serena (code analysis) + Desktop Commander (logs)
- Systematic investigation with hypothesis testing
- Detailed report with evidence and recommendations

#### Project-Wide Changes

```bash
# Safe refactoring
/sp add comprehensive logging to interception.py with proper error handling

# Feature addition
/sp add rate limiting to email release endpoint in interception.py

# Migration tasks
/sp update all database queries to use proper parameterization
```

**What happens**:
- Serena finds all affected code locations
- Desktop Commander handles file operations
- Memory stores the refactoring plan
- Changes applied with validation

### MCP Server Selection Guide

**Choose the right server for your task**:

| Task Type | Primary Server | Secondary | Example |
|-----------|---------------|-----------|---------|
| Find function/class | Serena | - | "Find all uses of decrypt_credential" |
| Refactor code | Serena | Memory | "Rename User to SimpleUser everywhere" |
| Search files | Desktop Commander | - | "Find all TODO comments in Python files" |
| Library questions | Context7 | Exa | "How to use pytest-asyncio?" |
| Debug complex issue | Sequential Thinking | Serena | "Why is IMAP watcher disconnecting?" |
| Research patterns | Exa/Perplexity | Context7 | "Best practices for email threading" |
| System diagnostics | Desktop Commander | - | "Why is port 5001 in use?" |

### Tips for Effective MCP Usage

**1. Be specific in task descriptions**:
```bash
# ✅ Good
/sp add type hints to app/utils/crypto.py functions

# ❌ Too vague
/sp improve the code
```

**2. Use natural language**:
```bash
# ✅ Good
/sp find all places where we call IMAP MOVE command

# ❌ Overly technical
/sp grep -r "MOVE" --include="*.py" | xargs
```

**3. Trust intelligent routing**:
- No need to specify which MCP server to use
- `/sp` automatically detects the best tool for your task
- Servers work together when needed (e.g., Serena + Desktop Commander for refactoring)

**4. Leverage caching**:
- Research findings saved to `.claude/research/`
- Reuse previous analysis for similar tasks
- Faster responses for repeated patterns

### Example Workflows

#### Adding a New Feature

```bash
# 1. Research the pattern
/sp find similar implementations of rate limiting in the codebase

# 2. Plan the implementation
/sp outline implementation plan for adding email attachment scanning

# 3. Implement with validation
/sp add attachment scanning to email processing pipeline with tests

# 4. Verify integration
/sp verify attachment scanning integrates correctly with SMTP proxy
```

#### Debugging an Issue

```bash
# 1. Understand the problem
/sp analyze why emails are not being released from HELD status

# 2. Find related code
/sp find all code paths that update email status to RELEASED

# 3. Check for issues
/sp check for race conditions in email status transitions

# 4. Propose fix
/sp suggest fix for status transition race condition with proper locking
```

#### Code Quality Improvements

```bash
# 1. Security scan
/sp scan for SQL injection vulnerabilities in database queries

# 2. Performance analysis
/sp identify slow database queries and suggest indices

# 3. Type safety
/sp add type hints to all functions in app/routes/ directory

# 4. Documentation
/sp generate docstrings for all public functions in app/services/
```

### Serena Dashboard

**Access**: http://127.0.0.1:24282/dashboard/index.html

**Features**:
- Visual code dependency graph
- Symbol hierarchy browser
- Find references across project
- Safe rename refactoring

**When to use directly**:
- Exploring large codebases visually
- Understanding module relationships
- Planning complex refactorings

**Note**: `/sp` command automatically uses Serena's capabilities - dashboard is optional for visual exploration.

### Context Optimization

**Token usage optimized** (2025-10-18):
- SuperClaude framework: Archived (saves 24.8k tokens)
- MCP tools: 53.6k tokens (chrome-devtools and shadcn-ui disabled)
- Context usage: 122k/200k (61%) with 78k free space

**Why this matters**:
- More room for code context in conversations
- Faster response times
- Only essential tools loaded by default
- Enable optional servers when needed via `/mcp` command

## Testing Strategy

### Test Structure

```
tests/
├── conftest.py                    # Pytest configuration
├── test_unified_stats.py          # Dashboard stats (2 tests, all pass)
├── test_latency_stats.py          # Latency metrics (4 tests, 2 pass in suite)
├── test_intercept_flow.py         # Interception lifecycle (3 tests, all pass) ✅ NEW
└── TEST_ISOLATION_STATUS.md       # Known test limitations
```

### Test Coverage
- ✅ **Interception Lifecycle** (test_intercept_flow.py) - 100% pass rate (3/3)
  - `test_fetch_stores_uid_and_internaldate` - Verifies IMAP fetch stores UID and server timestamp
  - `test_manual_intercept_moves_and_latency` - Validates HELD status with remote MOVE and latency calculation
  - `test_release_sets_delivered` - Confirms RELEASED/DELIVERED transition after email edit
- ✅ **Dashboard Stats** (test_unified_stats.py) - 100% pass rate (2/2)
- ⚠️ **Latency Metrics** (test_latency_stats.py) - 50% pass rate (2/4 in suite, all pass individually)

### Running Tests

```bash
# Run all interception tests (recommended)
python -m pytest tests/test_intercept_flow.py -v

# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_intercept_flow.py::test_fetch_stores_uid_and_internaldate -v
```

**Known Limitation**: 2/4 latency tests fail in suite mode due to Flask singleton, but pass individually (code is correct).

**Workaround**:
```bash
python -m pytest tests/test_latency_stats.py::test_latency_stats_empty -v
```

### Recommended Testing Strategy

**For Development**:
```bash
# Use working test suites
python -m pytest tests/interception/ -v
python -m pytest tests/test_complete_application.py::TestEmailDiagnostics -v
```

**For CI/CD** (when implemented):
```bash
# Exclude broken imports until Phase 1 fixes complete
python -m pytest tests/ --ignore=tests/integration --ignore=tests/unit/frontend
```

## Architecture Constraints

**NO POP3 SUPPORT**: The database schema only supports IMAP/SMTP. Do not add POP3 code:

- `email_accounts` table has no `pop3_*` columns
- Only `imap_host`, `imap_port`, `smtp_host`, `smtp_port` exist
- Any POP3 references will cause SQLite column errors

## Configuration & Settings

### Environment Variables

**`.env` file** (not committed) - Optional configuration overrides:
- `DB_PATH` - Override default SQLite database path
- `ENABLE_WATCHERS` - Enable/disable IMAP monitoring threads (default: 1)
- `ENABLE_LIVE_EMAIL_TESTS` - Gate live email tests (default: 0)
- `LIVE_EMAIL_ACCOUNT` - Which test account to use (gmail or hostinger)
- `GMAIL_ADDRESS`, `GMAIL_PASSWORD` - Gmail test credentials
- `HOSTINGER_ADDRESS`, `HOSTINGER_PASSWORD` - Hostinger test credentials
- `FLASK_SECRET_KEY` - Strong 64-char hex for session security

**`.env.example`** - Template with all configuration options and credential placeholders

### Configuration Toggles

**Environment Variables** (via `.env`):
```bash
# Database
DB_PATH=email_manager.db

# IMAP monitoring
ENABLE_WATCHERS=1  # 0 to disable IMAP threads (dev mode)

# Testing
ENABLE_LIVE_EMAIL_TESTS=0  # 1 to enable live tests
LIVE_EMAIL_ACCOUNT=gmail   # or 'hostinger'

# Credentials (for testing only - values MUST be set locally in .env)
GMAIL_ADDRESS=ndayijecika@gmail.com
GMAIL_PASSWORD=
HOSTINGER_ADDRESS=mcintyre@corrinbox.com
HOSTINGER_PASSWORD=
```

## Troubleshooting

### Common Issues

**Gmail Authentication Failed**
→ Use App Password (with spaces), verify 2FA enabled

**Port Already in Use**
→ `netstat -an | findstr :8587` then `taskkill /F /PID <pid>`

**Database Schema Mismatch**
→ Run `python scripts/migrate_database.py`

## Quick Reference Scripts

All scripts in `scripts/` directory:

**Email Account Management**:
- `test_permanent_accounts.py` - Test IMAP/SMTP connections (no DB changes)
- `setup_test_accounts.py` - Add/update accounts in database
- `verify_accounts.py` - Check database configuration

**Database Operations**:
- `verify_indices.py` - Verify database indices and query plans
- `migrations/*.py` - Database schema migrations

**Security & Validation**:
- `validate_security.py` - Run comprehensive security tests (4 tests)
- `../setup_security.ps1` - PowerShell security setup (Windows)
- `../setup_security.sh` - Bash security setup (Git Bash/WSL)

**System Checks**:
- `check_status.bat` - Quick Windows status check

## Threading Model

- **Main Thread**: Flask web server (port 5001)
- **SMTP Thread**: Email interception proxy (port 8587, daemon)
- **IMAP Threads**: Per-account monitoring (daemon, auto-reconnect)
  - Controlled by `ENABLE_WATCHERS` env var (default: enabled)
  - Started via `app/workers/imap_startup.py::start_imap_watchers()`
  - All threads share SQLite DB; WAL + busy_timeout mitigate contention

## Gmail Setup (For Adding New Accounts)

1. Enable 2-Factor Authentication
2. Generate App Password: https://myaccount.google.com/apppasswords
3. **Use password WITH spaces**: `xxxx xxxx xxxx xxxx`
4. Enable IMAP in Gmail settings
5. SMTP: `smtp.gmail.com:587` (STARTTLS)
6. IMAP: `imap.gmail.com:993` (SSL)
