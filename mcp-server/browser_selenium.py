"""Selenium browser automation: navigate and capture network traffic + console logs."""
import asyncio
import json
import time
from typing import List, Dict, Any

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    webdriver = None
    Options = None
    SELENIUM_AVAILABLE = False

# Max response body size stored per request (10 KB)
MAX_RESPONSE_BODY_SIZE = 10 * 1024


def _capture_network_sync(
    url: str,
    headless: bool = True,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE,
) -> Dict[str, Any]:
    """
    Synchronous Selenium capture. Runs inside asyncio.to_thread.

    Note: Selenium has limited network capture compared to Playwright.
    Response bodies are not available via the performance log API.

    Returns:
        Dict with 'requests' (List[dict]) and 'console_logs' (List[dict]).
    """
    if not SELENIUM_AVAILABLE:
        return {"requests": [], "console_logs": []}

    out: List[dict] = []
    console_logs: List[dict] = []

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})

    driver = None
    try:
        driver = webdriver.Chrome(options=opts)
        driver.get(url)
        time.sleep(2)  # allow network activity to settle

        perf_logs = driver.get_log("performance")

        if capture_console_logs:
            try:
                for entry in driver.get_log("browser"):
                    console_logs.append({
                        "type": entry.get("level", "log").lower(),
                        "text": entry.get("message", ""),
                        "timestamp": entry.get("timestamp", time.time()),
                        "source": "browser_log",
                    })
            except Exception:
                pass

    except Exception as exc:
        return {
            "requests": [],
            "console_logs": [{"type": "error", "text": str(exc), "timestamp": time.time()}],
        }
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    for entry in perf_logs:
        try:
            msg = json.loads(entry["message"])["message"]
            method = msg.get("method", "")
            params = msg.get("params", {})

            if method == "Network.requestWillBeSent":
                req = params.get("request", {})
                out.append({
                    "url": req.get("url", ""),
                    "method": (req.get("method") or "GET").upper(),
                    "status": 0,
                    "response_time_ms": 0,
                    "request_headers": req.get("headers", {}),
                    "request_body": "",
                    "response_headers": {},
                    "response_body": "",
                    "resource_type": params.get("type", "unknown"),
                })

            elif method == "Network.responseReceived":
                response = params.get("response", {})
                req_url = response.get("url", "")
                for r in out:
                    if r.get("url") == req_url and r.get("status") == 0:
                        r["status"] = response.get("status", 0)
                        r["response_headers"] = response.get("headers", {})
                        timing = response.get("timing") or {}
                        r["response_time_ms"] = int(timing.get("receiveHeadersEnd", 0))
                        break

        except Exception:
            continue

    return {"requests": out, "console_logs": console_logs}


async def navigate_and_capture_network_selenium(
    url: str,
    headless: bool = True,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE,
) -> Dict[str, Any]:
    """
    Async wrapper: runs Selenium in a thread pool and returns captured data.

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
