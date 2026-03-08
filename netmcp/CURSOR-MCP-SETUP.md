# Cursor MCP – NetMCP (voicezero.ai + Supabase)

Use this so Cursor can talk to your NetMCP server and open the frontend in Chrome, then read network tab data.

## 1. mcp.json for Cursor

**Option A – Paste into Cursor**

1. Open **Cursor** → **Settings** (Ctrl+,) → search **MCP** → open **Edit MCP configuration** (or **Cursor Settings → Features → MCP**).
2. Paste this (or merge under `mcpServers`):

```json
{
  "mcpServers": {
    "netmcp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Option B – Use project config file**

Copy `netmcp/cursor-mcp-config.json` into Cursor’s MCP config file. On Windows it is often:

- `%APPDATA%\Cursor\User\globalStorage\cursor.mcp\mcp.json`, or  
- **Settings → MCP** and use “Open config file” if shown.

So either paste the JSON above into that file under `mcpServers`, or set Cursor to use `cursor-mcp-config.json` if your Cursor version supports a project-level path.

**Your stack (already in .env):**

- **Frontend:** https://voicezero.ai  
- **Backend:** https://kitebvteletvheszekfg.supabase.co  
- **NetMCP server:** http://localhost:8000 (run locally; the `url` in mcp.json is `http://localhost:8000/mcp`)

## 2. Run MCP server in CMD

From the repo root:

```cmd
cd d:\Coding\Hanuman\Awsmcp\netmcp
run-mcp-server.bat
```

Or manually:

```cmd
cd d:\Coding\Hanuman\Awsmcp\netmcp\mcp-server
set STORAGE_BACKEND=file
set FRONTEND_URL=https://voicezero.ai
set BACKEND_URL=https://kitebvteletvheszekfg.supabase.co
python main.py
```

Leave this window open. When you see `Uvicorn running on http://0.0.0.0:8000`, Cursor can use the MCP.

## 3. Use in Cursor (open Chrome + network tab)

1. Restart Cursor or reload MCP after adding `mcp.json` so it connects to `http://localhost:8000/mcp`.
2. In the chat, ask to run:
   - **“Run navigate_to_app”** or **“Run navigate_with_playwright with url https://voicezero.ai and headless false”**
3. A **Chrome** window should open on voicezero.ai and NetMCP will capture all network requests (including Supabase).
4. Then ask:
   - **“Get network logs”** → `get_network_logs`
   - **“Search requests that contain supabase”** → `search_requests(url_contains="supabase")`
   - **“Export network logs to netmcp_export.txt”** → `export_network_logs_to_txt`

So: **run the server in CMD** → **add mcp.json to Cursor** → **in Cursor, run navigate_to_app or navigate_with_playwright with headless false** → **then use get_network_logs / search_requests / export**.

## 4. Deploy (use MCP from another machine)

To use NetMCP from another PC or without running CMD locally:

1. Deploy the server (e.g. AWS Lambda with `netmcp/infra` SAM, or a VPS with Docker).
2. Set **FRONTEND_URL** and **BACKEND_URL** in the deployed environment.
3. In Cursor’s mcp.json, set:

```json
"netmcp": {
  "url": "https://your-deployed-netmcp.com/mcp"
}
```

Then run the same tools; the browser will open on the machine where the MCP server runs (e.g. headless on the server), and Cursor will still get network logs from the tools.
