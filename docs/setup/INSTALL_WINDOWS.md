# Windows Installation Guide - Email Management Tool

## ⚠️ NO DOCKER REQUIRED
This application runs natively on Windows without Docker, containers, or any virtualization. It's a pure Python application optimized for Windows.

## 📋 Prerequisites

### Required Software
1. **Python 3.9 or higher**
   - Download from: https://www.python.org/downloads/
   - During installation, CHECK "Add Python to PATH"
   - Verify: Open Command Prompt and run `python --version`

2. **Windows Version**
   - Windows 10 (version 1903 or later)
   - Windows 11 (any version)
   - Windows Server 2016 or later

3. **Administrator Access** (optional)
   - Only needed if installing as Windows Service
   - Regular user access is fine for standard operation

## 🚀 Quick Installation (5 minutes)

### Step 1: Download the Application
```batch
# Option A: Clone from repository (if you have git)
git clone https://github.com/yourcompany/email-management-tool.git
cd email-management-tool

# Option B: Download and extract ZIP file
# Download from your repository and extract to C:\EmailManagementTool
```

### Step 2: Run Setup Script
```batch
# Open Command Prompt in the application directory
cd C:\EmailManagementTool

# Run the automated setup
setup.bat
```

The setup script will:
- ✅ Check Python installation
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Create necessary directories
- ✅ Generate default configuration

### Step 3: Configure Email Settings
1. Open `config\config.ini` in Notepad
2. Update SMTP relay settings:
```ini
[SMTP_RELAY]
relay_host = smtp.gmail.com  # Your SMTP server
relay_port = 587
username = your-email@gmail.com
password = your-app-password  # Use app-specific password for Gmail
```

### Step 4: Start the Application
```batch
# Start the application
start.bat
```

### Step 5: Access the Dashboard
1. Open your web browser
2. Navigate to: http://localhost:5000
3. Login with:
   - Username: `admin`
   - Password: `admin123`
4. **Important**: Change the admin password immediately!

## 🔧 Detailed Installation Options

### Option A: Standard Installation (Recommended)

Perfect for development and testing:

```batch
# 1. Setup
setup.bat

# 2. Configure
notepad config\config.ini

# 3. Start
start.bat
```

### Option B: PowerShell Installation

For more control and features:

```powershell
# 1. Open PowerShell
# Right-click Start → Windows PowerShell

# 2. Navigate to application directory
cd C:\EmailManagementTool

# 3. Run setup
.\setup.bat

# 4. Use PowerShell management
.\manage.ps1 status
.\manage.ps1 start
```

### Option C: Windows Service Installation

For production deployment (auto-starts with Windows):

```powershell
# 1. Open PowerShell as Administrator
# Right-click Start → Windows PowerShell (Admin)

# 2. Navigate to application directory
cd C:\EmailManagementTool

# 3. Run setup first
.\setup.bat

# 4. Install as service
.\manage.ps1 install

# 5. Service will auto-start
# Access at http://localhost:5000
```

## 📧 Email Client Configuration

### Microsoft Outlook
1. File → Account Settings → Account Settings
2. Select your email account → Change
3. More Settings → Outgoing Server tab
4. Change SMTP server to: `localhost`
5. Change port to: `8587`
6. Uncheck "Require authentication"
7. Test Account Settings

### Mozilla Thunderbird
1. Account Settings → Outgoing Server (SMTP)
2. Add new SMTP server:
   - Server: `localhost`
   - Port: `8587`
   - Security: None
   - Authentication: None
3. Set as default SMTP server

### Other Email Clients
Configure SMTP settings:
- **Server**: `localhost` or `127.0.0.1`
- **Port**: `8587`
- **Security**: None
- **Authentication**: Not required

## 🛠️ Configuration Details

### Essential Configuration (`config\config.ini`)

```ini
[SMTP_PROXY]
host = 0.0.0.0          # Listen on all interfaces
port = 8587             # SMTP proxy port
max_message_size = 33554432  # 32MB max

[SMTP_RELAY]
relay_host = smtp.office365.com  # Your actual SMTP server
relay_port = 587
use_tls = true
username = your-email@company.com
password = your-password

[WEB_INTERFACE]
host = 127.0.0.1        # Web interface binding
port = 5000             # Web dashboard port
secret_key = [auto-generated]
debug = false           # Set to true for development

[DATABASE]
database_path = data\email_moderation.db

[SECURITY]
session_timeout = 30    # Minutes
max_login_attempts = 5
lockout_duration = 15   # Minutes
```

### Advanced Configuration

#### Enable HTTPS for Dashboard
1. Generate SSL certificate (self-signed for testing):
```batch
# In config\certs directory
openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365
```

2. Update config.ini:
```ini
[WEB_INTERFACE]
use_ssl = true
ssl_cert = config\certs\cert.pem
ssl_key = config\certs\key.pem
```

