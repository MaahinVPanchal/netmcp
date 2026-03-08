# Claude Code / Claude Desktop – NetMCP (mcp-http vs /mcp)

## Why Claude Code was connecting to `/mcp` instead of `mcp-http`

- **Cursor** uses the URL you put in `args` as-is, so `.../Prod/mcp-http` works.
- **Claude Code / Claude Desktop** sometimes normalizes the MCP server URL and can end up calling `.../Prod/mcp` or `.../Prod/mcp/` (e.g. if it treats the base as `.../Prod` and appends `mcp` for the MCP endpoint).
- Our Lambda exposes a **stateless** JSON-RPC endpoint at **`/mcp-http`**, not a streaming session at `/mcp`. So when the client hit `/mcp` or `/mcp/`, it got:
  - **404 "Session not found"** when POSTing (streamable HTTP expects a session).
  - **400** when falling back to SSE (Lambda doesn’t support that SSE endpoint).

## Fix 1: Config must use the full `mcp-http` URL

In **Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json`) or **Claude Code** (e.g. `~/.claude.json` or project `.mcp.json`), set the **full** URL including the path:

```json
{
  "mcpServers": {
    "netmcp": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://r06a66ywad.execute-api.us-east-1.amazonaws.com/Prod/mcp-http"
      ]
    }
  }
}
```

- Use **`/Prod/mcp-http`** (no trailing slash).
- Do **not** use `.../Prod` or `.../Prod/mcp` or `.../Prod/mcp/` in the args, or the client may treat it as a base and append `/mcp`, which used to fail.

## Fix 2: Server now accepts POST `/mcp` and `/mcp/`

So that clients that only send requests to `.../Prod/mcp` or `.../Prod/mcp/` still work, the NetMCP server now handles:

- `POST .../Prod/mcp-http` (preferred)
- `POST .../Prod/mcp`
- `POST .../Prod/mcp/`

All use the same stateless JSON-RPC handler. After you **redeploy** the Lambda (or run the server locally), Claude Code should work even if it uses `.../Prod/mcp/`.

## If it still fails

1. **Confirm the URL in the running app**  
   Check the log line that shows `args`; the last argument must be `.../Prod/mcp-http` (or at least `.../Prod/mcp`/`.../Prod/mcp/` after the server update).

2. **Claude Code vs Desktop**  
   - **Claude Desktop:** `%APPDATA%\Claude\claude_desktop_config.json` (Windows).  
   - **Claude Code (CLI):** `~/.claude.json` or project `.mcp.json` / `.claude/settings.json`.  
   Edit the file that your running app actually reads.

3. **Restart** Claude Code / Claude Desktop after changing the config.

4. **Redeploy** Lambda so the new POST `/mcp` and `/mcp/` routes are live.
