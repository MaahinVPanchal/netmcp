# NetMCP – AI Network Inspector

Capture browser and proxy network traffic, store it in DynamoDB, and query it via MCP tools (e.g. from Cursor).

**MVP stack:** API Gateway → Lambda → DynamoDB (no EC2).

## Project structure

```
netmcp/
├── mcp-server/       # FastAPI + FastMCP + DynamoDB
├── proxy/            # Node.js HTTP proxy (logs to ingest)
├── browser-extension/# Chrome extension (DevTools → ingest)
├── infra/            # AWS SAM (Lambda + DynamoDB)
├── .env.example      # Env template
└── mcp.json          # MCP client config (set URL to your backend)
```

## Backend URL (mcp.json / .env)

- **MCP client (Cursor, etc.):** Point `mcp.json` at your server’s MCP base URL, e.g. `https://your-api.com/mcp` or `http://localhost:8000/mcp`.
- **Proxy / extension:** Use the same base URL for ingest:
  - Proxy: `MCP_INGEST_URL=http://localhost:8000/ingest` (or your deployed URL).
  - Extension: set “Backend URL” in the popup (e.g. `http://localhost:8000`).

Copy `.env.example` to `.env` and set:

- `MCP_INGEST_URL` – used by the proxy to post logs.
- `MCP_SERVER_URL` – used by MCP clients (e.g. Cursor) to talk to the MCP server.
- `INGEST_FILTER_URLS` – optional comma-separated hosts (e.g. `voicezero.ai,kitebvteletvheszekfg.supabase.co`). When set, only requests whose URL contains one of these strings are stored; others are skipped. Leave empty to store all.
- `AWS_REGION` / `DYNAMO_TABLE` – for DynamoDB (when using dynamodb storage).
- `STORAGE_BACKEND` – set to `file` or `txt` to store logs in a JSONL text file instead of DynamoDB.
- `NETMCP_LOG_FILE` – path for file storage (e.g. netmcp_logs.txt). Used when STORAGE_BACKEND=file.

## Voicezero.ai + Supabase

- **Frontend:** voicezero.ai  
- **Backend:** `https://kitebvteletvheszekfg.supabase.co`

**How to pass frontend and backend URL**

1. **In .env (recommended)** – In `netmcp/mcp-server/.env` or `netmcp/.env` set:
   - `FRONTEND_URL=https://voicezero.ai` – the page to open in the browser.
   - `BACKEND_URL=https://kitebvteletvheszekfg.supabase.co` – your API/Supabase base (used for filtering and reference; backend requests are captured automatically when you open the frontend).
2. **When calling MCP tools** – You can pass the frontend URL directly, e.g. `navigate_with_playwright(url="https://voicezero.ai")`. If you omit `url`, the tool uses `FRONTEND_URL` from .env.
3. **Visible Chrome window** – To see the browser (e.g. for Google sign-in or to debug "Load failed"), use **headless=false**: call `navigate_with_playwright(url="https://voicezero.ai", headless=false)` or `navigate_to_app(headless=false)`. That opens a real Chrome window; the default is now headless=false so the browser window appears by default.

**Goal:** When a user connects to your MCP (e.g. from Cursor), they see all endpoints from the Network tab — requests from the frontend and to your Supabase backend.

1. Deploy the NetMCP server (Lambda + DynamoDB or Docker). Set `MCP_SERVER_URL` and `MCP_INGEST_URL` to that base URL.
2. In the server `.env`, optionally set `INGEST_FILTER_URLS=voicezero.ai,kitebvteletvheszekfg.supabase.co` so only your app + Supabase traffic is stored.
3. Install the browser extension; in the popup set **NetMCP server URL** to your deployed base URL.
4. In Cursor, set `mcp.json` so `netmcp.url` is your NetMCP base URL + `/mcp`.
5. User opens **voicezero.ai**, opens **DevTools → Network**. The extension sends all requests (including to Supabase) to `/ingest`. MCP tools like `get_network_logs`, `get_failed_requests`, or `search_requests(url_contains="supabase")` return those endpoints.

## Quick start

### Is it working?

