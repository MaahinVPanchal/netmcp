# NetMCP – Deploy to Lambda & test with curl

## Build (Windows)

Use Linux wheels so the build doesn't pull Windows-only deps (e.g. pywin32):

```powershell
cd netmcp\infra
$env:PIP_PLATFORM = "manylinux2014_x86_64"
sam build
```

## Deploy

```powershell
sam deploy --no-confirm-changeset --parameter-overrides "FrontendUrl=https://voicezero.ai" "BackendUrl=https://kitebvteletvheszekfg.supabase.co" --capabilities CAPABILITY_IAM
```

Or use your own URLs and optionally `--guided` for first-time setup.

## Test with curl / PowerShell

Base URL (from stack output): `https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod/`

**Health**
```powershell
Invoke-RestMethod -Uri "https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod/health" -Method Get
```

**MCP tools/list**
```powershell
$body = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
Invoke-RestMethod -Uri "https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod/mcp-http" -Method Post -Body $body -ContentType "application/json"
```

**fetch_and_extract_apis (no browser, works on Lambda)**
```powershell
$body = '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"fetch_and_extract_apis","arguments":{"url":"https://voicezero.ai","fetch_linked_js":true,"max_js":3}}}'
(Invoke-RestMethod -Uri "https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text
```

**get_backend_urls**
```powershell
$body = '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_backend_urls","arguments":{"limit":20}}}'
(Invoke-RestMethod -Uri "https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text
```

**get_network_logs**
```powershell
$body = '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_network_logs","arguments":{"limit":10}}}'
(Invoke-RestMethod -Uri "https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod/mcp-http" -Method Post -Body $body -ContentType "application/json").result.content[0].text
```

## Bash/curl equivalents

```bash
BASE="https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod"
curl -s "$BASE/health"
curl -s -X POST "$BASE/mcp-http" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
curl -s -X POST "$BASE/mcp-http" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"fetch_and_extract_apis","arguments":{"url":"https://voicezero.ai"}}}'
```
