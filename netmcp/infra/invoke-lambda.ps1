# Invoke NetMCP Lambda directly via AWS CLI (no API Gateway).
# Use this to test that /mcp and tools load correctly inside Lambda.
# Requires: AWS CLI configured (aws configure) and same region as deployment.

param(
    [string] $FunctionName = "",  # e.g. netmcp-NetMCPFunction-XXXXXXXXX
    [ValidateSet("initialize", "tools-list", "health")]
    [string] $Test = "initialize"
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$eventsDir = Join-Path $scriptDir "lambda-events"

if (-not $FunctionName) {
    Write-Host "Resolving NetMCP function name..." -ForegroundColor Gray
    $name = aws lambda list-functions --query "Functions[?contains(FunctionName, 'NetMCP')].FunctionName | [0]" --output text 2>$null
    if (-not $name -or $name -eq "None") {
        Write-Host "ERROR: No NetMCP Lambda found. Deploy first (sam deploy) or pass -FunctionName <name>." -ForegroundColor Red
        Write-Host "  Example: .\invoke-lambda.ps1 -FunctionName netmcp-NetMCPFunction-abc123xyz" -ForegroundColor Gray
        exit 1
    }
    $FunctionName = $name
    Write-Host "  Using: $FunctionName" -ForegroundColor Gray
}

$payloadFile = switch ($Test) {
    "initialize" { Join-Path $eventsDir "post-mcp-initialize.json" }
    "tools-list"  { Join-Path $eventsDir "post-mcp-tools-list.json" }
    "health"      { $null }
}

$outFile = Join-Path $scriptDir "lambda-response.json"

if ($Test -eq "health") {
    $healthEvent = @{
        resource = "/"
        path     = "/health"
        httpMethod = "GET"
        headers   = @{}
        requestContext = @{ path = "/health"; stage = "Prod" }
    } | ConvertTo-Json -Compress
    $payloadFile = Join-Path $env:TEMP "netmcp-health-event.json"
    $healthEvent | Set-Content -Path $payloadFile -Encoding utf8
}

if (-not (Test-Path $payloadFile)) {
    Write-Host "ERROR: Payload file not found: $payloadFile" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Invoking Lambda: $FunctionName" -ForegroundColor Cyan
Write-Host "Test: $Test  (payload: $payloadFile)" -ForegroundColor Gray
Write-Host ""

# AWS CLI expects file path; on Windows use forward slashes or absolute path for file://
$payloadPath = (Resolve-Path $payloadFile).Path -replace "\\", "/"
$payloadUri = "file:///$payloadPath"

aws lambda invoke `
    --function-name $FunctionName `
    --payload $payloadUri `
    --cli-binary-format raw-in-base64-out `
    $outFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "Lambda invoke failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

$response = Get-Content $outFile -Raw
$parsed = $response | ConvertFrom-Json

$status = $parsed.statusCode
$body = $parsed.body
if ($parsed.body) {
    try {
        $bodyObj = $parsed.body | ConvertFrom-Json
        $body = ($bodyObj | ConvertTo-Json -Depth 10)
    } catch {}
}

Write-Host "Response statusCode: $status" -ForegroundColor $(if ($status -eq 200) { "Green" } else { "Yellow" })
Write-Host "Response body:" -ForegroundColor Cyan
Write-Host $body
Write-Host ""
Write-Host "Full response file: $outFile" -ForegroundColor Gray

if ($Test -eq "initialize" -and $body -match "serverInfo") {
    Write-Host "MCP initialize OK - server responded." -ForegroundColor Green
}
if ($Test -eq "tools-list" -and $body -match "tools") {
    Write-Host "Tools list OK." -ForegroundColor Green
}
