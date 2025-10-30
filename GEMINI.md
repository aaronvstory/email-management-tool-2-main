# GEMINI.md

This file provides guidance to Gemini when working with code in this repository.

## Project Overview

**Email Management Tool** is a Python Flask application for local email interception, moderation, and management. It is developer-focused and runs entirely on localhost using SQLite, with no cloud services or Docker required.

**Version**: 2.8
**Status**: Fully functional.

### Key Features
- **SMTP Proxy Server**: Intercepts outgoing emails.
- **Web Dashboard**: A web interface for email management.
- **Email Moderation**: Allows holding, reviewing, editing, approving, or rejecting emails.
- **IMAP Watchers**: Uses a hybrid IDLE+polling strategy to monitor inboxes.
- **Security**: Includes CSRF protection, rate limiting, and encrypted credential storage.
- **Modular Design**: Routes are organized into Flask Blueprints.

## At-a-Glance

| Component            | Details                                                           |
| -------------------- | ----------------------------------------------------------------- |
| **Web Dashboard**    | http://localhost:5001 (Default Login: `admin` / `admin123`)       |
| **SMTP Proxy**       | localhost:8587                                                    |
| **Database**         | SQLite (`email_manager.db`)                                       |
| **Encryption Key**   | `key.txt` (Fernet symmetric encryption)                           |
| **Primary Launcher** | `EmailManager.bat` or `launch.bat`                                |
| **Test Accounts**    | Gmail (ndayijecika@gmail.com), Hostinger (mcintyre@corrinbox.com) |

**Security Note**: Test accounts are for development and testing only.

## Quick Start

### Prerequisites
- Python 3.9+
- Windows environment
- Email accounts with App Passwords configured

### Starting the Application

You can start the application using one of the following methods:

```bash
# Recommended launcher with a menu
EmailManager.bat

# Quick start without a menu
launch.bat

# Direct Python execution
python simple_app.py
```

After starting, the web dashboard is accessible at `http://localhost:5001`.

### Restarting After Port Conflicts
If you encounter port conflicts, you can use the provided cleanup script:
```bash
python cleanup_and_start.py
```

## File Organization

```
Email-Management-Tool/
├── simple_app.py            # Main application file
├── email_manager.db         # SQLite database
├── key.txt                  # Encryption key
├── requirements.txt         # Python dependencies
├── EmailManager.bat         # Primary launcher script
├── CLAUDE.md                # Guide for Claude AI
├── GEMINI.md                # Guide for Gemini AI (this file)
├── app/
│   ├── routes/              # Flask Blueprint modules for different parts of the app
│   ├── services/            # Business logic (stats, audit, IMAP workers)
│   └── utils/               # Utility modules (db, crypto)
├── docs/                    # Project documentation
├── tests/                   # Pytest test suite
├── scripts/                 # Utility and maintenance scripts
└── static/ & templates/     # Frontend assets (CSS, JS, HTML)
```

## Essential Commands

Here are some essential commands for development and maintenance:

```bash
# Start the application
python simple_app.py

# Run the full test suite
python -m pytest tests/ -v

# Run tests for a specific file
python -m pytest tests/test_intercept_flow.py -v

# Validate security configuration
python -m scripts.validate_security

# Test connectivity for permanent email accounts
python scripts/test_permanent_accounts.py

# Check the health of the application
curl http://localhost:5001/healthz
```

## Key API Endpoints

The application exposes several RESTful API endpoints for management:

- **Authentication**: `GET /login`, `POST /login`
- **Dashboard**: `GET /dashboard`
- **Interception**:
    - `GET  /api/interception/held`: List held messages.
    - `POST /api/interception/release/<id>`: Release a message.
    - `POST /api/interception/discard/<id>`: Discard a message.
    - `POST /api/email/<id>/edit`: Edit an email.
- **Health & Monitoring**: `GET /healthz`, `GET /metrics`

## Development Guidelines

### Database Access
- Use the `app.utils.db.get_db()` context manager for thread-safe SQLite connections.
- The database is configured to use `row_factory` to allow accessing columns by name (e.g., `row['subject']`).

### UI Development
- Adhere to the standards in `docs/STYLEGUIDE.md` for any UI changes.
- The application uses a dark theme with Bootstrap 5.3 components.

### Code Structure
- The application is structured using Flask Blueprints, located in the `app/routes/` directory. This keeps the codebase modular and organized.

## Troubleshooting

- **Gmail Authentication Failed**: Ensure you are using an App Password and that 2FA is enabled for the account.
- **Port Already in Use**: Run `python cleanup_and_start.py` to kill existing Python processes and restart the application.
- **UI Styling Issues**: Refer to `docs/STYLEGUIDE.md` for correct UI patterns and classes.
