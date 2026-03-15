"""Playwright browser automation: navigate and capture network traffic + console logs."""
import asyncio
import time
from typing import List, Dict, Any

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False

# Max response body size stored per request (10 KB)
MAX_RESPONSE_BODY_SIZE = 10 * 1024


def _capture_network_sync(
    url: str,
    headless: bool = False,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE,
) -> Dict[str, Any]:
    """
    Synchronous Playwright capture. Runs inside asyncio.to_thread.

    Returns:
        Dict with 'requests' (List[dict]) and 'console_logs' (List[dict]).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"requests": [], "console_logs": []}

    requests_log: List[dict] = []
    console_logs: List[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        def on_request(req):
            requests_log.append({
                "url": req.url,
                "method": req.method,
                "resource_type": req.resource_type,
                "request_headers": dict(req.headers),
                "_start_time": time.monotonic(),
            })

        def on_response(res):
            try:
                req_url = res.request.url
                status = res.status
                headers = dict(res.headers)

                # Calculate response time from monotonic clock stored on request
                response_time_ms = 0
                for r in requests_log:
                    if r.get("url") == req_url and "status" not in r:
                        elapsed = time.monotonic() - r.pop("_start_time", time.monotonic())
                        response_time_ms = int(elapsed * 1000)
                        r["status"] = status
                        r["response_time_ms"] = response_time_ms
                        r["response_headers"] = headers

                        if capture_response_bodies:
                            content_type = headers.get("content-type", "").lower()
                            if "application/json" in content_type or "text/" in content_type:
                                try:
                                    body_bytes = res.body()
                                    if body_bytes:
                                        r["response_body"] = body_bytes.decode("utf-8", errors="ignore")[:max_body_size]
                                except Exception:
                                    pass
                        break
            except Exception:
                pass

        def on_console(msg):
            if capture_console_logs:
                console_logs.append({
                    "type": msg.type,
                    "text": msg.text,
                    "location": msg.location if hasattr(msg, "location") else {},
                    "timestamp": time.time(),
                })

        def on_page_error(error):
            if capture_console_logs:
                console_logs.append({
                    "type": "page_error",
                    "text": str(error),
                    "timestamp": time.time(),
                })

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)  # allow late XHR/fetch calls to complete
        except Exception:
            pass
        finally:
            # Always close browser to avoid resource leaks
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    # Normalise entries — fill in any requests that never got a response
    out = []
    for r in requests_log:
        r.pop("_start_time", None)  # clean up if response never fired
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

    return {"requests": out, "console_logs": console_logs}


async def navigate_and_capture_network(
    url: str,
    headless: bool = False,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE,
) -> Dict[str, Any]:
    """
    Async wrapper: runs Playwright in a thread pool and returns captured data.

    Returns:
        Dict with 'requests' (List[dict]) and 'console_logs' (List[dict]).
    """
    return await asyncio.to_thread(
        _capture_network_sync,
        url,
        headless,
        capture_console_logs,
        capture_response_bodies,
        max_body_size,
    )
