# NetMCP – AI Network Inspector

Capture browser and proxy network traffic, store it in **DynamoDB** or a **JSONL file**, and query it via MCP tools from **[Cursor](https://cursor.com)** or **[Claude Code](https://claude.ai/code)**.

**Stack:** FastAPI + FastMCP + (DynamoDB | file). Deploy: API Gateway → Lambda → DynamoDB (no EC2).

---

## Project structure

```
netmcp/
├── mcp-server/       # FastAPI + FastMCP (Python)
├── proxy/            # Node.js HTTP proxy (logs to /ingest)
├── browser-extension/# Chrome extension (DevTools → /ingest)
├── infra/            # AWS SAM (Lambda + DynamoDB)
├── .env.example      # Env template
└── mcp.json          # MCP client config (frontend_url, backend_url, storage_backend)
```

---

## MCP tools (Cursor & Claude Code)

| Tool | Description |
|------|-------------|
| **navigate_to_app** | Open `FRONTEND_URL` in Chrome (Playwright), capture all network requests, save to storage. |
| **navigate_with_playwright** | Same; pass `url` or use `FRONTEND_URL`. Use `headless=false` to see the browser. On Lambda, use **fetch_and_extract_apis** instead. |
| **fetch_and_extract_apis** | **No browser.** GET a URL, parse HTML/JS for API-like URLs (Supabase, `/api`, etc.), save to storage. **Works on Lambda.** |
| **get_backend_urls** | Return unique backend/API URLs from stored logs (e.g. from navigate or fetch_and_extract_apis). |
| **get_network_logs** | Recent stored requests. |
| **get_failed_requests** | Requests with status ≥ 400 (e.g. failed Supabase edge functions). |
| **get_endpoint_details** | Full details for a given URL. |
| **search_requests** | Filter by method, status code, or URL substring (e.g. `url_contains: "supabase"`). |
| **get_slow_requests** | Requests above a time threshold. |
| **clear_logs** | Clear all stored logs. |
| **export_network_logs_to_txt** | Export logs to a .txt file. |
| **navigate_with_selenium** | Same as Playwright but via Selenium (optional). |

Auth headers (Authorization, Cookie, etc.) are redacted before storage.

---

## Storage: files vs DynamoDB

In **mcp.json** (under `netmcp`) or in **.env**:

| Setting | Values | Use case |
|--------|--------|----------|
| **storage_backend** | `files` \| `file` \| `dynamodb` | `files` = JSONL file (local); `dynamodb` = AWS (Lambda). |
| **netmcp_log_file** / **NETMCP_LOG_FILE** | Path, e.g. `netmcp_logs.txt` | Used when `storage_backend` is `files`. |

- **Local:** Set `storage_backend: "files"` in `mcp.json`; install Playwright for `navigate_with_playwright`. Logs go to `netmcp_logs.txt` in the mcp-server directory.
- **Lambda:** Uses DynamoDB (set in `infra/template.yaml`). Use **fetch_and_extract_apis** to discover backend URLs without a browser.

---

## Backend URL & frontend URL (mcp.json / .env)

- **frontend_url** – Default URL for navigate tools and fetch_and_extract_apis (e.g. `https://voicezero.ai`).
- **backend_url** – Your API/Supabase base (for reference/filtering). Backend requests are captured when you open the frontend in the browser or discover them via fetch_and_extract_apis.

**Example mcp.json** (Cursor / Claude Code):

```json
{
  "mcpServers": {
    "netmcp": {
      "command": "npx",
      "args": ["mcp-remote", "https://YOUR_API.execute-api.us-east-1.amazonaws.com/Prod/mcp-http"]
    }
  },
  "netmcp": {
    "frontend_url": "https://voicezero.ai",
    "backend_url": "https://your-project.supabase.co",
    "storage_backend": "files"
  }
}
```

Replace the `mcp-remote` URL with your deployed Lambda base + `/mcp-http`, or `http://localhost:8000` for local.

---

## VoiceZero.ai + Supabase

- **Frontend:** voicezero.ai  
- **Backend:** e.g. `https://kitebvteletvheszekfg.supabase.co`

1. Set **frontend_url** and **backend_url** in `mcp.json` or `.env`.
2. **Local:** Use **navigate_with_playwright**(url="https://voicezero.ai", headless=false) to capture traffic (including Supabase edge functions). Then **get_failed_requests** or **search_requests**(url_contains="supabase").
3. **Lambda:** Use **fetch_and_extract_apis**(url="https://voicezero.ai") to discover API URLs; then **get_network_logs** / **get_backend_urls** to inspect.

Optional: **INGEST_FILTER_URLS** – comma-separated hosts; only requests whose URL contains one of these are stored. Example: `voicezero.ai,kitebvteletvheszekfg.supabase.co`.

---

## Quick start

### 1. MCP server (local)

```bash
cd netmcp/mcp-server
pip install -r requirements.txt
# Optional: .env with FRONTEND_URL, BACKEND_URL, STORAGE_BACKEND=files
python main.py
# → http://localhost:8000  (ingest: POST /ingest, MCP: /mcp, health: /health)
```

### 2. Cursor / Claude Code

Point MCP at your server. **Local:**

```json
{
  "mcpServers": {
    "netmcp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Deployed Lambda:** use `mcp-remote` with your `https://xxx.execute-api.region.amazonaws.com/Prod/mcp-http` URL (see root [README.md](../README.md)).

### 3. Optional: proxy & browser extension

- **Proxy:** `cd netmcp/proxy && MCP_INGEST_URL=http://localhost:8000/ingest npm start` → proxy on :8080, forwards to ingest.
- **Extension:** Load `netmcp/browser-extension` as unpacked; set Backend URL in popup; DevTools → Network traffic goes to `{backend}/ingest`.

---

## Deploy (AWS SAM)

```bash
cd netmcp/infra
export PIP_PLATFORM=manylinux2014_x86_64   # Windows
sam build
sam deploy --no-confirm-changeset --parameter-overrides "FrontendUrl=https://your-app.com" "BackendUrl=https://your-supabase.supabase.co" --capabilities CAPABILITY_IAM
```

See **[infra/DEPLOY.md](infra/DEPLOY.md)** for full steps and curl/PowerShell tests.

---

## Docker (EC2/ECS)

```bash
cd netmcp/mcp-server
docker build -t netmcp .
docker run -p 8000:8000 -e AWS_REGION=us-east-1 -e DYNAMO_TABLE=netmcp-requests netmcp
```

Ensure the container has IAM or env credentials for DynamoDB when using `storage_backend=dynamodb`.
