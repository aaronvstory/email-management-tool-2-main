#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Example usage of EmailToolHelpers module for API testing

.DESCRIPTION
    Demonstrates how to use the PowerShell helper module to interact
    with the Email Management Tool API without manual session/CSRF management.

.NOTES
    Run this after starting the app with .\start-clean.ps1
#>

# Import the helper module
Import-Module .\EmailToolHelpers.psm1 -Force

# Color helpers
function Write-Step { param($msg) Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-OK { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "  ℹ $msg" -ForegroundColor Gray }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Email Tool API Testing Examples" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 1: Health check (no auth required)
Write-Step "Health Check (no authentication required)"
$health = Get-EmailToolHealth -BaseUrl "http://127.0.0.1:5010"
if ($health.status -eq "healthy") {
    Write-OK "App is running and healthy"
} else {
    Write-Error "Health check failed!"
    exit 1
}

# Step 2: Login
Write-Step "Connecting to Email Tool"
$connected = Connect-EmailTool -BaseUrl "http://127.0.0.1:5010" -Verbose
if (-not $connected) {
    Write-Error "Failed to connect!"
    exit 1
}

# Step 3: Get stats
Write-Step "Fetching statistics"
$stats = Invoke-EmailToolApi "/api/stats"
Write-Info "Total Emails: $($stats.total_emails)"
Write-Info "Pending: $($stats.pending)"
Write-Info "Approved: $($stats.approved)"
Write-Info "Rejected: $($stats.rejected)"

# Step 4: List accounts
Write-Step "Listing email accounts"
$accounts = Invoke-EmailToolApi "/api/accounts"
Write-Info "Found $($accounts.accounts.Count) account(s)"
foreach ($account in $accounts.accounts) {
    Write-Info "  - $($account.account_name) ($($account.email_address))"
}

# Step 5: Test an account connection (if account exists)
if ($accounts.accounts.Count -gt 0) {
    $accountId = $accounts.accounts[0].id
    Write-Step "Testing account #$accountId connection"

    try {
        $testResult = Invoke-EmailToolApi -Method POST -Path "/api/accounts/$accountId/test"
        if ($testResult.success) {
            Write-OK "Account connection test passed"
            Write-Info "IMAP: $($testResult.imap_status)"
            Write-Info "SMTP: $($testResult.smtp_status)"
        } else {
            Write-Warning "Account connection test failed: $($testResult.error)"
        }
    }
    catch {
        Write-Warning "Account test threw an error (account may not be configured yet)"
    }
}

# Step 6: Get unified stats
Write-Step "Fetching unified statistics"
$unifiedStats = Invoke-EmailToolApi "/api/unified-stats"
Write-Info "Processing Rate: $($unifiedStats.processing_rate) emails/hour"
Write-Info "Active Accounts: $($unifiedStats.active_accounts)"

# Step 7: Logout
Write-Step "Logging out"
Disconnect-EmailTool

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "✓ All examples completed successfully!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "Try these commands yourself:" -ForegroundColor Yellow
Write-Host "  Import-Module .\EmailToolHelpers.psm1" -ForegroundColor Gray
Write-Host "  Connect-EmailTool -BaseUrl 'http://127.0.0.1:5010'" -ForegroundColor Gray
Write-Host "  Invoke-EmailToolApi '/api/stats'" -ForegroundColor Gray
Write-Host "  Invoke-EmailToolApi -Method POST -Path '/api/accounts/1/test'" -ForegroundColor Gray
Write-Host ""
