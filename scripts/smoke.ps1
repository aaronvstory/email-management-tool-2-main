$ErrorActionPreference = "Stop"

$script:SmokeSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$script:BaseUri = 'http://localhost:5001'
$script:CsrfToken = $null

function Ensure-SmokeSession {
    if ($script:SmokeSession.Cookies.Count -gt 0 -and $script:CsrfToken) {
        return
    }

    try {
        $loginPage = Invoke-WebRequest -Uri "$($script:BaseUri)/login" -Method Get -WebSession $script:SmokeSession -ErrorAction Stop
    }
    catch {
        throw "Failed to load login page: $($_.Exception.Message)"
    }

    if ($loginPage.Content -match 'name="csrf_token" value="([^"]+)"') {
        $csrfToken = $matches[1]
    } else {
        throw "Unable to extract CSRF token from login page"
    }

    $loginBody = @{ username = 'admin'; password = 'admin123'; csrf_token = $csrfToken }
    try {
        $response = Invoke-WebRequest -Uri "$($script:BaseUri)/login" -Method Post -Body $loginBody -ContentType 'application/x-www-form-urlencoded' -WebSession $script:SmokeSession -Headers @{ Referer = "$($script:BaseUri)/login" } -ErrorAction Stop
    }
    catch {
        throw "Login request failed: $($_.Exception.Message)"
    }

    if ($response.StatusCode -notin @(200, 302)) {
        throw "Unexpected login status code: $($response.StatusCode)"
    }

    try {
        $dashboard = Invoke-WebRequest -Uri "$($script:BaseUri)/dashboard" -Method Get -WebSession $script:SmokeSession -ErrorAction Stop
    }
    catch {
        throw "Failed to load dashboard after login: $($_.Exception.Message)"
    }

    if ($dashboard.Content -match 'name="csrf-token" content="([^"]+)"') {
        $script:CsrfToken = $matches[1]
    } else {
        throw "Unable to extract CSRF token from dashboard"
    }
}

function Invoke-SmokeRequest {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('GET','POST','DELETE','PUT','PATCH','HEAD')][string]$Method,
        [Parameter(Mandatory = $true)][string]$Url,
        [string]$Body
    )

    $invokeParams = @{
        Method     = $Method
        Uri        = $Url
        TimeoutSec = 15
        WebSession = $script:SmokeSession
    }

    if ($script:CsrfToken) {
        $invokeParams.Headers = @{ 'X-CSRFToken' = $script:CsrfToken }
    }

    if ($Body) {
        $invokeParams.Body        = $Body
        $invokeParams.ContentType = 'application/json'
    }

    try {
        return Invoke-RestMethod @invokeParams
    }
    catch {
        throw "HTTP request failed for ${Url}: $($_.Exception.Message)"
    }
}

function Assert-ApiOk {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [Parameter(Mandatory = $true)][string]$Url
    )

    if ($null -eq $Response) {
        throw "Empty response from $Url"
    }

    $okField = $Response.PSObject.Properties.Name -contains 'ok'
    $successField = $Response.PSObject.Properties.Name -contains 'success'

    $isOk = $false
    if ($okField) { $isOk = [bool]$Response.ok }
    elseif ($successField) { $isOk = [bool]$Response.success }

    if (-not $isOk) {
        $detail = $Response.detail
        if (-not $detail -and $Response.error) { $detail = $Response.error }
        throw "API indicated failure at $Url`nDetail: $detail"
    }
}

function Hit {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Url,
        [string]$Body
    )

    $response = Invoke-SmokeRequest -Method $Method -Url $Url -Body $Body
    if ($response -is [string]) {
        throw "Non-JSON response from ${Url}: $response"
    }
    return $response
}

Write-Host "Running smoke checks against $($script:BaseUri)" -ForegroundColor Cyan

Ensure-SmokeSession

$health = Hit -Method 'GET' -Url "$($script:BaseUri)/healthz"
Assert-ApiOk -Response $health -Url '/healthz'

# Account diagnostics
$accountTest = Hit -Method 'POST' -Url "$($script:BaseUri)/api/accounts/1/test"
Assert-ApiOk -Response $accountTest -Url '/api/accounts/1/test'

# Watcher controls
$startWatcher = Hit -Method 'POST' -Url "$($script:BaseUri)/api/accounts/1/monitor/start"
Assert-ApiOk -Response $startWatcher -Url '/api/accounts/1/monitor/start'
if ([string]::IsNullOrWhiteSpace($startWatcher.state)) {
    throw "Watcher start returned empty state"
}

$stopWatcher = Hit -Method 'POST' -Url "$($script:BaseUri)/api/accounts/1/monitor/stop"
Assert-ApiOk -Response $stopWatcher -Url '/api/accounts/1/monitor/stop'
if ($stopWatcher.state -notin @('stopped', 'stopping')) {
    throw "Unexpected watcher stop state: $($stopWatcher.state)"
}

Write-Host "SMOKE OK" -ForegroundColor Green
