# Test NetMCP on localhost:8000 (run with server started via run-mcp-server.bat)
$base = "http://localhost:8000"

Write-Host "1. Health (GET /health)" -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri "$base/health" -Method Get
    Write-Host "   OK: $($h | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "   FAIL: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Is the server running? Run run-mcp-server.bat first." -ForegroundColor Yellow
    exit 1
}

Write-Host "`n2. MCP initialize (POST /mcp with Accept header)" -ForegroundColor Cyan
$headers = @{ "Content-Type" = "application/json"; "Accept" = "application/json, text/event-stream" }
$body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
try {
    $r = Invoke-WebRequest -Uri "$base/mcp" -Method POST -Headers $headers -Body $body -UseBasicParsing
    Write-Host "   Status: $($r.StatusCode)" -ForegroundColor Green
    if ($r.Content -match '"serverInfo":\{"name":"(\w+)"') { Write-Host "   Server: $($Matches[1])" -ForegroundColor Green }
} catch {
    Write-Host "   FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nDone. If both pass, set Cursor mcp.json to: " -ForegroundColor Gray
Write-Host '  "netmcp": { "url": "http://localhost:8000/mcp" }' -ForegroundColor Gray
