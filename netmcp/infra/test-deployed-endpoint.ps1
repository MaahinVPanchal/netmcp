# Test NetMCP LIVE (AWS) endpoint - same as Cursor uses
$base = "https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod"
$mcpHeaders = @{ "Content-Type" = "application/json"; "Accept" = "application/json, text/event-stream" }
$mcpBody = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"cursor","version":"1.0"}}}'

Write-Host "=== Testing LIVE NetMCP (AWS) ===" -ForegroundColor Cyan
Write-Host "URL: $base" -ForegroundColor Gray
Write-Host ""

Write-Host "1. Health (GET /health)" -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri "$base/health" -Method Get
    Write-Host "   OK: $($h | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "   FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n2. MCP initialize (POST /mcp with Accept header)" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/mcp" -Method POST -Headers $mcpHeaders -Body $mcpBody -UseBasicParsing
    Write-Host "   Status: $($r.StatusCode)" -ForegroundColor Green
    if ($r.Content -match '"serverInfo":\{"name":"(\w+)"') { Write-Host "   Server: $($Matches[1])" -ForegroundColor Green }
    Write-Host "   Content (first 200 chars): $($r.Content.Substring(0, [Math]::Min(200, $r.Content.Length)))..." -ForegroundColor Gray
} catch {
    Write-Host "   FAIL: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) { Write-Host "   Body: $($_.ErrorDetails.Message)" -ForegroundColor Gray }
    Write-Host "`n   If 403: Check CloudWatch Logs for netmcp Lambda - see if request reached it and what it returned." -ForegroundColor Yellow
}

Write-Host "`nDone." -ForegroundColor Gray
