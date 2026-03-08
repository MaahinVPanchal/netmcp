# Test NetMCP – navigate to FRONTEND_URL and get network tab

## 1. Start the server with file storage (required)

So the MCP tools work without AWS, start the server from CMD **with file storage**:

```cmd
cd d:\Coding\Hanuman\Awsmcp\netmcp
run-mcp-server.bat
```

Leave this window open. You should see: `Uvicorn running on http://0.0.0.0:8000`.

(If you start `python main.py` without the batch file, the server may use DynamoDB and you’ll get permission errors.)

---

## 2. In Cursor – open FRONTEND_URL and capture network

The netmcp panel lists **navigate_to_app** and **navigate_with_playwright** as the first two buttons. No need to click Show more.

- **navigate_to_app** – Opens FRONTEND_URL (https://voicezero.ai) in Chrome and captures network. Click this first.
- **navigate_with_playwright** – Same, with optional url and headless.

**To test:**

1. Click **navigate_to_app** (no parameters).  
   - A **Chrome** window opens at https://voicezero.ai.  
   - All network requests (including to your backend/Supabase) are saved.

2. Then click **get_network_logs** to see the captured requests (network tab data).

3. Optional: **search_requests** with `url_contains`: `supabase` to see only backend calls.

---

## 3. Quick sequence

| Step | Action in netmcp panel |
|------|-------------------------|
| 1 | **navigate_to_app** (first button – Chrome opens at voicezero.ai) |
| 2 | **get_network_logs** (view captured requests) |
| 3 | **search_requests** with `url_contains`: `supabase` (only backend) |

FRONTEND_URL and BACKEND_URL are set in `mcp-server/.env`; `navigate_to_app` uses FRONTEND_URL automatically.