#### Active Directory Integration
```ini
[AUTHENTICATION]
use_ad = true
ad_server = dc.company.local
ad_domain = COMPANY
ad_base_dn = DC=company,DC=local
```

## 🔍 Verification Steps

### 1. Check Python Installation
```batch
python --version
# Should show: Python 3.9.x or higher

pip --version
# Should show: pip 21.x.x or higher
```

### 2. Verify Services Running
```batch
# Check SMTP proxy
telnet localhost 8587
# Type: HELO test
# Should respond: 250 OK

# Check web dashboard
curl http://localhost:5000
# Should return HTML content
```

### 3. Check Ports
```batch
netstat -an | findstr "8587 5000"
# Should show:
# TCP    0.0.0.0:8587    LISTENING
# TCP    127.0.0.1:5000  LISTENING
```

### 4. Test Email Flow
1. Configure email client to use localhost:8587
2. Send test email with subject "Test Invoice"
3. Check dashboard for pending email
4. Approve or reject the email

## 🚨 Troubleshooting

### Python Not Found
```batch
# Error: 'python' is not recognized

# Solution 1: Add Python to PATH manually
setx PATH "%PATH%;C:\Python39;C:\Python39\Scripts"

# Solution 2: Reinstall Python with "Add to PATH" checked
```

### Port Already in Use
```batch
# Error: Port 8587 or 5000 already in use

# Find process using port
netstat -ano | findstr :8587
# Note the PID (last column)

# Kill the process
taskkill /F /PID [process_id]
```

### Permission Denied
```batch
# Error: Permission denied creating directories

# Solution: Run as Administrator or change install location
# Right-click Command Prompt → Run as Administrator
```

### Dependencies Installation Failed
```batch
# Error: Failed to install dependencies

# Solution 1: Upgrade pip
python -m pip install --upgrade pip

# Solution 2: Install manually
venv\Scripts\activate
pip install flask sqlalchemy aiosmtpd
```

### Cannot Access Dashboard
```batch
# Error: Cannot connect to http://localhost:5000

# Check Windows Firewall
# Windows Security → Firewall → Allow an app
# Add Python.exe from venv\Scripts\
```

## 🔐 Security Hardening

### 1. Change Default Password
```python
# After first login, go to Settings → Users
# Change admin password immediately
```

### 2. Configure Firewall
```batch
# Allow only specific IPs to access dashboard
netsh advfirewall firewall add rule name="Email Dashboard" dir=in action=allow protocol=TCP localport=5000 remoteip=192.168.1.0/24
```

### 3. Enable Audit Logging
```ini
[LOGGING]
audit_level = INFO
audit_file = logs\audit.log
log_ip_addresses = true
log_user_actions = true
```

### 4. Regular Backups
```powershell
# Schedule daily backups
schtasks /create /tn "Email Backup" /tr "powershell C:\EmailManagementTool\manage.ps1 backup" /sc daily /st 02:00
```

## 📊 Performance Tuning

### For High Volume (>1000 emails/hour)
```ini
[PERFORMANCE]
worker_threads = 4
connection_pool_size = 20
cache_size = 100
batch_processing = true
```

### Database Optimization
```batch
# Periodic maintenance (monthly)
sqlite3 data\email_moderation.db "VACUUM;"
sqlite3 data\email_moderation.db "ANALYZE;"
```

## 🆘 Getting Help

### Check Logs
```batch
# View recent errors
type logs\email_moderation.log | findstr ERROR

# View with PowerShell
Get-Content logs\email_moderation.log -Tail 50
```

### Generate Diagnostic Report
```powershell
.\manage.ps1 status > diagnostic.txt
```

### Common Issues Database
See `docs\TROUBLESHOOTING.md` for comprehensive issue resolution.

## ✅ Post-Installation Checklist

- [ ] Python 3.9+ installed and in PATH
- [ ] Virtual environment created
- [ ] Dependencies installed successfully
- [ ] Configuration file updated with email settings
- [ ] Application starts without errors
- [ ] Can access dashboard at http://localhost:5000
- [ ] Default admin password changed
- [ ] Email client configured to use proxy
- [ ] Test email successfully intercepted
- [ ] Backup scheduled (production only)
- [ ] Firewall rules configured (production only)
- [ ] Windows Service installed (production only)

## 🎉 Installation Complete!

Your Email Management Tool is now ready to use. Remember:
- **NO DOCKER REQUIRED** - Runs natively on Windows
- Dashboard: http://localhost:5000
- SMTP Proxy: localhost:8587
- Default login: admin/admin123 (change immediately!)

For daily operations, see `README.md`
For troubleshooting, see `docs\TROUBLESHOOTING.md`
For API documentation, see `docs\API.md`