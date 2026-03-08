"""Playwright browser automation: navigate and capture network traffic."""
import asyncio
import time
from typing import List, Optional

# Optional: only fail at runtime if playwright not installed
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False


def _capture_network_sync(url: str, headless: bool = False) -> List[dict]:
    if not PLAYWRIGHT_AVAILABLE:
        return []
    requests_log: List[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        def on_request(req):
            requests_log.append({
                "url": req.url,
                "method": req.method,
                "resource_type": getattr(req, "resource_type", "unknown"),
            })

        def on_response(res):
            try:
                req = res.request
                timing = res.request.timing
                response_time = 0
                if timing and hasattr(timing, "response_end") and timing.get("response_end"):
                    response_time = int(timing["response_end"] * 1000)
                for r in requests_log:
                    if r.get("url") == req.url and "status" not in r:
                        r["status"] = res.status
                        r["response_time_ms"] = response_time
                        r["response_headers"] = dict(res.headers)
                        break
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)
        try:
            page.goto(url, wait_until="load", timeout=30000)
            time.sleep(4)
        except Exception:
            pass
        browser.close()

    # Build full entries with defaults
    out = []
    for r in requests_log:
        out.append({
            "url": r.get("url", ""),
            "method": (r.get("method") or "GET").upper(),
            "status": r.get("status", 0),
            "response_time_ms": r.get("response_time_ms", 0),
            "request_headers": {},
            "request_body": "",
            "response_headers": r.get("response_headers") or {},
            "response_body": "",
        })
    return out


async def navigate_and_capture_network(
    url: str, headless: bool = False
) -> List[dict]:
    """Run Playwright in a thread; return list of request dicts for storage. Default headless=False so browser window is visible."""
    return await asyncio.to_thread(_capture_network_sync, url, headless)
