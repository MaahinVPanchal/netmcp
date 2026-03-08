"""Selenium browser automation: navigate and capture network traffic (Chrome performance log)."""
import asyncio
from typing import List

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    webdriver = None
    Options = None
    Service = None
    SELENIUM_AVAILABLE = False


def _capture_network_sync(url: str, headless: bool = True) -> List[dict]:
    if not SELENIUM_AVAILABLE:
        return []
    out: List[dict] = []
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.set_capability("goog:loggingPrefs", {"performance": "all"})
    try:
        driver = webdriver.Chrome(options=opts)
        driver.get(url)
        import time
        time.sleep(2)
        logs = driver.get_log("performance")
        driver.quit()
    except Exception:
        return []
    for entry in logs:
        try:
            import json
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") == "Network.requestWillBeSent":
                params = msg.get("params", {})
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
                })
        except Exception:
            continue
    return out


async def navigate_and_capture_network_selenium(
    url: str, headless: bool = True
) -> List[dict]:
    """Run Selenium Chrome in a thread; return list of request dicts for storage."""
    return await asyncio.to_thread(_capture_network_sync, url, headless)
