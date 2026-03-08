from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from tools import register_tools
import uvicorn
import os
import json
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Single config: load FRONTEND_URL, BACKEND_URL from mcp.json if present
from config_from_mcp_json import load_netmcp_config
load_netmcp_config()

from storage import get_storage
db = get_storage()


def create_app():
    """Build FastAPI app with MCP mounted. Used for both local server and Lambda (per-invocation)."""
    mcp = FastMCP("NetMCP")
    register_tools(mcp, db)
    mcp_app = mcp.http_app(path="/")

    @asynccontextmanager
    async def app_lifespan(_app):
        async with mcp_app.lifespan(mcp_app):
            yield

    api = FastAPI(
        title="NetMCP - AI Network Inspector",
        lifespan=app_lifespan,
        redirect_slashes=False,
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.mount("/mcp", mcp_app)

    # Stateless HTTP endpoint for Lambda compatibility (no SSE/session required)
    # This allows mcp-remote to work with AWS Lambda
    @api.post("/mcp-http")
    async def mcp_http_endpoint(request: Request):
        """Stateless HTTP endpoint for MCP JSON-RPC requests."""
        try:
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})
            req_id = body.get("id")

            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "resources": {"subscribe": False, "listChanged": True}
                        },
                        "serverInfo": {"name": "NetMCP", "version": "3.1.0"}
                    }
                }
            elif method == "tools/list":
                tools = [
                    {
                        "name": "navigate_to_app",
                        "description": "Open FRONTEND_URL (your app URL) in Chrome, capture all network requests (including backend/API), and save to storage. Click this first to open the browser and capture network tab data.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "headless": {"type": "boolean", "description": "Run browser in headless mode", "default": False}
                            }
                        }
                    },
                    {
                        "name": "navigate_with_playwright",
                        "description": "Open a URL in Chrome (Playwright), capture network, save to storage. Omit url to use FRONTEND_URL from mcp.json. Set headless=false to see the browser window.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "URL to navigate to (optional, uses FRONTEND_URL if not provided)"},
                                "headless": {"type": "boolean", "description": "Run browser in headless mode", "default": False}
                            }
                        }
                    },
                    {
                        "name": "get_network_logs",
                        "description": "Get recent network requests captured from the developer's browser",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Maximum number of logs to return", "default": 20}
                            }
                        }
                    },
                    {
                        "name": "get_failed_requests",
                        "description": "Get only failed network requests (status >= 400)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Maximum number of failed requests to return", "default": 20}
                            }
                        }
                    },
                    {
                        "name": "get_endpoint_details",
                        "description": "Get full request and response details for a specific endpoint URL",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "The endpoint URL to get details for"}
                            },
                            "required": ["url"]
                        }
                    },
                    {
                        "name": "search_requests",
                        "description": "Search network requests by method (GET/POST), status code, or URL substring",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "method": {"type": "string", "description": "HTTP method to filter by (GET, POST, etc.)"},
                                "status_code": {"type": "integer", "description": "HTTP status code to filter by"},
                                "url_contains": {"type": "string", "description": "URL substring to search for"},
                                "limit": {"type": "integer", "description": "Maximum number of results", "default": 20}
                            }
                        }
                    },
                    {
                        "name": "clear_logs",
                        "description": "Clear all stored network logs",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "get_slow_requests",
                        "description": "Get requests slower than threshold_ms milliseconds",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "threshold_ms": {"type": "integer", "description": "Response time threshold in milliseconds", "default": 1000}
                            }
                        }
                    },
                    {
                        "name": "export_network_logs_to_txt",
                        "description": "Export stored network logs to a human-readable text file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string", "description": "Path for the output file", "default": "netmcp_export.txt"},
                                "limit": {"type": "integer", "description": "Maximum number of logs to export", "default": 100}
                            }
                        }
                    },
                    {
                        "name": "navigate_with_selenium",
                        "description": "Open a URL in Chrome via Selenium, capture network requests, and save them to storage",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "URL to navigate to (optional, uses FRONTEND_URL if not provided)"},
                                "headless": {"type": "boolean", "description": "Run browser in headless mode", "default": False}
                            }
                        }
                    },
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": tools}
                }
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})

                # Map tool calls to actual functions
                result = None
                if tool_name == "navigate_to_app":
                    from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE
                    if not PLAYWRIGHT_AVAILABLE:
                        result = {"error": "Playwright not installed"}
                    else:
                        target = os.getenv("FRONTEND_URL", "").strip()
                        if not target:
                            result = {"error": "Set frontend_url in mcp.json"}
                        else:
                            entries = await navigate_and_capture_network(target, headless=tool_args.get("headless", False))
                            for e in entries:
                                await db.save_request(e)
                            result = {"status": "ok", "url": target, "requests_captured": len(entries)}
                elif tool_name == "navigate_with_playwright":
                    from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE
                    if not PLAYWRIGHT_AVAILABLE:
                        result = {"error": "Playwright not installed"}
                    else:
                        target = tool_args.get("url") or os.getenv("FRONTEND_URL", "").strip()
                        if not target:
                            result = {"error": "No URL provided"}
                        else:
                            entries = await navigate_and_capture_network(target, headless=tool_args.get("headless", False))
                            for e in entries:
                                await db.save_request(e)
                            result = {"status": "ok", "url": target, "requests_captured": len(entries)}
                elif tool_name == "get_network_logs":
                    requests = await db.get_recent_requests(tool_args.get("limit", 20))
                    result = requests
                elif tool_name == "get_failed_requests":
                    requests = await db.get_failed_requests(tool_args.get("limit", 20))
                    result = requests
                elif tool_name == "search_requests":
                    requests = await db.search_requests(
                        method=tool_args.get("method"),
                        status_code=tool_args.get("status_code"),
                        url_contains=tool_args.get("url_contains"),
                        limit=tool_args.get("limit", 20)
                    )
                    result = requests
                elif tool_name == "clear_logs":
                    await db.clear_all()
                    result = {"status": "cleared"}
                elif tool_name == "get_slow_requests":
                    requests = await db.get_slow_requests(tool_args.get("threshold_ms", 1000))
                    result = requests
                elif tool_name == "get_endpoint_details":
                    details = await db.get_by_url(tool_args.get("url", ""))
                    result = details or {"error": "URL not found"}
                elif tool_name == "export_network_logs_to_txt":
                    requests = await db.get_recent_requests(tool_args.get("limit", 100))
                    file_path = tool_args.get("file_path", "netmcp_export.txt")
                    base = os.path.dirname(os.path.abspath(__file__))
                    path = file_path if os.path.isabs(file_path) else os.path.join(base, file_path)
                    lines = []
                    for i, r in enumerate(requests, 1):
                        lines.append(f"--- Request {i} ---")
                        lines.append(f"URL: {r.get('url', '')}")
                        lines.append(f"Method: {r.get('method', '')}  Status: {r.get('status', '')}  Time: {r.get('response_time_ms', 0)}ms")
                        lines.append(f"Timestamp: {r.get('timestamp', '')}")
                        lines.append("")
                    text = "\n".join(lines)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)
                    result = {"status": "exported", "path": path, "count": len(requests)}
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]}
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": body.get("id") if 'body' in dir() else None,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            }

    @api.get("/mcp-http")
    async def mcp_http_get():
        """Health check for HTTP endpoint."""
        return {"status": "MCP HTTP endpoint ready", "version": "3.1.0"}

    @api.post("/ingest")
    async def ingest_request(request: Request):
        try:
            data = await request.json()
        except Exception as e:
            return {"status": "error", "message": f"Invalid JSON: {e}"}, 500
        filter_urls = os.getenv("INGEST_FILTER_URLS", "").strip()
        if filter_urls:
            url = (data.get("url") or "")
            allowed = [s.strip().lower() for s in filter_urls.split(",") if s.strip()]
            if allowed and not any(h in url.lower() for h in allowed):
                return {"status": "skipped", "reason": "url_not_in_filter"}
        try:
            await db.save_request(data)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
        return {"status": "ok"}

    @api.get("/health")
    def health():
        return {"status": "healthy"}

    @api.get("/routes")
    def list_routes():
        routes = []
        for r in api.routes:
            if hasattr(r, "methods") and hasattr(r, "path"):
                for method in r.methods - {"HEAD", "OPTIONS"}:
                    routes.append({"method": method, "path": r.path})
            elif hasattr(r, "path") and hasattr(r, "routes"):
                routes.append({"method": "(mount)", "path": r.path})
        return {"base_url": "See NetMCPApiUrl in stack outputs", "routes": routes}

    @api.post("/api/navigate")
    async def api_navigate(headless: bool = False):
        target = os.getenv("FRONTEND_URL", "").strip()
        if not target:
            return {"error": "Set frontend_url in mcp.json or FRONTEND_URL in .env"}, 400
        if not target.startswith(("http://", "https://")):
            target = "https://" + target
        from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright not installed"}, 503
        entries = await navigate_and_capture_network(target, headless=headless)
        for e in entries:
            await db.save_request(e)
        return {"status": "ok", "url": target, "requests_captured": len(entries)}

    @api.get("/api/failed_requests")
    async def api_failed_requests(limit: int = 20):
        requests = await db.get_failed_requests(limit)
        return requests

    return api


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Lambda handler for AWS SAM (API Gateway → Lambda)
# Create app per invocation so StreamableHTTPSessionManager.run() is only called once per instance
# (the library forbids calling run() twice on the same instance; Mangum runs lifespan per request).
try:
    from mangum import Mangum

    def handler(event, context):
        rc = event.get("requestContext") or {}
        http_ctx = rc.get("http") or {}
        path = event.get("rawPath") or event.get("path") or http_ctx.get("path") or rc.get("path") or "/"
        if path.startswith("/Prod"):
            path = path[4:] or "/"
        if path.rstrip("/") == "/mcp" and path != "/mcp/":
            path = "/mcp/"
        event["rawPath"] = path
        event["path"] = path
        if rc:
            rc["path"] = path
            if http_ctx:
                http_ctx["path"] = path
        print(f"[NetMCP] normalized_path={path}")
        lambda_app = create_app()
        mangum = Mangum(lambda_app, lifespan="on")
        return mangum(event, context)
except ImportError:
    handler = None
