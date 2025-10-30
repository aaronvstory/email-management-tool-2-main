# Email Management Tool — Quick Start

This is the fastest path to run the app locally on Windows.

## Prerequisites
- Python 3.9+ in PATH (tested with 3.13)
- Network access to IMAP/SMTP (ports 465/587/993)

## 1) Security setup (first run only)
- Run PowerShell: `./setup_security.ps1`
- It generates a strong FLASK_SECRET_KEY and `.env` if missing

## 2) Start the app
- Recommended: double‑click `launch.bat`
- Or: `python cleanup_and_start.py` (auto‑cleans stale processes, opens browser)
- Direct: `python simple_app.py`

Dashboard: http://localhost:5000  (login: admin / admin123)
SMTP Proxy: localhost:8587

## 3) Add an account
- Dashboard → Accounts → Add Account
- Use provider presets (Gmail/Outlook/Hostinger) or Custom
- Use App Passwords where required

## 4) Verify
- Accounts page: click Test IMAP/SMTP
- Dashboard → Diagnostics: run per‑account diagnostics
- Interception Test: /interception-test → run end‑to‑end flow

## 5) Troubleshooting
- Run: `python -m scripts.validate_security` (all 4 tests should PASS)
- Logs: `app.log`
- If the port is occupied, use `cleanup_and_start.py`
