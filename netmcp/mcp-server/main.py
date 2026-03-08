from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from tools import register_tools
import uvicorn
import os
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
