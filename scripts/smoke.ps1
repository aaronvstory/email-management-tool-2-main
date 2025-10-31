$ErrorActionPreference = "Stop"

$BaseUri = $env:SMOKE_BASE_URI
if ([string]::IsNullOrWhiteSpace($BaseUri)) {
    $BaseUri = "http://127.0.0.1:5001"
}
$Session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$Script:CsrfToken = $null

function Invoke-SmokeRequest {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('GET','POST','PUT','PATCH','DELETE','HEAD')][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        $Body
    )

    $uri = if ($Path -like 'http*') { $Path } else { "$BaseUri$Path" }
    $headers = @{}

    if ($Method -in @('POST','PUT','PATCH','DELETE')) {
        if ($Script:CsrfToken) {
            $headers['X-CSRFToken'] = $Script:CsrfToken
            $headers['X-CSRF-Token'] = $Script:CsrfToken
        }
        $headers['Referer'] = "$BaseUri/"
    }

    $invokeParams = @{
        Method     = $Method
        Uri        = $uri
        WebSession = $Session
        ErrorAction = 'Stop'
        TimeoutSec = 15
    }

    if ($headers.Count -gt 0) {
        $invokeParams['Headers'] = $headers
    }

    if ($null -ne $Body) {
        if ($Body -is [string]) {
            $invokeParams['Body'] = $Body
        } else {
            $invokeParams['Body'] = ($Body | ConvertTo-Json -Depth 6)
        }
        if (-not $invokeParams.ContainsKey('ContentType')) {
            $invokeParams['ContentType'] = 'application/json'
        }
    }

    return Invoke-RestMethod @invokeParams
}

function Assert-ApiOk {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if ($null -eq $Response) {
        throw "Empty response from $Path"
    }

    $okField = $Response.PSObject.Properties.Name -contains 'ok'
    $successField = $Response.PSObject.Properties.Name -contains 'success'

    $isOk = $false
    if ($okField) { $isOk = [bool]$Response.ok }
    elseif ($successField) { $isOk = [bool]$Response.success }

    if (-not $isOk) {
        $detail = $Response.detail
        if (-not $detail -and $Response.error) { $detail = $Response.error }
        throw "API indicated failure at $Path`nDetail: $detail"
    }
}

Write-Host "Running smoke checks against $BaseUri" -ForegroundColor Cyan

# Health check (no auth required)
Invoke-SmokeRequest -Method 'GET' -Path '/healthz' | Out-Null

# Login step with CSRF token and session cookie
$loginPage = Invoke-WebRequest -Uri "$BaseUri/login" -WebSession $Session -UseBasicParsing
if ($loginPage.Content -notmatch 'name="csrf_token" value="([^"]+)"') {
    throw 'Failed to locate CSRF token on login page'
}
$loginToken = $matches[1]
$loginBody = "username=admin&password=admin123&csrf_token=$loginToken"
$loginHeaders = @{ 'Referer' = "$BaseUri/login" }
Invoke-WebRequest -Uri "$BaseUri/login" -Method POST -Body $loginBody `
    -ContentType 'application/x-www-form-urlencoded' -Headers $loginHeaders `
    -WebSession $Session -UseBasicParsing | Out-Null

# Retrieve dashboard to capture meta csrf for API requests
$dashboardPage = Invoke-WebRequest -Uri "$BaseUri/dashboard" -WebSession $Session -UseBasicParsing
if ($dashboardPage.Content -notmatch 'meta name="csrf-token" content="([^"]+)"') {
    throw 'Unable to locate dashboard CSRF meta tag'
}
$Script:CsrfToken = $matches[1]

# Core API checks
$accountTest = Invoke-SmokeRequest -Method 'POST' -Path '/api/accounts/1/test'
Assert-ApiOk -Response $accountTest -Path '/api/accounts/1/test'

$startWatcher = Invoke-SmokeRequest -Method 'POST' -Path '/api/accounts/1/monitor/start'
Assert-ApiOk -Response $startWatcher -Path '/api/accounts/1/monitor/start'
if ([string]::IsNullOrWhiteSpace($startWatcher.state)) {
    throw 'Watcher start returned empty state'
}

Start-Sleep -Seconds 1

$stopWatcher = Invoke-SmokeRequest -Method 'POST' -Path '/api/accounts/1/monitor/stop'
Assert-ApiOk -Response $stopWatcher -Path '/api/accounts/1/monitor/stop'
if ($stopWatcher.state -notin @('stopped','stopping')) {
    throw "Unexpected watcher stop state: $($stopWatcher.state)"
}

Write-Host 'SMOKE OK' -ForegroundColor Green

