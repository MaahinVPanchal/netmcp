from fastmcp import FastMCP
from typing import Optional
import json
import os
import uuid

# Message when Playwright is not available (e.g. on Lambda)
_NAVIGATE_NO_PLAYWRIGHT = (
    "Playwright is not installed (e.g. on Lambda there is no browser). "
    "To capture full browser network traffic: run NetMCP locally with storage_backend: 'files' in mcp.json and install Playwright (pip install playwright && playwright install chromium). "
    "Alternatively use fetch_and_extract_apis(url) to discover API/backend URLs from the page source without a browser (works on Lambda)."
)


def register_tools(mcp: FastMCP, db):  # db can be DynamoDBClient or FileStorage
    # --- Register navigate tools FIRST so they appear in Cursor's netmcp panel (first 6) ---
    @mcp.tool
    async def navigate_to_app(
        headless: bool = False,
        capture_console_logs: bool = True,
        capture_response_bodies: bool = False,
    ) -> str:
        """
        Open FRONTEND_URL (your app URL) in Chrome, capture all network requests (including backend/API),
        save to storage. Click this first to open the browser and capture network tab data.
        Set capture_response_bodies=true to capture JSON response payloads (up to 10KB).
        """
        from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})
        target = os.getenv("FRONTEND_URL", "").strip()
        if not target:
            return json.dumps({"error": "Set frontend_url in mcp.json (netmcp section) or FRONTEND_URL in .env"})
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

        session_id = str(uuid.uuid4())
        result = await navigate_and_capture_network(
            target,
            headless=headless,
            capture_console_logs=capture_console_logs,
            capture_response_bodies=capture_response_bodies,
        )
        entries = result.get("requests", [])
        console_logs = result.get("console_logs", [])

        # Save each request with session ID
        for e in entries:
            e["capture_session_id"] = session_id
            await db.save_request(e)

        # Save console logs if captured
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
        Open a URL in Chrome (Playwright), capture network, save to storage.
        Omit url to use FRONTEND_URL from mcp.json. Set headless=false to see the browser window.
        Set capture_response_bodies=true to capture JSON response payloads (up to 10KB).
        On Lambda use fetch_and_extract_apis instead.
        """
        from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})
        target = url or os.getenv("FRONTEND_URL", "").strip()
        if not target:
            return json.dumps({"error": "No URL. Set url= or frontend_url in mcp.json (netmcp section)"})
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

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
    async def get_network_logs(limit: int = 20, include_bodies: bool = False) -> str:
        """
        Get recent network requests captured from the developer's browser.
        Set include_bodies=true to include request/response bodies (increases payload size).
        """
        requests = await db.get_recent_requests(limit, include_bodies=include_bodies)
        return json.dumps(requests, indent=2, default=str)

    @mcp.tool
    async def get_network_logs_with_bodies(limit: int = 20) -> str:
        """
        Get recent network requests WITH request/response bodies included.
        Useful for debugging but generates larger payloads.
        """
        requests = await db.get_recent_requests(limit, include_bodies=True)
        return json.dumps(requests, indent=2, default=str)

    @mcp.tool
    async def get_failed_requests(limit: int = 20, include_bodies: bool = False) -> str:
        """
        Get only failed network requests (status >= 400).
        Set include_bodies=true to include request/response bodies for debugging.
        """
        requests = await db.get_failed_requests(limit, include_bodies=include_bodies)
        return json.dumps(requests, indent=2, default=str)

    @mcp.tool
    async def get_failed_requests_with_bodies(limit: int = 20) -> str:
        """
        Get failed network requests (status >= 400) WITH request/response bodies.
        Useful for inspecting error payloads from APIs.
        """
        requests = await db.get_failed_requests(limit, include_bodies=True)
        return json.dumps(requests, indent=2, default=str)

    @mcp.tool
    async def get_endpoint_details(url: str, include_body: bool = False) -> str:
        """
        Get full request/response details for a specific endpoint URL.
        Set include_body=true to see the full response body content.
        """
        details = await db.get_by_url(url, include_body=include_body)
        if not details:
            return json.dumps({"error": f"No requests found for URL: {url}"})
        return json.dumps(details, indent=2, default=str)

    @mcp.tool
    async def get_endpoint_details_with_body(url: str) -> str:
        """
        Get full request/response details INCLUDING the response body for a specific URL.
        Use this when you need to inspect the actual JSON/error payload.
        """
        details = await db.get_by_url(url, include_body=True)
        if not details:
            return json.dumps({"error": f"No requests found for URL: {url}"})
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
        Search network requests by method (GET/POST), status code, or URL substring.
        Set include_bodies=true to include request/response bodies in results.
        """
        results = await db.search_requests(
            method=method,
            status_code=status_code,
            url_contains=url_contains,
            limit=limit,
            include_bodies=include_bodies,
        )
        return json.dumps(results, indent=2, default=str)

    @mcp.tool
    async def clear_logs() -> str:
        """Clear all stored network logs"""
        await db.clear_all()
        return json.dumps({"status": "cleared"})

    @mcp.tool
    async def get_slow_requests(threshold_ms: int = 1000, include_bodies: bool = False) -> str:
        """
        Get requests slower than threshold_ms milliseconds.
        Set include_bodies=true to include request/response bodies.
        """
        results = await db.get_slow_requests(threshold_ms, include_bodies=include_bodies)
        return json.dumps(results, indent=2, default=str)

    @mcp.tool
    async def export_network_logs_to_txt(
        file_path: str = "netmcp_export.txt",
        limit: int = 100,
        include_bodies: bool = False,
    ) -> str:
        """
        Export stored network logs to a human-readable text file.
        Use a filename like netmcp_export.txt.
        Set include_bodies=true to include response bodies in the export.
        """
        requests = await db.get_recent_requests(limit, include_bodies=include_bodies)
        base = os.path.dirname(os.path.abspath(__file__))
        path = file_path if os.path.isabs(file_path) else os.path.join(base, file_path)
        lines = []
        for i, r in enumerate(requests, 1):
            lines.append(f"--- Request {i} ---")
            lines.append(f"URL: {r.get('url', '')}")
            lines.append(f"Method: {r.get('method', '')}  Status: {r.get('status', '')}  Time: {r.get('response_time_ms', 0)}ms")
            lines.append(f"Resource Type: {r.get('resource_type', 'unknown')}")
            lines.append(f"Timestamp: {r.get('timestamp', '')}")

            # Include response body if present
            if include_bodies:
                body = r.get('response_body', '')
                if body:
                    lines.append(f"Response Body: {body[:2000]}{'...' if len(body) > 2000 else ''}")

            lines.append("")
        text = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return json.dumps({"status": "exported", "path": path, "count": len(requests), "include_bodies": include_bodies})

    @mcp.tool
    async def navigate_with_selenium(
        url: Optional[str] = None,
        headless: bool = False,
        capture_console_logs: bool = True,
    ) -> str:
        """
        Open a URL in Chrome via Selenium, capture network requests, and save them to storage.
        If url is omitted, uses FRONTEND_URL from .env.
        """
        from browser_selenium import navigate_and_capture_network_selenium, SELENIUM_AVAILABLE
        if not SELENIUM_AVAILABLE:
            return json.dumps({"error": "Selenium not installed. Run: pip install selenium"})
        target = url or os.getenv("FRONTEND_URL", "").strip()
        if not target:
            return json.dumps({"error": "No URL. Set url= or FRONTEND_URL in .env"})
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

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
        Discover API/backend URLs from a page without a browser (works on Lambda).
        GETs the URL, parses HTML/JS for API-like URLs, saves them to storage.
        Use when Playwright is not available.
        """
        from api_extract import fetch_and_extract_apis as _extract
        target = url or os.getenv("FRONTEND_URL", "").strip()
        if not target:
            return json.dumps({"error": "No URL. Set url= or frontend_url in mcp.json"})

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

    @mcp.tool
    async def get_backend_urls(limit: int = 50) -> str:
        """
        Get unique API/backend-like URLs from stored network logs
        (e.g. from navigate or fetch_and_extract_apis).
        Filters for URLs containing api, supabase, graphql, rest, execute-api.
        """
        requests = await db.get_recent_requests(limit * 2)
        seen = set()
        backend_urls = []
        keywords = ("/api", "supabase", "graphql", "rest", "execute-api", "webhook")
        for r in requests:
            u = (r.get("url") or "").strip()
            if not u or u in seen or len(u) < 10:
                continue
            u_lower = u.lower()
            if any(k in u_lower for k in keywords) or "supabase.co" in u or ".co/rest/" in u_lower:
                seen.add(u)
                backend_urls.append(u)
                if len(backend_urls) >= limit:
                    break
        return json.dumps({"backend_urls": backend_urls, "count": len(backend_urls)})

    @mcp.tool
    async def get_console_logs(
        session_id: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: int = 100,
    ) -> str:
        """
        Get browser console logs captured during navigation.

        Args:
            session_id: Optional session ID to filter logs from a specific capture
            log_type: Filter by log type - 'error', 'warning', 'log', 'info', 'debug'
            limit: Maximum number of logs to return
        """
        logs = await db.get_console_logs(session_id=session_id, limit=limit * 2)

        if log_type:
            logs = [l for l in logs if l.get("type") == log_type.lower()]

        # Sort by timestamp and limit
        logs = sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

        # Summarize by type
        summary = {}
        for log in logs:
            t = log.get("type", "unknown")
            summary[t] = summary.get(t, 0) + 1

        return json.dumps({
            "logs": logs,
            "count": len(logs),
            "summary": summary,
        }, indent=2, default=str)

    @mcp.tool
    async def get_console_errors(limit: int = 50) -> str:
        """Get only console errors and page errors from browser captures."""
        logs = await db.get_console_logs(limit=limit * 2)
        error_logs = [l for l in logs if l.get("type") in ("error", "page_error")]
        error_logs = sorted(error_logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

        return json.dumps({
            "errors": error_logs,
            "count": len(error_logs),
        }, indent=2, default=str)
