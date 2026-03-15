from fastmcp import FastMCP
from typing import Optional
import json
import os
import uuid

_NAVIGATE_NO_PLAYWRIGHT = (
    "Playwright is not installed (e.g. on Lambda there is no browser). "
    "To capture full browser network traffic: run NetMCP locally with storage_backend: 'files' "
    "in mcp.json and install Playwright (pip install playwright && playwright install chromium). "
    "Alternatively use fetch_and_extract_apis(url) to discover API/backend URLs from the page "
    "source without a browser (works on Lambda)."
)

_VALID_LOG_TYPES = {"error", "warning", "log", "info", "debug"}
_MAX_LIMIT = 500


def _normalize_url(url: Optional[str]) -> Optional[str]:
    """Ensure URL has a scheme. Returns None if url is empty."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _validate_limit(limit: int) -> int:
    """Clamp limit to a safe range."""
    return max(1, min(limit, _MAX_LIMIT))


def _validate_threshold(threshold_ms: int) -> int:
    return max(0, threshold_ms)


def register_tools(mcp: FastMCP, db):  # db can be DynamoDBClient or FileStorage

    # ── Navigation tools ──────────────────────────────────────────────────────

    @mcp.tool
    async def navigate_to_app(
        headless: bool = False,
        capture_console_logs: bool = True,
        capture_response_bodies: bool = False,
    ) -> str:
        """
        Open FRONTEND_URL (your app URL) in Chrome via Playwright, capture all network
        requests (including backend/API calls), and save them to storage.
        Use this first to open the browser and populate the network log.
        Set capture_response_bodies=true to also capture JSON response payloads (up to 10 KB).
        """
        from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        target = _normalize_url(os.getenv("FRONTEND_URL", ""))
        if not target:
            return json.dumps({
                "error": "FRONTEND_URL is not set. Add frontend_url in mcp.json (netmcp section) or FRONTEND_URL in .env"
            })

        session_id = str(uuid.uuid4())
        result = await navigate_and_capture_network(
            target,
            headless=headless,
            capture_console_logs=capture_console_logs,
            capture_response_bodies=capture_response_bodies,
        )
        entries = result.get("requests", [])
        console_logs = result.get("console_logs", [])

        for e in entries:
            e["capture_session_id"] = session_id
            await db.save_request(e)

        if console_logs and capture_console_logs:
            await db.save_console_logs(session_id, console_logs)

        return json.dumps({
            "status": "ok",
            "url": target,
            "session_id": session_id,
            "requests_captured": len(entries),
            "console_logs_captured": len(console_logs),
        })

    @mcp.tool
    async def navigate_with_playwright(
        url: Optional[str] = None,
        headless: bool = False,
        capture_console_logs: bool = True,
        capture_response_bodies: bool = False,
    ) -> str:
        """
        Open any URL in Chrome via Playwright, capture network traffic, and save to storage.
        Omit url to fall back to FRONTEND_URL from mcp.json.
        Set headless=false to see the browser window.
        Set capture_response_bodies=true to capture JSON response payloads (up to 10 KB).
        On Lambda use fetch_and_extract_apis instead (no browser required).
        """
        from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        target = _normalize_url(url) or _normalize_url(os.getenv("FRONTEND_URL", ""))
        if not target:
            return json.dumps({
                "error": "No URL provided. Pass url= or set frontend_url in mcp.json (netmcp section)."
            })

        session_id = str(uuid.uuid4())
        result = await navigate_and_capture_network(
            target,
            headless=headless,
            capture_console_logs=capture_console_logs,
            capture_response_bodies=capture_response_bodies,
        )
        entries = result.get("requests", [])
        console_logs = result.get("console_logs", [])

        for e in entries:
            e["capture_session_id"] = session_id
            await db.save_request(e)

        if console_logs and capture_console_logs:
            await db.save_console_logs(session_id, console_logs)

        return json.dumps({
            "status": "ok",
            "url": target,
            "session_id": session_id,
            "requests_captured": len(entries),
            "console_logs_captured": len(console_logs),
        })

    @mcp.tool
    async def navigate_with_selenium(
        url: Optional[str] = None,
        headless: bool = False,
        capture_console_logs: bool = True,
    ) -> str:
        """
        Open a URL in Chrome via Selenium, capture network requests, and save to storage.
        Omit url to use FRONTEND_URL from .env.
        Prefer navigate_with_playwright when available — Selenium has limited network capture.
        """
        from browser_selenium import navigate_and_capture_network_selenium, SELENIUM_AVAILABLE
        if not SELENIUM_AVAILABLE:
            return json.dumps({
                "error": "Selenium is not installed. Run: pip install selenium",
                "hint": "Prefer Playwright for richer network capture: pip install playwright && playwright install chromium",
            })

        target = _normalize_url(url) or _normalize_url(os.getenv("FRONTEND_URL", ""))
        if not target:
            return json.dumps({
                "error": "No URL provided. Pass url= or set FRONTEND_URL in .env"
            })

        session_id = str(uuid.uuid4())
        result = await navigate_and_capture_network_selenium(
            target,
            headless=headless,
            capture_console_logs=capture_console_logs,
        )
        entries = result.get("requests", [])
        console_logs = result.get("console_logs", [])

        for e in entries:
            e["capture_session_id"] = session_id
            await db.save_request(e)

        if console_logs and capture_console_logs:
            await db.save_console_logs(session_id, console_logs)

        return json.dumps({
            "status": "ok",
            "url": target,
            "session_id": session_id,
            "requests_captured": len(entries),
            "console_logs_captured": len(console_logs),
        })

    @mcp.tool
    async def fetch_and_extract_apis(
        url: Optional[str] = None,
        fetch_linked_js: bool = True,
        max_js: int = 5,
    ) -> str:
        """
        Discover API/backend URLs from a page without launching a browser (works on Lambda).
        Fetches the page HTML and optionally linked JS files, then extracts API-like URLs
        and saves them to storage so they appear in get_network_logs.
        Use when Playwright/Selenium is unavailable.
        """
        from api_extract import fetch_and_extract_apis as _extract

        target = _normalize_url(url) or _normalize_url(os.getenv("FRONTEND_URL", ""))
        if not target:
            return json.dumps({
                "error": "No URL provided. Pass url= or set frontend_url in mcp.json."
            })

        max_js = max(0, min(max_js, 20))  # clamp to reasonable range

        session_id = str(uuid.uuid4())
        entries = await _extract(target, fetch_linked_js=fetch_linked_js, max_js=max_js)

        if entries and entries[0].get("error"):
            return json.dumps({"error": entries[0]["error"], "url": target})

        for e in entries:
            save_data = {k: v for k, v in e.items() if k != "_synthetic"}
            save_data["capture_session_id"] = session_id
            await db.save_request(save_data)

        urls = [e.get("url", "") for e in entries if e.get("url")]
        return json.dumps({
            "status": "ok",
            "url": target,
            "session_id": session_id,
            "apis_discovered": len(urls),
            "backend_urls": urls[:50],
        })

    # ── Network log retrieval ─────────────────────────────────────────────────

    @mcp.tool
    async def get_network_logs(limit: int = 20, include_bodies: bool = False) -> str:
        """
        Get recent network requests captured from the browser.
        Returns the most recent entries sorted by timestamp descending.
        Set include_bodies=true to include request/response bodies (larger payload).
        Max limit is 500.
        """
        limit = _validate_limit(limit)
        requests = await db.get_recent_requests(limit, include_bodies=include_bodies)
        return json.dumps(requests, indent=2, default=str)

    @mcp.tool
    async def get_failed_requests(limit: int = 20, include_bodies: bool = False) -> str:
        """
        Get network requests that returned an HTTP error status (>= 400).
        Set include_bodies=true to include request/response bodies for deeper debugging.
        Max limit is 500.
        """
        limit = _validate_limit(limit)
        requests = await db.get_failed_requests(limit, include_bodies=include_bodies)
        if not requests:
            return json.dumps({"message": "No failed requests found.", "count": 0})
        return json.dumps(requests, indent=2, default=str)

    @mcp.tool
    async def get_endpoint_details(url: str, include_body: bool = False) -> str:
        """
        Get full request/response details for a specific endpoint URL (exact or partial match).
        Set include_body=true to see the full response body content.
        """
        if not url or not url.strip():
            return json.dumps({"error": "url parameter is required."})

        details = await db.get_by_url(url.strip(), include_body=include_body)
        if not details:
            return json.dumps({
                "error": f"No requests found matching URL: {url}",
                "hint": "Try a shorter substring, or run navigate_with_playwright first to capture traffic.",
            })
        return json.dumps(details, indent=2, default=str)

    @mcp.tool
    async def search_requests(
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        url_contains: Optional[str] = None,
        limit: int = 20,
        include_bodies: bool = False,
    ) -> str:
        """
        Search captured network requests by HTTP method, status code, or URL substring.
        All filters are optional and combinable.
        Set include_bodies=true to include request/response bodies in results.
        Max limit is 500.

        Args:
            method: HTTP method filter, e.g. 'GET', 'POST', 'PUT', 'DELETE'
            status_code: Exact HTTP status code to filter by, e.g. 404, 500
            url_contains: Substring to match against request URLs
            limit: Maximum number of results to return (default 20, max 500)
            include_bodies: Include request/response body content in results
        """
        if method and method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            return json.dumps({"error": f"Invalid HTTP method: {method}"})
        if status_code is not None and not (100 <= status_code <= 599):
            return json.dumps({"error": f"Invalid status code: {status_code}. Must be 100–599."})

        limit = _validate_limit(limit)
        results = await db.search_requests(
            method=method.upper() if method else None,
            status_code=status_code,
            url_contains=url_contains,
            limit=limit,
            include_bodies=include_bodies,
        )
        return json.dumps({
            "count": len(results),
            "results": results,
        }, indent=2, default=str)

    @mcp.tool
    async def get_slow_requests(threshold_ms: int = 1000, include_bodies: bool = False) -> str:
        """
        Get requests whose response time exceeded threshold_ms milliseconds.
        Useful for identifying performance bottlenecks.
        Set include_bodies=true to include request/response bodies.
        """
        threshold_ms = _validate_threshold(threshold_ms)
        results = await db.get_slow_requests(threshold_ms, include_bodies=include_bodies)
        if not results:
            return json.dumps({
                "message": f"No requests found slower than {threshold_ms} ms.",
                "count": 0,
            })
        return json.dumps({
            "threshold_ms": threshold_ms,
            "count": len(results),
            "results": results,
        }, indent=2, default=str)

    @mcp.tool
    async def get_backend_urls(limit: int = 50) -> str:
        """
        Extract unique API/backend-like URLs from stored network logs.
        Filters for URLs containing common API patterns: /api, supabase, graphql,
        /rest, execute-api, webhook.
        Useful for quickly discovering what backend services the frontend talks to.
        """
        limit = _validate_limit(limit)
        requests = await db.get_recent_requests(limit * 2)
        seen: set = set()
        backend_urls = []
        keywords = ("/api", "supabase", "graphql", "rest", "execute-api", "webhook")

        for r in requests:
            u = (r.get("url") or "").strip()
            if not u or u in seen or len(u) < 10:
                continue
            u_lower = u.lower()
            if any(k in u_lower for k in keywords) or "supabase.co" in u:
                seen.add(u)
                backend_urls.append(u)
                if len(backend_urls) >= limit:
                    break

        return json.dumps({"backend_urls": backend_urls, "count": len(backend_urls)})

    # ── Console log retrieval ─────────────────────────────────────────────────

    @mcp.tool
    async def get_console_logs(
        session_id: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: int = 100,
    ) -> str:
        """
        Get browser console logs captured during navigation.

        Args:
            session_id: Filter logs from a specific capture session (use session_id from navigate tools)
            log_type: Filter by log level — 'error', 'warning', 'log', 'info', 'debug'
            limit: Maximum number of log entries to return (default 100, max 500)
        """
        if log_type and log_type.lower() not in _VALID_LOG_TYPES:
            return json.dumps({
                "error": f"Invalid log_type: '{log_type}'.",
                "valid_types": sorted(_VALID_LOG_TYPES),
            })

        limit = _validate_limit(limit)
        logs = await db.get_console_logs(session_id=session_id, limit=limit * 2)

        if log_type:
            logs = [l for l in logs if l.get("type") == log_type.lower()]

        logs = sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

        summary: dict = {}
        for log in logs:
            t = log.get("type", "unknown")
            summary[t] = summary.get(t, 0) + 1

        return json.dumps({
            "count": len(logs),
            "summary": summary,
            "logs": logs,
        }, indent=2, default=str)

    @mcp.tool
    async def get_console_errors(limit: int = 50) -> str:
        """
        Get only console errors and uncaught page errors from browser captures.
        Shortcut for get_console_logs(log_type='error').
        """
        limit = _validate_limit(limit)
        logs = await db.get_console_logs(limit=limit * 2)
        error_logs = [l for l in logs if l.get("type") in ("error", "page_error")]
        error_logs = sorted(error_logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

        return json.dumps({
            "count": len(error_logs),
            "errors": error_logs,
        }, indent=2, default=str)

    # ── Export / maintenance ──────────────────────────────────────────────────

    @mcp.tool
    async def export_network_logs_to_txt(
        file_path: str = "netmcp_export.txt",
        limit: int = 100,
        include_bodies: bool = False,
    ) -> str:
        """
        Export stored network logs to a human-readable text file.
        Set include_bodies=true to include response bodies in the export (up to 2 KB each).
        The file is written relative to the mcp-server directory unless an absolute path is given.
        """
        limit = _validate_limit(limit)

        # Prevent path traversal
        if ".." in file_path:
            return json.dumps({"error": "Invalid file path: '..' is not allowed."})

        base = os.path.dirname(os.path.abspath(__file__))
        path = file_path if os.path.isabs(file_path) else os.path.join(base, file_path)

        requests = await db.get_recent_requests(limit, include_bodies=include_bodies)
        lines = []
        for i, r in enumerate(requests, 1):
            lines.append(f"--- Request {i} ---")
            lines.append(f"URL:           {r.get('url', '')}")
            lines.append(f"Method:        {r.get('method', '')}  Status: {r.get('status', '')}  Time: {r.get('response_time_ms', 0)} ms")
            lines.append(f"Resource Type: {r.get('resource_type', 'unknown')}")
            lines.append(f"Timestamp:     {r.get('timestamp', '')}")
            if include_bodies:
                body = r.get("response_body", "")
                if body:
                    truncated = body[:2000]
                    suffix = "... [truncated]" if len(body) > 2000 else ""
                    lines.append(f"Response Body: {truncated}{suffix}")
            lines.append("")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except OSError as exc:
            return json.dumps({"error": f"Failed to write file: {exc}"})

        return json.dumps({
            "status": "exported",
            "path": path,
            "count": len(requests),
            "include_bodies": include_bodies,
        })

    @mcp.tool
    async def clear_logs() -> str:
        """
        Delete all stored network logs and console logs.
        This action is irreversible — use with care.
        """
        await db.clear_all()
        return json.dumps({"status": "cleared", "message": "All network logs have been deleted."})