- **Server and /health:** Yes — the app starts and `GET /health` returns `{"status":"healthy"}`.
- **/ingest and MCP tools:** They need **DynamoDB** and **IAM** set up:
  1. **Create the table** `netmcp-requests` (e.g. run `sam build && sam deploy --guided` from `netmcp/infra/`, or create the table in AWS Console with primary key `id` (String) and TTL attribute `ttl`).
  2. **Give your IAM user/role** permission to use that table. The identity that runs the server (e.g. IAM user `AwsAiHack`) must be allowed `dynamodb:PutItem`, `dynamodb:GetItem`, `dynamodb:Scan`, `dynamodb:Query`, `dynamodb:DeleteItem`, `dynamodb:BatchWriteItem` on `arn:aws:dynamodb:REGION:ACCOUNT:table/netmcp-requests`. Attach a policy like [DynamoDBCrudPolicy](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-templates.html) for that table, or add the above actions in IAM.

After the table exists and IAM allows access, run the server again; `POST /ingest` and MCP tools will work. Alternatively set STORAGE_BACKEND=file and NETMCP_LOG_FILE=netmcp_logs.txt to use a text file instead of DynamoDB (no AWS needed).

### 1. MCP server (local)

```bash
cd netmcp/mcp-server
pip install -r requirements.txt
# Set AWS credentials and DYNAMO_TABLE (or create table in AWS)
python main.py
# → http://localhost:8000  (ingest: POST /ingest, MCP: /mcp)
```

### 2. Proxy (optional)

```bash
cd netmcp/proxy
npm install
MCP_INGEST_URL=http://localhost:8000/ingest npm start
# → Proxy on :8080, forwards to X-Target-Host or localhost:3000
```

### 3. Browser extension

- Load `netmcp/browser-extension` as an unpacked extension.
- Open popup, set Backend URL to `http://localhost:8000` (or your deployed base URL).
- Open DevTools → Network; traffic is sent to `{backend}/ingest`.

### 4. Cursor / MCP client

Use `mcp.json` (or your client’s config) with the MCP server URL, e.g.:

```json
{
  "mcpServers": {
    "netmcp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Replace with your deployed API base + `/mcp` when using Lambda.

## mcp.json example (Voicezero.ai + Supabase)

**Your stack:**
- **Frontend:** https://voicezero.ai  
- **Backend (Supabase):** https://kitebvteletvheszekfg.supabase.co  
- **NetMCP server:** This app (e.g. `python main.py` → `http://localhost:8000`). The `url` in mcp.json points here, not at voicezero or Supabase.

**Local development – put this in Cursor MCP config or `mcp.json`:**

```json
{
  "mcpServers": {
    "netmcp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**When NetMCP is deployed** (e.g. Lambda or your host), use your base URL + `/mcp`:

```json
{
  "mcpServers": {
    "netmcp": {
      "url": "https://your-netmcp.example.com/mcp"
    }
  }
}
```

**Quick test:** Start the server (`cd netmcp/mcp-server && python main.py`). In Cursor, use **navigate_to_app** (or **navigate_with_playwright** with `url="https://voicezero.ai"` and `headless=false`) to open a visible Chrome window and capture network (including Supabase). Then use **get_network_logs** or **search_requests** with `url_contains="supabase"` to see endpoints.

## MCP tools

- `get_network_logs` – recent requests
- `get_failed_requests` – status ≥ 400
- `get_endpoint_details` – by URL
- `search_requests` – by method, status, URL substring
- `get_slow_requests` – above a time threshold
- `clear_logs` – delete all stored logs
- **`export_network_logs_to_txt`** – export stored logs to a human-readable .txt file.
- **`navigate_with_playwright`** – open a URL in Playwright, capture network, save to storage. Pass **headless=false** to open a visible Chrome window (e.g. for Google sign-in). Omit `url` to use FRONTEND_URL from .env.
- **`navigate_to_app`** – open FRONTEND_URL from .env in a visible browser (headless=false by default). Set FRONTEND_URL and BACKEND_URL in .env.
- **`navigate_with_selenium`** – same using Selenium + Chrome. Run `pip install selenium`.

Auth headers (e.g. Authorization, Cookie) are redacted before storage.

## Deploy (AWS SAM)

```bash
cd netmcp/infra
./deploy.sh
# First run: sam deploy --guided
```

Then set your MCP client and extension/proxy to the API URL from the stack output (e.g. `https://xxx.execute-api.region.amazonaws.com/Prod/`). Ingest = `{url}/ingest`, MCP = `{url}/mcp`.

## Docker (EC2/ECS)

```bash
cd netmcp/mcp-server
docker build -t netmcp .
docker run -p 8000:8000 -e AWS_REGION=us-east-1 -e DYNAMO_TABLE=netmcp-requests netmcp
```

Ensure the container has IAM or env credentials for DynamoDB.
