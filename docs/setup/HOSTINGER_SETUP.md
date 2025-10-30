# Hostinger Email Configuration Guide

## Current Configuration Status
- **SMTP Server**: smtp.hostinger.com:465 (SSL) ✅ Reachable
- **IMAP Server**: imap.hostinger.com:993 (SSL) ✅ Reachable
- **Authentication**: ❌ Currently failing

## Configuration in .env File

```env
# SMTP Settings (Outgoing Mail)
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=465
SMTP_USERNAME=mcintyre@corrinbox.com
SMTP_PASSWORD=Slaypap3!!
SMTP_USE_TLS=false
SMTP_USE_SSL=true

# IMAP Settings (Incoming Mail)
IMAP_HOST=imap.hostinger.com
IMAP_PORT=993
IMAP_USERNAME=mcintyre@corrinbox.com
IMAP_PASSWORD=Slaypap3!!
IMAP_USE_SSL=true
```

## Troubleshooting Authentication Issues

### 1. Check Hostinger Email Settings
Log into your Hostinger account and verify:
- IMAP is enabled for the email account
- SMTP is enabled for the email account
- No IP restrictions are in place
- The account is active and not suspended

### 2. Generate App-Specific Password (if available)
Some email providers require app-specific passwords:
1. Log into Hostinger email settings
2. Look for "App Passwords" or "Application Passwords"
3. Generate a new password for "Email Client"
4. Use this password instead of your regular password

### 3. Verify Account Access
Test your credentials manually:
1. Try logging into webmail at https://webmail.hostinger.com
2. Verify the username is the full email address: mcintyre@corrinbox.com
3. Ensure no extra spaces in the password

### 4. Security Settings
Check if Hostinger requires:
- Specific authentication methods (PLAIN, LOGIN, CRAM-MD5)
- SSL/TLS certificate verification
- Specific client identification

### 5. Alternative Authentication Methods

#### For Gmail/Google Workspace:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

#### For Outlook/Office 365:
```env
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

## Testing Connectivity

### Quick Test Script
Run the provided test script:
```bash
python test_hostinger.py
```

### Web Dashboard Diagnostics
1. Start the application: `python simple_app.py`
2. Navigate to: http://localhost:5000/diagnostics
3. Review the detailed connectivity report

### Manual Testing with OpenSSL
Test SSL connection:
```bash
# Test SMTP SSL connection
openssl s_client -connect smtp.hostinger.com:465 -showcerts

# Test IMAP SSL connection
openssl s_client -connect imap.hostinger.com:993 -showcerts
```

## Common Issues and Solutions

### Issue: Authentication Failed
**Error**: `535 5.7.8 Error: authentication failed`

**Solutions**:
1. Double-check password for typos
2. Try with app-specific password
3. Ensure account allows IMAP/SMTP access
4. Check if 2FA is blocking access

### Issue: Connection Timeout
**Error**: Connection times out

**Solutions**:
1. Check firewall settings
2. Verify ports 465 (SMTP) and 993 (IMAP) are not blocked
3. Try alternative ports if available

### Issue: SSL Certificate Error
**Error**: SSL certificate verification failed

**Solutions**:
1. Update Python certificates: `pip install --upgrade certifi`
2. Use custom SSL context in code
3. Temporarily disable SSL verification (not recommended for production)

## Next Steps

1. **Verify Credentials**:
   - Confirm password is correct
   - Try logging into webmail to verify account access

2. **Check Account Settings**:
   - Log into Hostinger control panel
   - Navigate to Email → Email Accounts
   - Check settings for mcintyre@corrinbox.com
   - Ensure IMAP and SMTP are enabled

3. **Contact Support**:
   If authentication continues to fail:
   - Contact Hostinger support
   - Ask about:
     - IMAP/SMTP authentication requirements
     - App-specific passwords
     - IP whitelisting requirements
     - Any special authentication methods required

## Alternative Configuration

If Hostinger authentication cannot be resolved, you can use a Gmail account:

1. Create/use a Gmail account
2. Enable 2-factor authentication
3. Generate app-specific password at https://myaccount.google.com/apppasswords
4. Update .env with Gmail settings:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_USE_TLS=true
   SMTP_USE_SSL=false
   
   IMAP_HOST=imap.gmail.com
   IMAP_PORT=993
   IMAP_USERNAME=your-email@gmail.com
   IMAP_PASSWORD=your-app-password
   IMAP_USE_SSL=true
   ```