"""Playwright browser automation: navigate and capture network traffic + console logs."""
import asyncio
import time
from typing import List, Optional, Dict, Any

# Optional: only fail at runtime if playwright not installed
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False


# Max size for response bodies to store (10KB)
MAX_RESPONSE_BODY_SIZE = 10 * 1024


def _capture_network_sync(
    url: str,
    headless: bool = False,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE
) -> Dict[str, Any]:
    """
    Capture network requests and console logs using Playwright.

    Args:
        url: URL to navigate to
        headless: Run browser in headless mode
        capture_console_logs: Capture browser console logs (errors, warnings, etc.)
        capture_response_bodies: Capture response bodies for JSON responses (up to max_body_size)
        max_body_size: Maximum response body size in bytes (default 10KB)

    Returns:
        Dict with 'requests' (List[dict]) and 'console_logs' (List[dict])
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"requests": [], "console_logs": []}

    requests_log: List[dict] = []
    console_logs: List[dict] = []
    response_bodies: Dict[str, str] = {}  # url -> body

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        def on_request(req):
            requests_log.append({
                "url": req.url,
                "method": req.method,
                "resource_type": getattr(req, "resource_type", "unknown"),
                "request_headers": dict(req.headers) if hasattr(req, "headers") else {},
            })

        def on_response(res):
            try:
                req = res.request
                timing = res.request.timing
                response_time = 0
                if timing and hasattr(timing, "response_end") and timing.get("response_end"):
                    response_time = int(timing["response_end"] * 1000)

                # Find matching request and update
                for r in requests_log:
                    if r.get("url") == req.url and "status" not in r:
                        r["status"] = res.status
                        r["response_time_ms"] = response_time
                        r["response_headers"] = dict(res.headers)

                        # Optionally capture response body for JSON responses
                        if capture_response_bodies:
                            content_type = res.headers.get("content-type", "").lower()
                            if "application/json" in content_type or "text/" in content_type:
                                try:
                                    # Only attempt to get body for certain content types
                                    body = res.body()
                                    if body:
                                        text_body = body.decode('utf-8', errors='ignore')[:max_body_size]
                                        response_bodies[req.url] = text_body
                                        r["response_body"] = text_body
                                except Exception:
                                    pass  # Body may not be available
                        break
            except Exception:
                pass

        def on_console(msg):
            """Capture console messages from the browser."""
            if capture_console_logs:
                console_logs.append({
                    "type": msg.type,  # 'log', 'debug', 'info', 'error', 'warning'
                    "text": msg.text,
                    "location": msg.location if hasattr(msg, "location") else {},
                    "timestamp": time.time(),
                })

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", on_console)

        # Also capture page errors
        def on_page_error(error):
            if capture_console_logs:
                console_logs.append({
                    "type": "page_error",
                    "text": str(error),
                    "timestamp": time.time(),
                })

        page.on("pageerror", on_page_error)

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait a bit more for any late network requests
            time.sleep(2)
        except Exception:
            pass
        finally:
            browser.close()

    # Build full entries with defaults
    out = []
    for r in requests_log:
        out.append({
            "url": r.get("url", ""),
            "method": (r.get("method") or "GET").upper(),
            "status": r.get("status", 0),
            "response_time_ms": r.get("response_time_ms", 0),
            "request_headers": r.get("request_headers") or {},
            "request_body": "",
            "response_headers": r.get("response_headers") or {},
            "response_body": r.get("response_body", ""),
            "resource_type": r.get("resource_type", "unknown"),
        })

    return {
        "requests": out,
        "console_logs": console_logs,
    }


async def navigate_and_capture_network(
    url: str,
    headless: bool = False,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE
) -> Dict[str, Any]:
    """
    Run Playwright in a thread; return network requests and console logs.

    Args:
        url: URL to navigate to
        headless: Run browser in headless mode
        capture_console_logs: Capture browser console logs
        capture_response_bodies: Capture response bodies for JSON responses
        max_body_size: Maximum response body size in bytes

    Returns:
        Dict with 'requests' (List[dict]) and 'console_logs' (List[dict])
    """
    return await asyncio.to_thread(
        _capture_network_sync,
        url,
        headless,
        capture_console_logs,
        capture_response_bodies,
        max_body_size
    )


# Backward compatibility - maintain old function signature for existing code
def _capture_network_sync_legacy(url: str, headless: bool = False) -> List[dict]:
    """Legacy function that returns just the requests list for backward compatibility."""
    result = _capture_network_sync(url, headless, capture_console_logs=False, capture_response_bodies=False)
    return result.get("requests", [])


async def navigate_and_capture_network_legacy(url: str, headless: bool = False) -> List[dict]:
    """Legacy async function for backward compatibility."""
    return await asyncio.to_thread(_capture_network_sync_legacy, url, headless)
