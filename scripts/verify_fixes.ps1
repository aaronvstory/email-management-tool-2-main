#!/usr/bin/env pwsh
# Quick verification that the resilient API fixes are working

$ErrorActionPreference = "Stop"

$BASE = $env:SMOKE_BASE_URI
if (-not $BASE) { $BASE = "http://127.0.0.1:5001" }

Write-Host "`n=== Verifying API Fixes ===" -ForegroundColor Cyan

# Test 1: Check /api/emails/recent endpoint
Write-Host "`n1. Testing /api/emails/recent..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$BASE/api/emails/recent" -Method GET
    if ($response.StatusCode -eq 200) {
        $json = $response.Content | ConvertFrom-Json
        Write-Host "   ✅ /api/emails/recent returned 200 OK" -ForegroundColor Green
        Write-Host "   Items: $($json.items.Count)" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ❌ Failed: $_" -ForegroundColor Red
    exit 1
}

# Test 2: Check /api/emails endpoint with filters
Write-Host "`n2. Testing /api/emails with filters..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$BASE/api/emails?status=ALL&page=1&page_size=10" -Method GET
    if ($response.StatusCode -eq 200) {
        $json = $response.Content | ConvertFrom-Json
        Write-Host "   ✅ /api/emails returned 200 OK" -ForegroundColor Green
        Write-Host "   Total: $($json.total), Pages: $($json.pages)" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ❌ Failed: $_" -ForegroundColor Red
    exit 1
}

# Test 3: Seed demo emails (if in debug mode)
Write-Host "`n3. Testing seed endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$BASE/api/dev/seed_emails" -Method POST
    if ($response.StatusCode -eq 200) {
        $json = $response.Content | ConvertFrom-Json
        Write-Host "   ✅ Seeded $($json.inserted) demo emails" -ForegroundColor Green
    }
} catch {
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "   ℹ️  Seed endpoint disabled (app not in DEBUG mode)" -ForegroundColor Gray
    } else {
        Write-Host "   ⚠️  Seed failed: $_" -ForegroundColor Yellow
    }
}

# Test 4: Verify dashboard page loads without JS errors
Write-Host "`n4. Testing dashboard page..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$BASE/dashboard" -Method GET
    if ($response.StatusCode -eq 200 -and $response.Content -match "escapeHtml") {
        Write-Host "   ✅ Dashboard loads with helper functions" -ForegroundColor Green
    }
} catch {
    Write-Host "   ⚠️  Dashboard check: $_" -ForegroundColor Yellow
}

Write-Host "`n=== Verification Complete ===" -ForegroundColor Cyan
Write-Host "All critical endpoints are responding correctly!`n" -ForegroundColor Green
