# NetMCP – AI Network Inspector

Capture browser network traffic, console logs, and API requests. Store in **DynamoDB** or **JSONL file**, query via MCP tools from **[Cursor](https://cursor.com)** or **[Claude Code](https://claude.ai/code)**.

**Stack:** FastAPI + FastMCP + (DynamoDB | file). Deploy: API Gateway → Lambda → DynamoDB.

---

## What's New (v3.2.0)

- **Console Log Capture**: Capture browser console logs (errors, warnings, info) alongside network requests
- **Optional Response Bodies**: Capture JSON response payloads (up to 10KB) with `capture_response_bodies=true`
- **Cost Protection**: Built-in AWS billing alerts ($15 threshold), cost anomaly detection, Lambda concurrency limits
- **Enhanced Querying**: Get logs with/without bodies, filter console logs by type

---

## Project structure

```
netmcp/
├── mcp-server/       # FastAPI + FastMCP (Python)
│   ├── browser_playwright.py  # Network + console capture
│   ├── browser_selenium.py    # Selenium alternative
│   ├── tools.py              # MCP tools
│   ├── db.py                 # DynamoDB storage
│   └── storage_file.py       # File storage
├── proxy/            # Node.js HTTP proxy (logs to /ingest)
├── browser-extension/# Chrome extension (DevTools → /ingest)
├── infra/            # AWS SAM (Lambda + DynamoDB + Billing Alerts)
│   ├── template.yaml         # CloudFormation template
│   └── iam-policy-netmcp-deploy.json  # Deployment IAM policy
├── .env.example      # Env template
└── mcp.json          # MCP client config
```

---

## MCP Tools

### Navigation & Capture

| Tool | Description |
|------|-------------|
| **navigate_to_app** | Open `FRONTEND_URL` in Chrome, capture **network + console logs**, save to storage. Set `capture_response_bodies=true` for JSON payloads. |
| **navigate_with_playwright** | Navigate to any URL with Playwright. Capture network, console logs, optional response bodies. |
| **navigate_with_selenium** | Selenium alternative for network capture. |
| **fetch_and_extract_apis** | **No browser.** Parse HTML/JS for API URLs. Works on Lambda. |

### Query & Analysis

| Tool | Description |
|------|-------------|
| **get_network_logs** | Recent requests. Set `include_bodies=true` for response content. |
| **get_network_logs_with_bodies** | Get logs **with** request/response bodies included. |
| **get_failed_requests** | Requests with status ≥ 400. Set `include_bodies=true` for error payloads. |
| **get_failed_requests_with_bodies** | Failed requests **with** bodies for debugging. |
| **get_endpoint_details** | Full details for a URL. Set `include_body=true` for response content. |
| **get_endpoint_details_with_body** | Endpoint details **with** full response body. |
| **search_requests** | Filter by method, status, URL substring. Optional body inclusion. |
| **get_slow_requests** | Requests above time threshold. |
| **get_backend_urls** | Unique API/backend URLs from logs. |

### Console Logs

| Tool | Description |
|------|-------------|
| **get_console_logs** | Browser console logs. Filter by `session_id` or `log_type` (error/warning/log/info/debug). |
| **get_console_errors** | Only console errors and page errors. |

### Management

| Tool | Description |
|------|-------------|
| **clear_logs** | Clear all stored logs. |
| **export_network_logs_to_txt** | Export to text file. Set `include_bodies=true` for full content. |

---

## Capture Coverage

### ✅ What's Captured

- **HTTP(S) requests** - All browser network traffic
- **Frontend assets** - JS, CSS, images, fonts
- **XHR/fetch calls** - API requests
- **Supabase edge functions** - REST/GraphQL endpoints
- **Console logs** - log, debug, info, warn, error, page errors
- **Response bodies** (optional) - JSON/text up to 10KB when requested

### ❌ What's NOT Captured (Limitations)

| Protocol | Status |
|----------|--------|
| WebSocket frames | Initial HTTP upgrade only, not individual frames |
| WebRTC | Not captured |
| gRPC over non-HTTP | Not captured |
| Response bodies | Only captured when `capture_response_bodies=true` (JSON/text only) |
| Client-side caches | Requests from Service Workers without network call |

---

## Storage: files vs DynamoDB

In **mcp.json** or **.env**:

| Setting | Values | Use case |
|--------|--------|----------|
| `storage_backend` | `files` \| `dynamodb` | `files` = local JSONL; `dynamodb` = AWS Lambda |
| `netmcp_log_file` | Path (e.g. `netmcp_logs.txt`) | For file storage |

**Local:** Set `storage_backend: "files"` in `mcp.json`, install Playwright.
**Lambda:** Uses DynamoDB with TTL (24h auto-cleanup).

---

## Configuration (mcp.json / .env)

```json
{
  "mcpServers": {
    "netmcp": {
      "command": "npx",
      "args": ["mcp-remote", "https://YOUR_API.execute-api.us-east-1.amazonaws.com/Prod/mcp-http"]
    }
  },
  "netmcp": {
    "frontend_url": "https://your-app.com",
    "backend_url": "https://your-project.supabase.co",
    "storage_backend": "files"
  }
}
```

**Environment variables:**
- `FRONTEND_URL` - Default URL for navigation tools
- `BACKEND_URL` - Reference for filtering
- `STORAGE_BACKEND` - `files` or `dynamodb`
- `INGEST_FILTER_URLS` - Comma-separated hosts to filter (e.g. `your-app.com,supabase.co`)

---

## AWS Cost Protection (Built-in)

The deployment includes multiple safeguards to keep costs under $20/month:

1. **Billing Alert** - CloudWatch alarm at $15 estimated monthly charges
2. **Cost Anomaly Detection** - Automatic alerts for unusual spending
3. **Lambda Reserved Concurrency** - Max 10 concurrent executions
4. **DynamoDB On-Demand** - Pay per request (no provisioned capacity)
5. **TTL** - Data auto-expires after 24 hours
6. **Log Retention** - CloudWatch logs kept for 7 days
7. **Daily Cleanup** - Scheduled Lambda removes old records

**Estimated monthly costs (moderate usage):**
- Lambda: ~$0.50 (128MB, occasional invocations)
- DynamoDB: ~$1-5 (on-demand, with TTL)
- API Gateway: ~$3-5 (if using heavily)
- CloudWatch: ~$0.50
- **Total: ~$5-12/month**

---

## Quick Start

### 1. Local Development

```bash
cd netmcp/mcp-server
pip install -r requirements.txt
pip install playwright && playwright install chromium

# Create .env
echo "FRONTEND_URL=https://your-app.com" > .env
echo "STORAGE_BACKEND=files" >> .env

python main.py
# → http://localhost:8000
```

### 2. Cursor / Claude Code Config

**Local:**
```json
{
  "mcpServers": {
    "netmcp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Deployed:**
```json
{
  "mcpServers": {
    "netmcp": {
      "command": "npx",
      "args": ["mcp-remote", "https://xxx.execute-api.region.amazonaws.com/Prod/mcp-http"]
    }
  }
}
```

---

## Deploy (AWS SAM)

```bash
cd netmcp/infra

# Build
export PIP_PLATFORM=manylinux2014_x86_64  # Windows
sam build

# Deploy with cost protection
sam deploy \
  --no-confirm-changeset \
  --parameter-overrides \
    "FrontendUrl=https://your-app.com" \
    "BackendUrl=https://your-project.supabase.co" \
    "AlertEmail=your-email@example.com" \
    "MonthlyBudget=15" \
  --capabilities CAPABILITY_IAM
```

See **[infra/DEPLOY.md](infra/DEPLOY.md)** for detailed deployment steps.

---

## Usage Examples

### Capture with Console Logs
```python
# Navigate and capture everything
navigate_to_app(
    headless=False,
    capture_console_logs=True,
    capture_response_bodies=True
)
```

### Get Console Errors
```python
# After navigation, get all JavaScript errors
get_console_errors(limit=50)
```

### Debug Failed Requests
```python
# Get failed requests with their error response bodies
get_failed_requests_with_bodies(limit=20)
```

### Search with Body Inclusion
```python
# Find POST requests to supabase with full bodies
search_requests(
    method="POST",
    url_contains="supabase",
    include_bodies=True
)
```

---

## Docker (Optional)

```bash
cd netmcp/mcp-server
docker build -t netmcp .
docker run -p 8000:8000 \
  -e AWS_REGION=us-east-1 \
  -e DYNAMO_TABLE=netmcp-requests \
  netmcp
```
