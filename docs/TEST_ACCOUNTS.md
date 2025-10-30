# Test Accounts Documentation

## 🔑 PERMANENT TEST ACCOUNTS (DO NOT MODIFY)

**CRITICAL**: These are the ONLY two accounts with confirmed working credentials. Use these for all testing.

⚠️ **Security Note**: Permanent test accounts are for **development/testing only**. Rotate credentials if exposed. Never use in production.

### Account 1: Gmail - NDayijecika (Primary Test Account)

- **Email**: ndayijecika@gmail.com
- **Password**: [REDACTED – set via .env GMAIL_PASSWORD]
- **SMTP**: smtp.gmail.com:587 (STARTTLS, not SSL)
- **IMAP**: imap.gmail.com:993 (SSL)
- **Username**: ndayijecika@gmail.com (same as email)
- **Database ID**: 3
- **Status**: ✅ FULLY OPERATIONAL
- **Last Tested**: 2025-09-30 09:47:44
  - IMAP: ✅ Connected (9 folders found)
  - SMTP: ✅ Authenticated successfully

### Account 2: Hostinger - Corrinbox (Secondary Test Account)

- **Email**: mcintyre@corrinbox.com
- **Password**: [REDACTED – set via .env HOSTINGER_PASSWORD]
- **SMTP**: smtp.hostinger.com:465 (SSL direct)
- **IMAP**: imap.hostinger.com:993 (SSL)
- **Username**: mcintyre@corrinbox.com (same as email)
- **Database ID**: 2
- **Status**: ✅ FULLY OPERATIONAL
- **Last Tested**: 2025-09-30 09:47:44
  - IMAP: ✅ Connected (5 folders found)
  - SMTP: ✅ Authenticated successfully

## SMTP/IMAP Smart Detection Rules

### Gmail
- SMTP: Port 587 with STARTTLS (smtp_use_ssl=0)
- IMAP: Port 993 with SSL
- Requires App Password (not regular password)

### Hostinger
- SMTP: Port 465 with SSL (smtp_use_ssl=1)
- IMAP: Port 993 with SSL

### General Rules
- Port 587 → Always use STARTTLS (smtp_use_ssl=0)
- Port 465 → Always use direct SSL (smtp_use_ssl=1)
- Port 993 (IMAP) → Always SSL
- Username = Email address for most providers

## Smart Detection Implementation

**Location**: `simple_app.py` lines 97-160

**Function**: `detect_email_settings(email_address: str) -> dict`

- Auto-detects SMTP/IMAP settings based on email domain
- Returns dictionary with all connection parameters
- Supports Gmail, Hostinger, Outlook, Yahoo, and generic fallback

### Supported Providers

| Provider | Domain | SMTP Port | IMAP Port | Notes |
|----------|--------|-----------|-----------|-------|
| Gmail | gmail.com | 587 (STARTTLS) | 993 (SSL) | Requires App Password |
| Hostinger | corrinbox.com | 465 (SSL) | 993 (SSL) | Direct SSL |
| Outlook | outlook.com, hotmail.com | 587 (STARTTLS) | 993 (SSL) | App Password for 2FA |
| Yahoo | yahoo.com | 465 (SSL) | 993 (SSL) | Direct SSL |
| Generic | any | 587 (STARTTLS) | 993 (SSL) | Fallback pattern |

## Testing Commands

### Test Account Connections
```bash
# Test permanent account connections (no DB modification)
python scripts/test_permanent_accounts.py

# Setup/update permanent accounts in database
python scripts/setup_test_accounts.py

# Verify account configuration in database
python scripts/verify_accounts.py

# Quick status check (Windows batch file)
scripts\check_status.bat
```

## Environment Variables for Testing

Add these to your `.env` file for testing:

```bash
# Testing toggles
ENABLE_LIVE_EMAIL_TESTS=0  # Set to 1 to enable live tests
LIVE_EMAIL_ACCOUNT=gmail   # or 'hostinger'

# Gmail test account (values must be set locally)
GMAIL_ADDRESS=ndayijecika@gmail.com
GMAIL_PASSWORD=xxxx xxxx xxxx xxxx  # App password with spaces

# Hostinger test account (values must be set locally)
HOSTINGER_ADDRESS=mcintyre@corrinbox.com
HOSTINGER_PASSWORD=your-password-here
```

## Gmail Setup Instructions

For adding new Gmail accounts:

1. Enable 2-Factor Authentication on the Gmail account
2. Generate App Password: https://myaccount.google.com/apppasswords
3. **Use password WITH spaces**: `xxxx xxxx xxxx xxxx`
4. Enable IMAP in Gmail settings
5. Configure in application:
   - SMTP: `smtp.gmail.com:587` (STARTTLS)
   - IMAP: `imap.gmail.com:993` (SSL)
   - Username: Same as email address

## Multi-Account Management

The application supports multiple email accounts simultaneously:

- Each account runs an independent IMAP monitor thread
- Accounts can be enabled/disabled without affecting others
- Smart detection automatically configures most providers
- Manual configuration available for custom email servers

### Supported Providers

- **Gmail**: Requires App Password (keep spaces in password)
- **Outlook/Hotmail**: App Password required for 2FA accounts
- **Hostinger**: Direct SSL connections
- **Yahoo**: Direct SSL connections
- **Custom IMAP/SMTP**: Manual configuration supported

## Account Testing Workflow

1. **Initial Setup**:
   ```bash
   # Add test accounts to database
   python scripts/setup_test_accounts.py
   ```

2. **Verify Configuration**:
   ```bash
   # Check accounts are properly configured
   python scripts/verify_accounts.py
   ```

3. **Test Connectivity**:
   ```bash
   # Test IMAP/SMTP connections (no DB changes)
   python scripts/test_permanent_accounts.py
   ```

4. **Monitor Status**:
   - Check dashboard at http://localhost:5001
   - View account health in Accounts tab
   - Monitor `app.log` for connection issues

## Troubleshooting Test Accounts

### Gmail Authentication Failed
- Ensure 2FA is enabled on the Gmail account
- Generate new App Password (old ones may expire)
- Keep spaces in App Password: `xxxx xxxx xxxx xxxx`
- Verify IMAP is enabled in Gmail settings
- Check "Less secure app access" is not blocking connections

### Hostinger Connection Issues
- Verify SSL settings (port 465 for SMTP, 993 for IMAP)
- Check firewall isn't blocking ports
- Ensure credentials are correct (email as username)

### General Connection Problems
- Run `python scripts/test_permanent_accounts.py` for detailed diagnostics
- Check `app.log` for specific error messages
- Verify network connectivity to email servers
- Test with telnet: `telnet smtp.gmail.com 587`

## Important Security Notes

1. **Never commit credentials** - Keep passwords in `.env` file only
2. **Rotate test passwords regularly** - Especially after exposing logs
3. **Use app-specific passwords** - Never use main account passwords
4. **Development only** - These accounts are for testing, not production
5. **Monitor access** - Check account activity logs regularly

## Account Management Best Practices

- Always test changes with permanent test accounts first
- Keep test data separate from production data
- Use smart detection for initial configuration
- Document any custom server configurations
- Maintain backup of working account configurations
- Test both sending and receiving for each account
