# Single config: mcp.json

Put your frontend and backend URLs **in mcp.json** so you don’t need a separate .env for NetMCP.

## 1. Use one mcp.json (for Cursor + NetMCP server)

**In Cursor:** use the same file for MCP connection and for NetMCP config (or point Cursor at the `mcpServers` part).

**Example `mcp.json`** (in your project, e.g. `netmcp/mcp.json` or your repo root):

```json
{
  "mcpServers": {
    "netmcp": {
      "url": "http://localhost:8000/mcp"
    }
  },
  "netmcp": {
    "frontend_url": "https://voicezero.ai",
    "backend_url": "https://kitebvteletvheszekfg.supabase.co"
  }
}
```

- **mcpServers.netmcp.url** – Cursor uses this to connect to the NetMCP server.
- **netmcp.frontend_url** – Page the MCP opens in the browser (e.g. voicezero.ai). Server reads this on startup.
- **netmcp.backend_url** – Your API/Supabase base; used for filtering/reference.

When you start the NetMCP server (e.g. `run-mcp-server.bat`), it looks for `mcp.json` in the netmcp folder (or the path in `NETMCP_CONFIG`) and loads `frontend_url` and `backend_url` from the `netmcp` section. So you only maintain this one file.

## 2. Optional in netmcp

- **ingest_filter_urls** – Comma-separated list of URL substrings to keep (e.g. `"voicezero.ai,kitebvteletvheszekfg.supabase.co"`). If omitted, all requests are stored.

Example with filter:

```json
"netmcp": {
  "frontend_url": "https://voicezero.ai",
  "backend_url": "https://kitebvteletvheszekfg.supabase.co",
  "ingest_filter_urls": "voicezero.ai,kitebvteletvheszekfg.supabase.co"
}
```

## 3. Where the server looks for mcp.json

The server looks for a config file in this order:

1. Path in the **NETMCP_CONFIG** env var (if set).
2. **netmcp/mcp.json** (parent of mcp-server).
3. **mcp-server/mcp.json**.
4. **mcp.json** in the current working directory.

So if you run the server from the netmcp folder (`run-mcp-server.bat`), it will load `netmcp/mcp.json` and use `frontend_url` / `backend_url` from there. No need for a separate .env for these.

## 4. Browser opens and network tab is captured

- **navigate_to_app** uses **frontend_url** from mcp.json (or .env) and opens it in a **visible Chrome** window (headless off by default).
- The page is left open for a few seconds so requests (including Supabase/API) are captured.
- Then use **get_network_logs** or **search_requests(url_contains="supabase")** to see the network tab data.

If the browser doesn’t open: ensure Playwright is installed (`pip install playwright` then `playwright install chromium`). If you run the server over SSH or in a headless environment, the browser can’t be visible there; run the server locally for visible browser capture.
