"""Selenium browser automation: navigate and capture network traffic + console logs - OPTIMIZED for speed."""
import asyncio
import time
from typing import List, Dict, Any

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    webdriver = None
    Options = None
    Service = None
    DesiredCapabilities = None
    SELENIUM_AVAILABLE = False


# Max size for response bodies to store (10KB)
MAX_RESPONSE_BODY_SIZE = 10 * 1024

# Cached driver for reuse
_driver_cache = None


def _get_driver(headless: bool = True):
    """Get or create a cached Chrome driver."""
    global _driver_cache

    if _driver_cache is not None:
        try:
            # Quick check if driver is still alive
            _driver_cache.current_url
            return _driver_cache
        except Exception:
            _driver_cache = None

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")

    # Speed optimizations
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-images")  # Block images for speed
    opts.add_argument("--disable-javascript")  # Faster if JS not needed
    opts.add_argument("--blink-settings=imagesEnabled=false")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-setuid-sandbox")
    opts.add_argument("--disable-logging")
    opts.add_argument("--disable-popup-blocking")

    # Enable performance logging for network capture
    opts.set_capability("goog:loggingPrefs", {"performance": "all", "browser": "ALL"})

    _driver_cache = webdriver.Chrome(options=opts)
    return _driver_cache


def _close_driver():
    """Close the cached driver."""
    global _driver_cache
    if _driver_cache:
        try:
            _driver_cache.quit()
        except Exception:
            pass
        _driver_cache = None


def _capture_network_sync(
    url: str,
    headless: bool = True,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE,
    fast_mode: bool = True,  # NEW: Fast mode with minimal waits
) -> Dict[str, Any]:
    """
    Capture network requests and console logs using Selenium.

    Args:
        url: URL to navigate to
        headless: Run browser in headless mode
        capture_console_logs: Capture browser console logs (errors, warnings, etc.)
        capture_response_bodies: Capture response bodies (limited support in Selenium)
        max_body_size: Maximum response body size in bytes (default 10KB)
        fast_mode: Use fast capture with minimal waits (default True)

    Returns:
        Dict with 'requests' (List[dict]) and 'console_logs' (List[dict])
    """
    if not SELENIUM_AVAILABLE:
        return {"requests": [], "console_logs": []}

    out: List[dict] = []
    console_logs: List[dict] = []

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")

    # Speed optimizations
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-images")
    opts.add_argument("--blink-settings=imagesEnabled=false")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-setuid-sandbox")
    opts.add_argument("--disable-logging")
    opts.add_argument("--disable-popup-blocking")

    # Enable performance logging for network capture
    opts.set_capability("goog:loggingPrefs", {"performance": "all", "browser": "ALL"})

    try:
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(20)  # 20 second timeout

        # Navigate with fast wait strategy
        driver.get(url)

        # OPTIMIZED: Reduced from fixed 2 seconds to conditional wait
        if fast_mode:
            # Fast mode: minimal wait for initial network activity
            time.sleep(0.3)  # Just 300ms for initial requests to start
        else:
            # Legacy mode: fixed 2 second wait
            time.sleep(2)

        # Get performance logs (network)
        logs = driver.get_log("performance")

        # Get browser logs (console)
        if capture_console_logs:
            try:
                browser_logs = driver.get_log("browser")
                for entry in browser_logs:
                    console_logs.append({
                        "type": entry.get("level", "log").lower(),
                        "text": entry.get("message", ""),
                        "timestamp": entry.get("timestamp", time.time()),
                        "source": "browser_log",
                    })
            except Exception:
                pass

        driver.quit()
    except Exception as e:
        return {"requests": [], "console_logs": [{"type": "error", "text": str(e)}]}

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
                    "resource_type": params.get("type", "unknown"),
                })
            elif msg.get("method") == "Network.responseReceived":
                params = msg.get("params", {})
                response = params.get("response", {})
                req_url = response.get("url", "")
                # Update existing request with response info
                for r in out:
                    if r.get("url") == req_url and r.get("status") == 0:
                        r["status"] = response.get("status", 0)
                        r["response_headers"] = response.get("headers", {})
                        r["response_time_ms"] = int(response.get("timing", {}).get("receiveHeadersEnd", 0))
                        break
        except Exception:
            continue

    return {
        "requests": out,
        "console_logs": console_logs,
    }


async def navigate_and_capture_network_selenium(
    url: str,
    headless: bool = True,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE
) -> Dict[str, Any]:
    """
    Run Selenium Chrome in a thread; return network requests and console logs.

    Args:
        url: URL to navigate to
        headless: Run browser in headless mode
        capture_console_logs: Capture browser console logs
        capture_response_bodies: Capture response bodies (limited support)
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


# Backward compatibility - maintain old function signature
def _capture_network_sync_legacy(url: str, headless: bool = True) -> List[dict]:
    """Legacy function that returns just the requests list."""
    result = _capture_network_sync(url, headless, capture_console_logs=False, capture_response_bodies=False)
    return result.get("requests", [])


async def navigate_and_capture_network_selenium_legacy(url: str, headless: bool = True) -> List[dict]:
    """Legacy async function for backward compatibility."""
    return await asyncio.to_thread(_capture_network_sync_legacy, url, headless)
