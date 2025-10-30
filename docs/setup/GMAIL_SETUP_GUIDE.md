# Gmail Setup Guide for Email Management Tool

## 🚨 IMPORTANT: Gmail Authentication Requirements

As of 2024, Gmail requires either:
1. **App Passwords** (requires 2FA enabled) - RECOMMENDED
2. **OAuth2** (more complex setup)

Regular passwords NO LONGER WORK for SMTP/IMAP access!

## Step 1: Enable 2-Factor Authentication (REQUIRED)

1. Go to: https://myaccount.google.com/signinoptions/two-step-verification
2. Click "Get Started"
3. Sign in to your account (ndayijecika@gmail.com)
4. Add a phone number for verification
5. Enter the verification code sent to your phone
6. Click "Turn On" to enable 2FA

## Step 2: Generate App Password

Once 2FA is enabled:

1. Go to: https://myaccount.google.com/apppasswords
2. You should now see the App Passwords page
3. Select app: "Mail"
4. Select device: "Windows Computer" (or "Other")
5. Click "Generate"
6. Copy the 16-character password shown (e.g., "abcd efgh ijkl mnop")
7. **IMPORTANT**: Save this password immediately - you won't see it again!

## Step 3: Update Configuration

Replace your regular password with the App Password in `email_accounts.json`:

```json
{
  "id": "gmail_ndayijecika",
  "email": "ndayijecika@gmail.com",
  "smtp": {
    "password": "YOUR_16_CHAR_APP_PASSWORD_HERE"  // No spaces!
  },
  "imap": {
    "password": "YOUR_16_CHAR_APP_PASSWORD_HERE"  // Same password
  }
}
```

## Alternative: If 2FA Cannot Be Enabled

### Option A: Create a New Gmail Account
1. Create a new Gmail account specifically for testing
2. Enable 2FA during account creation
3. Generate App Password immediately

### Option B: Use OAuth2 (Advanced)
Requires setting up a Google Cloud Project and implementing OAuth2 flow.
More complex but doesn't require passwords.

## Troubleshooting

### "App passwords not available" Error:
- **Cause**: 2FA not enabled
- **Solution**: Complete Step 1 above

### "Invalid credentials" Error:
- **Cause**: Using regular password instead of App Password
- **Solution**: Generate and use App Password (Step 2)

### "Authentication failed" Error:
- **Cause**: Spaces in App Password or wrong password
- **Solution**: Remove spaces from 16-char password (abcdefghijklmnop not abcd efgh ijkl mnop)

## Test Your Setup

After updating the password, run:
```bash
python test_gmail_integration.py
```

Expected output:
- ✅ Gmail SMTP connection successful!
- ✅ Gmail IMAP connection successful!

## Security Notes

- App Passwords bypass 2FA, so keep them secure
- Each App Password is specific to one application
- You can revoke App Passwords anytime from Google Account settings
- Never share App Passwords or commit them to public repositories

---
Last Updated: 2025-08-30
For: Email Management Tool Multi-Account System