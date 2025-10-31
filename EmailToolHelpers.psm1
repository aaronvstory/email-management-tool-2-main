<#
.SYNOPSIS
    Email Management Tool API Testing Helpers

.DESCRIPTION
    Convenient PowerShell functions for testing the Email Management Tool API.
    Handles session management and CSRF tokens automatically.

    Avoids common PowerShell gotchas like using reserved variables ($home, $host, etc.)

.EXAMPLE
    # Import the module
    Import-Module .\EmailToolHelpers.psm1

    # Login once
    Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"

    # Now make API calls easily
    Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"
    Invoke-EmailToolApi -Method GET -Path "/api/accounts"

    # GET is default, so this works too:
    Invoke-EmailToolApi "/api/stats"

.LINK
    Full documentation: POWERSHELL_HELPERS.md
    Complete example: example-api-usage.ps1

.NOTES
    Author: Email Management Tool
    Version: 1.0
#># Global session state
$script:EmailToolSession = $null
$script:EmailToolBaseUrl = $null
$script:EmailToolCsrfToken = $null

function Connect-EmailTool {
    <#
    .SYNOPSIS
        Login to the Email Management Tool and establish a session.

    .PARAMETER BaseUrl
        Base URL of the Email Management Tool (e.g., http://127.0.0.1:5010)

    .PARAMETER Username
        Username for login (default: admin)

    .PARAMETER Password
        Password for login (default: admin123)

    .EXAMPLE
        Connect-EmailTool -BaseUrl "http://127.0.0.1:5010"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$BaseUrl,

        [Parameter(Mandatory=$false)]
        [string]$Username = "admin",

        [Parameter(Mandatory=$false)]
        [string]$Password = "admin123"
    )

    try {
        Write-Verbose "Connecting to $BaseUrl..."

        # Get login page and CSRF token
        $loginPage = Invoke-WebRequest -Uri "$BaseUrl/login" -UseBasicParsing -SessionVariable sess
        $formCsrf = ($loginPage.Content | Select-String 'name="csrf_token" value="([^"]+)"').Matches[0].Groups[1].Value

        if (-not $formCsrf) {
            throw "Failed to extract CSRF token from login page"
        }

        # Login
        $body = "username=$Username&password=$Password&csrf_token=$formCsrf"
        $loginResp = Invoke-WebRequest -Uri "$BaseUrl/login" `
            -Method POST `
            -ContentType "application/x-www-form-urlencoded" `
            -Body $body `
            -WebSession $sess `
            -UseBasicParsing

        # Check if login was successful (redirect to dashboard or home)
        if ($loginResp.StatusCode -eq 200 -and $loginResp.Content -match "login") {
            throw "Login failed - check credentials"
        }

        # Get meta CSRF token for API calls
        $dashResp = Invoke-WebRequest -Uri "$BaseUrl/dashboard" -WebSession $sess -UseBasicParsing
        $metaCsrf = ($dashResp.Content | Select-String 'meta name="csrf-token" content="([^"]+)"').Matches[0].Groups[1].Value

        if (-not $metaCsrf) {
            throw "Failed to extract meta CSRF token"
        }

        # Store session state
        $script:EmailToolSession = $sess
        $script:EmailToolBaseUrl = $BaseUrl
        $script:EmailToolCsrfToken = $metaCsrf

        Write-Host "✓ Connected to Email Tool at $BaseUrl" -ForegroundColor Green
        Write-Host "  Session established, CSRF token obtained" -ForegroundColor Gray

        return $true
    }
    catch {
        Write-Error "Failed to connect: $_"
        return $false
    }
}

function Disconnect-EmailTool {
    <#
    .SYNOPSIS
        Logout and clear the session.
    #>
    [CmdletBinding()]
    param()

    if ($script:EmailToolSession -and $script:EmailToolBaseUrl) {
        try {
            Invoke-WebRequest -Uri "$script:EmailToolBaseUrl/logout" `
                -WebSession $script:EmailToolSession `
                -UseBasicParsing | Out-Null
            Write-Host "✓ Logged out" -ForegroundColor Green
        }
        catch {
            Write-Warning "Logout request failed (session may have expired)"
        }
    }

    $script:EmailToolSession = $null
    $script:EmailToolBaseUrl = $null
    $script:EmailToolCsrfToken = $null
}

function Invoke-EmailToolApi {
    <#
    .SYNOPSIS
        Call an Email Tool API endpoint with automatic session and CSRF handling.

    .PARAMETER Path
        API path (e.g., /api/accounts, /api/stats)

    .PARAMETER Method
        HTTP method (GET, POST, PUT, DELETE). Default: GET

    .PARAMETER Body
        Request body (for POST/PUT). Can be hashtable (auto-converted to JSON) or string.

    .PARAMETER AsJson
        Parse response as JSON and return object (default: true for application/json responses)

    .EXAMPLE
        Invoke-EmailToolApi "/api/stats"

    .EXAMPLE
        Invoke-EmailToolApi -Method POST -Path "/api/accounts/1/test"

    .EXAMPLE
        $account = @{
            account_name = "Test Account"
            email_address = "test@example.com"
        }
        Invoke-EmailToolApi -Method POST -Path "/api/accounts" -Body $account
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true, Position=0)]
        [string]$Path,

        [Parameter(Mandatory=$false)]
        [ValidateSet('GET', 'POST', 'PUT', 'DELETE', 'PATCH')]
        [string]$Method = 'GET',

        [Parameter(Mandatory=$false)]
        [object]$Body,

        [Parameter(Mandatory=$false)]
        [switch]$AsJson = $true
    )

    if (-not $script:EmailToolSession) {
        Write-Error "Not connected. Run Connect-EmailTool first."
        return
    }

    try {
        $uri = "$script:EmailToolBaseUrl$Path"

        $params = @{
            Uri = $uri
            Method = $Method
            WebSession = $script:EmailToolSession
            UseBasicParsing = $true
        }

        # Add CSRF token for mutations
        if ($Method -in @('POST', 'PUT', 'DELETE', 'PATCH')) {
            $params.Headers = @{ 'X-CSRFToken' = $script:EmailToolCsrfToken }
        }

        # Add body if provided
        if ($Body) {
            if ($Body -is [hashtable] -or $Body -is [PSCustomObject]) {
                $params.Body = ($Body | ConvertTo-Json -Depth 10)
                $params.ContentType = 'application/json'
            } else {
                $params.Body = $Body
            }
        }

        Write-Verbose "$Method $uri"
        $response = Invoke-WebRequest @params

        # Parse JSON responses
        if ($AsJson -and $response.Content) {
            try {
                return ($response.Content | ConvertFrom-Json)
            }
            catch {
                # Not JSON, return raw content
                return $response.Content
            }
        }

        return $response
    }
    catch {
        Write-Error "API call failed: $_"
        if ($_.Exception.Response) {
            Write-Error "Response: $($_.Exception.Response.StatusCode)"
        }
        throw
    }
}

function Get-EmailToolHealth {
    <#
    .SYNOPSIS
        Quick health check (doesn't require authentication).

    .PARAMETER BaseUrl
        Base URL of the Email Management Tool

    .EXAMPLE
        Get-EmailToolHealth -BaseUrl "http://127.0.0.1:5010"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$false)]
        [string]$BaseUrl = $script:EmailToolBaseUrl
    )

    if (-not $BaseUrl) {
        Write-Error "BaseUrl required. Either connect first or provide -BaseUrl parameter."
        return
    }

    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/healthz" -UseBasicParsing

        if ($response.status -eq "healthy") {
            Write-Host "✓ Email Tool is healthy" -ForegroundColor Green
            return $response
        } else {
            Write-Warning "Health check returned: $($response.status)"
            return $response
        }
    }
    catch {
        Write-Error "Health check failed: $_"
        return $null
    }
}

# Convenient aliases
New-Alias -Name "Login-EmailTool" -Value "Connect-EmailTool" -ErrorAction SilentlyContinue
New-Alias -Name "Logout-EmailTool" -Value "Disconnect-EmailTool" -ErrorAction SilentlyContinue
New-Alias -Name "Call-EmailToolApi" -Value "Invoke-EmailToolApi" -ErrorAction SilentlyContinue

# Export functions
Export-ModuleMember -Function Connect-EmailTool, Disconnect-EmailTool, Invoke-EmailToolApi, Get-EmailToolHealth
Export-ModuleMember -Alias Login-EmailTool, Logout-EmailTool, Call-EmailToolApi
