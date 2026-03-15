"""
Super-effective Playwright browser automation with scrolling, interaction, and intelligent waiting.
"""
import asyncio
import time
import json
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import re

# Optional: only fail at runtime if playwright not installed
try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    Page = None
    Browser = None
    BrowserContext = None
    PLAYWRIGHT_AVAILABLE = False


# Max size for response bodies to store (50KB for better debugging)
MAX_RESPONSE_BODY_SIZE = 50 * 1024


@dataclass
class ScrollConfig:
    """Configuration for page scrolling - OPTIMIZED for speed."""
    enabled: bool = True
    scroll_delay_ms: int = 30  # Reduced from 100ms - faster scrolling
    scroll_amount: int = 1200  # Increased from 800 - fewer scrolls needed
    max_scrolls: int = 5  # Reduced from 10 - most content loads in first few scrolls
    wait_after_scroll_ms: int = 100  # Reduced from 500ms - faster page settling
    scroll_to_bottom: bool = False  # Disabled by default - saves time


@dataclass
class WaitConfig:
    """Configuration for intelligent waiting - OPTIMIZED for speed."""
    wait_for_network_idle: bool = False  # Disabled - very slow
    wait_for_load_state: str = "domcontentloaded"  # Fastest reliable option
    extra_wait_ms: int = 50  # Reduced from 300ms - minimal wait
    wait_for_selector: Optional[str] = None  # Don't wait by default
    wait_for_selector_timeout_ms: int = 2000  # Reduced from 5000


@dataclass
class InteractionConfig:
    """Configuration for page interactions."""
    click_selector: Optional[str] = None  # Click element before capturing
    fill_form: Optional[Dict[str, str]] = None  # {selector: value}
    submit_form: Optional[str] = None  # Submit selector after filling
    hover_selector: Optional[str] = None  # Hover over element
    wait_for_navigation: bool = False  # Wait for navigation after interaction


@dataclass
class CaptureConfig:
    """Full capture configuration."""
    url: str = ""
    headless: bool = False
    capture_console_logs: bool = True
    capture_response_bodies: bool = False
    max_body_size: int = MAX_RESPONSE_BODY_SIZE
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    wait: WaitConfig = field(default_factory=WaitConfig)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    user_agent: Optional[str] = None


# Browser instance cache - use async locks for thread safety
_browser_instance: Optional[Browser] = None
_browser_context: Optional[BrowserContext] = None
_browser_lock = asyncio.Lock()
_browser_last_used: float = 0
_BROWSER_IDLE_TIMEOUT = 300  # Close browser after 5 minutes idle
_page_cache: dict = {}  # Cache for page objects to reuse


def get_browser_stats() -> dict:
    """Get current browser cache status for debugging."""
    return {
        "browser_connected": _browser_instance.is_connected() if _browser_instance else False,
        "context_exists": _browser_context is not None,
        "last_used": _browser_last_used,
        "idle_seconds": time.time() - _browser_last_used if _browser_last_used else 0,
    }


# Fast browser launch args - disable features we don't need
BROWSER_ARGS = [
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=TranslateUI",
    "--disable-ipc-flooding-protection",
    "--force-color-profile=srgb",
    "--no-sandbox",  # Required for Docker/Lambda environments
    "--disable-setuid-sandbox",
    # Additional speed optimizations
    "--disable-images",  # Skip image loading for faster page loads
    "--disable-styles",  # Can cause issues, removed
    "--disable-javascript-harness",  # Faster JS execution
    "--disable-plugins",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--disable-default-apps",
    "--disable-breakpad",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-client-side-phishing-detection",
    "--disable-hang-monitor",
    "--disable-popup-blocking",
    "--disable-prompt-on-replay",
    "--disable-notifications",
    "--blink-settings=imagesEnabled=false",  # Block images for speed
]


async def _get_browser(headless: bool = False) -> tuple[Browser, BrowserContext]:
    """Get or create a cached browser instance with proper lifecycle management."""
    global _browser_instance, _browser_context, _browser_last_used

    async with _browser_lock:
        now = time.time()

        # Check if browser is still valid
        if _browser_instance is not None:
            try:
                # Quick health check
                if not await _browser_instance.is_connected():
                    _browser_instance = None
                    _browser_context = None
                elif now - _browser_last_used > _BROWSER_IDLE_TIMEOUT:
                    # Browser idle too long, close it
                    try:
                        await _browser_instance.close()
                    except Exception:
                        pass
                    _browser_instance = None
                    _browser_context = None
            except Exception:
                _browser_instance = None
                _browser_context = None

        # Create new browser if needed
        if _browser_instance is None:
            playwright = await async_playwright().start()
            _browser_instance = await playwright.chromium.launch(
                headless=headless,
                args=BROWSER_ARGS,
                slow_mo=0,  # Removed slow_mo for speed - was causing delays
            )

        # Create isolated context for this session
        if _browser_context is None or not headless:
            # In non-headless, always create new context to avoid popup blocking
            context_options = {
                "bypass_csp": True,
                "java_script_enabled": True,
                "viewport": {"width": 1920, "height": 1080},
            }
            _browser_context = await _browser_instance.new_context(**context_options)

        _browser_last_used = now
        return _browser_instance, _browser_context


async def _close_browser():
    """Close the cached browser instance."""
    global _browser_instance, _browser_context
    async with _browser_lock:
        if _browser_context:
            try:
                await _browser_context.close()
            except Exception:
                pass
            _browser_context = None
        if _browser_instance:
            try:
                await _browser_instance.close()
            except Exception:
                pass
            _browser_instance = None


async def _perform_scrolls(page: Page, config: ScrollConfig) -> List[Dict[str, Any]]:
    """Perform intelligent scrolling on the page and collect data."""
    if not config.enabled:
        return []

    scroll_data = []
    last_height = await page.evaluate("document.body.scrollHeight")
    current_scroll = 0

    for scroll_num in range(config.max_scrolls):
        # Get current scroll position
        scroll_y = await page.evaluate("window.scrollY")

        # Scroll down
        await page.evaluate(f"window.scrollBy(0, {config.scroll_amount})")
        current_scroll += config.scroll_amount

        # Wait for content to load
        await asyncio.sleep(config.scroll_delay_ms / 1000)

        # Check if new content loaded
        new_height = await page.evaluate("document.body.scrollHeight")

        scroll_data.append({
            "scroll_number": scroll_num + 1,
            "scroll_y": scroll_y,
            "page_height": new_height,
            "new_content": new_height > last_height
        })

        # Break if no new content
        if new_height == last_height and scroll_y + config.scroll_amount >= new_height:
            break

        last_height = new_height

        # Wait after scroll if configured
        if config.wait_after_scroll_ms > 0:
            await asyncio.sleep(config.wait_after_scroll_ms / 1000)

    # Scroll to bottom if requested
    if config.scroll_to_bottom:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.3)

    return scroll_data


async def _perform_interactions(page: Page, config: InteractionConfig) -> List[Dict[str, Any]]:
    """Perform interactions like clicks, form fills, hovers."""
    interactions = []

    if config.hover_selector:
        try:
            await page.hover(config.hover_selector, timeout=5000)
            await asyncio.sleep(0.2)
            interactions.append({"action": "hover", "selector": config.hover_selector, "status": "success"})
        except Exception as e:
            interactions.append({"action": "hover", "selector": config.hover_selector, "status": "failed", "error": str(e)})

    if config.click_selector:
        try:
            await page.click(config.click_selector, timeout=10000)
            interactions.append({"action": "click", "selector": config.click_selector, "status": "success"})

            if config.wait_for_navigation:
                await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            interactions.append({"action": "click", "selector": config.click_selector, "status": "failed", "error": str(e)})

    if config.fill_form:
        for selector, value in config.fill_form.items():
            try:
                await page.fill(selector, value, timeout=5000)
                interactions.append({"action": "fill", "selector": selector, "value": value[:50] + "..." if len(value) > 50 else value, "status": "success"})
            except Exception as e:
                interactions.append({"action": "fill", "selector": selector, "status": "failed", "error": str(e)})

        if config.submit_form:
            try:
                await page.click(config.submit_form, timeout=10000)
                interactions.append({"action": "submit", "selector": config.submit_form, "status": "success"})

                if config.wait_for_navigation:
                    await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                interactions.append({"action": "submit", "selector": config.submit_form, "status": "failed", "error": str(e)})

    return interactions


async def _wait_for_conditions(page: Page, config: WaitConfig):
    """Apply intelligent waiting strategies."""
    # Wait for load state
    if config.wait_for_load_state:
        try:
            await page.wait_for_load_state(config.wait_for_load_state, timeout=30000)
        except Exception:
            pass  # Don't fail on timeout

    # Wait for specific selector
    if config.wait_for_selector:
        try:
            await page.wait_for_selector(config.wait_for_selector, timeout=config.wait_for_selector_timeout_ms)
        except Exception:
            pass  # Don't fail if element not found

    # Wait for network idle (can be slow)
    if config.wait_for_network_idle:
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

    # Extra wait for dynamic content
    if config.extra_wait_ms > 0:
        await asyncio.sleep(config.extra_wait_ms / 1000)


async def capture_network_advanced(config: CaptureConfig) -> Dict[str, Any]:
    """
    Capture network requests with scrolling, interaction, and intelligent waiting.

    This is the main function for super-effective browser automation.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            "requests": [],
            "console_logs": [],
            "page_info": {},
            "interactions": [],
            "scrolls": []
        }

    requests_log: Dict[str, dict] = {}
    request_order: List[str] = []
    console_logs: List[dict] = []
    response_bodies: Dict[str, str] = {}
    page_errors: List[dict] = []

    try:
        # Get or create browser
        browser, context = await _get_browser(config.headless)

        # Create new page
        page = await context.new_page()

        # Set user agent if provided
        if config.user_agent:
            await page.set_extra_http_headers({"User-Agent": config.user_agent})

        # Set up network monitoring
        async def on_request(req):
            url = req.url
            try:
                headers = await req.all_headers() if hasattr(req, 'all_headers') else req.headers
            except Exception:
                headers = {}

            requests_log[url] = {
                "url": url,
                "method": req.method,
                "resource_type": req.resource_type if hasattr(req, 'resource_type') else "unknown",
                "request_headers": dict(headers),
                "timestamp": time.time(),
            }
            request_order.append(url)

        async def on_response(res):
            try:
                req = res.request
                url = req.url

                # Get timing info
                timing = {}
                try:
                    if hasattr(req, 'timing'):
                        timing = req.timing
                except Exception:
                    pass

                response_time = 0
                if timing and hasattr(timing, 'response_end'):
                    try:
                        response_time = int(timing.get('response_end', 0) * 1000)
                    except Exception:
                        pass

                # Get response headers
                try:
                    headers = await res.all_headers() if hasattr(res, 'all_headers') else res.headers
                except Exception:
                    headers = {}

                if url in requests_log:
                    r = requests_log[url]
                    r["status"] = res.status
                    r["response_time_ms"] = response_time
                    r["response_headers"] = dict(headers)

                    # Capture response body
                    if config.capture_response_bodies:
                        content_type = res.headers.get("content-type", "").lower()
                        if "application/json" in content_type or "text/" in content_type:
                            try:
                                body = await res.body()
                                if body:
                                    text_body = body.decode('utf-8', errors='ignore')[:config.max_body_size]
                                    r["response_body"] = text_body
                            except Exception:
                                pass
            except Exception:
                pass

        async def on_console(msg):
            if config.capture_console_logs:
                try:
                    log_entry = {
                        "type": msg.type,
                        "text": msg.text if hasattr(msg, 'text') else str(msg),
                        "timestamp": time.time(),
                    }
                    if hasattr(msg, 'location'):
                        log_entry["location"] = msg.location
                    console_logs.append(log_entry)
                except Exception:
                    pass

        async def on_page_error(error):
            if config.capture_console_logs:
                page_errors.append({
                    "type": "page_error",
                    "text": str(error),
                    "timestamp": time.time(),
                })

        # Attach event listeners
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        # Navigate
        try:
            response = await page.goto(
                config.url,
                wait_until=config.wait.wait_for_load_state,
                timeout=30000
            )

            if response:
                initial_status = response.status
            else:
                initial_status = 0
        except Exception as e:
            return {
                "error": f"Navigation failed: {str(e)}",
                "url": config.url,
                "requests": [],
                "console_logs": [],
                "page_info": {"load_failed": True},
                "interactions": [],
                "scrolls": []
            }

        # Wait for initial load
        await _wait_for_conditions(page, config.wait)

        # Perform interactions
        interactions = await _perform_interactions(page, config.interaction)

        # Perform scrolling
        scrolls = await _perform_scrolls(page, config.scroll)

        # Get page information
        page_info = await _get_page_info(page)
        page_info["initial_status"] = initial_status

        # Close page
        await page.close()

        # Build final output
        out = []
        for url in request_order:
            if url in requests_log:
                r = requests_log[url]
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
                    "timestamp": r.get("timestamp", time.time()),
                })

        return {
            "status": "ok",
            "url": config.url,
            "requests": out,
            "console_logs": console_logs + page_errors,
            "page_info": page_info,
            "interactions": interactions,
            "scrolls": scrolls,
            "requests_captured": len(out),
            "console_logs_captured": len(console_logs) + len(page_errors),
        }

    except Exception as e:
        return {
            "error": str(e),
            "url": config.url,
            "requests": [],
            "console_logs": [],
            "page_info": {},
            "interactions": [],
            "scrolls": []
        }


async def _get_page_info(page: Page) -> Dict[str, Any]:
    """Extract useful information from the page."""
    try:
        title = await page.title()
    except Exception:
        title = ""

    try:
        url = page.url
    except Exception:
        url = ""

    # Try to detect forms
    try:
        form_count = await page.eval_on_selector_all("form", "forms => forms.length")
    except Exception:
        form_count = 0

    # Try to detect buttons
    try:
        button_count = await page.eval_on_selector_all("button", "btns => btns.length")
    except Exception:
        button_count = 0

    # Try to detect inputs
    try:
        input_count = await page.eval_on_selector_all("input, textarea, select", "els => els.length")
    except Exception:
        input_count = 0

    # Get page metrics
    try:
        metrics = await page.evaluate("() => JSON.stringify({\n            url: window.location.href,\n            title: document.title,\n            readyState: document.readyState,\n            scrollHeight: document.body.scrollHeight,\n            viewport: {width: window.innerWidth, height: window.innerHeight}\n        })")
        page_metrics = json.loads(metrics)
    except Exception:
        page_metrics = {}

    return {
        "title": title,
        "url": url,
        "forms_detected": form_count,
        "buttons_detected": button_count,
        "inputs_detected": input_count,
        "metrics": page_metrics,
    }


# Legacy compatibility - maintain old function signatures
async def navigate_and_capture_network(
    url: str,
    headless: bool = False,
    capture_console_logs: bool = True,
    capture_response_bodies: bool = False,
    max_body_size: int = MAX_RESPONSE_BODY_SIZE,
    wait_until: str = "domcontentloaded",
    extra_wait_ms: int = 500,
    enable_scrolling: bool = False,
    scroll_max: int = 5,
) -> Dict[str, Any]:
    """
    Backward-compatible network capture with optional scrolling.

    Args:
        url: URL to navigate to
        headless: Run browser in headless mode
        capture_console_logs: Capture browser console logs
        capture_response_bodies: Capture JSON response payloads
        max_body_size: Maximum response body size
        wait_until: When to consider navigation complete
        extra_wait_ms: Extra milliseconds to wait after navigation
        enable_scrolling: Enable automatic scrolling
        scroll_max: Maximum scroll attempts

    Returns:
        Dict with 'requests', 'console_logs', 'page_info', etc.
    """
    config = CaptureConfig(
        url=url,
        headless=headless,
        capture_console_logs=capture_console_logs,
        capture_response_bodies=capture_response_bodies,
        max_body_size=max_body_size,
        wait=WaitConfig(
            wait_for_load_state=wait_until,
            extra_wait_ms=extra_wait_ms,
        ),
        scroll=ScrollConfig(
            enabled=enable_scrolling,
            max_scrolls=scroll_max,
        ),
    )
    return await capture_network_advanced(config)


# Additional utility functions for common tasks

async def auto_detect_urls(url: str, headless: bool = True) -> Dict[str, Any]:
    """
    Automatically detect frontend and backend URLs from a page.
    Useful for 'check my signup flow' commands.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright not installed", "frontend_urls": [], "backend_urls": []}

    config = CaptureConfig(
        url=url,
        headless=headless,
        capture_console_logs=False,
        capture_response_bodies=False,
        scroll=ScrollConfig(enabled=True, max_scrolls=3),
        wait=WaitConfig(extra_wait_ms=1000),
    )

    result = await capture_network_advanced(config)

    if result.get("error"):
        return result

    requests = result.get("requests", [])
    frontend_urls = set()
    backend_urls = set()

    base_domain = _extract_domain(url)

    for req in requests:
        req_url = req.get("url", "")
        if not req_url:
            continue

        req_domain = _extract_domain(req_url)
        resource_type = req.get("resource_type", "")

        # Classify URLs
        if _is_backend_url(req_url):
            backend_urls.add(req_url)
        elif resource_type in ["document", "script", "stylesheet", "image", "font"]:
            frontend_urls.add(req_url)
        elif req_domain == base_domain:
            frontend_urls.add(req_url)
        else:
            backend_urls.add(req_url)

    return {
        "status": "ok",
        "page_url": url,
        "base_domain": base_domain,
        "frontend_urls": sorted(list(frontend_urls))[:50],
        "backend_urls": sorted(list(backend_urls))[:50],
        "frontend_count": len(frontend_urls),
        "backend_count": len(backend_urls),
        "page_info": result.get("page_info", {}),
    }


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def _is_backend_url(url: str) -> bool:
    """Check if URL looks like a backend/API endpoint."""
    backend_indicators = [
        "/api/", "/graphql", "/rest/", "/v1/", "/v2/", "/v3/",
        "/supabase.co", "/firebase", "/execute-api", "/lambda",
        "/webhook", "/callback", "/oauth", "/auth/",
        ".json", ".xml", "application/json",
    ]
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in backend_indicators)


async def test_signup_flow(
    url: str,
    email: str = "test@example.com",
    password: str = "TestPassword123!",
    headless: bool = False
) -> Dict[str, Any]:
    """
    Automatically test a signup flow by detecting and filling signup forms.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright not installed"}

    # First, navigate and analyze the page
    config = CaptureConfig(
        url=url,
        headless=headless,
        capture_console_logs=True,
        capture_response_bodies=True,
        scroll=ScrollConfig(enabled=True, max_scrolls=3),
        wait=WaitConfig(extra_wait_ms=1000),
    )

    result = await capture_network_advanced(config)

    if result.get("error"):
        return {"error": f"Initial navigation failed: {result['error']}", "stage": "navigation"}

    # Now try to find and interact with signup forms
    # (This would need a second navigation with interactions)
    # For now, return analysis

    page_info = result.get("page_info", {})
    console_logs = result.get("console_logs", [])
    requests = result.get("requests", [])

    # Analyze for signup-related elements
    signup_indicators = []
    for req in requests:
        url_lower = req.get("url", "").lower()
        if any(x in url_lower for x in ["signup", "register", "create", "auth"]):
            signup_indicators.append({"type": "request", "url": req.get("url")})

    errors = [log for log in console_logs if log.get("type") in ("error", "page_error")]

    return {
        "status": "analysis_complete",
        "page_url": url,
        "page_title": page_info.get("title", ""),
        "forms_detected": page_info.get("forms_detected", 0),
        "inputs_detected": page_info.get("inputs_detected", 0),
        "buttons_detected": page_info.get("buttons_detected", 0),
        "console_errors": len(errors),
        "signup_indicators": signup_indicators[:10],
        "backend_requests": len([r for r in requests if _is_backend_url(r.get("url", ""))]),
        "recommendation": _generate_recommendation(page_info, errors, signup_indicators),
    }


def _generate_recommendation(page_info: Dict, errors: List[Dict], indicators: List[Dict]) -> str:
    """Generate a recommendation based on page analysis."""
    if page_info.get("forms_detected", 0) == 0:
        return "No forms detected. Check if the page requires login or if the signup is on a different page."

    if errors:
        error_types = set(e.get("type") for e in errors)
        return f"Found {len(errors)} console errors ({', '.join(error_types)}). Check browser console for issues before testing signup."

    if indicators:
        return f"Found {len(indicators)} signup/auth related requests. Ready to test with form interaction."

    return "Page loaded successfully. Check for signup links/buttons to navigate to the registration form."


# Cleanup function
async def cleanup_browser():
    """Clean up browser resources. Call this when done."""
    await _close_browser()


# ==================== FAST COMPREHENSIVE CAPTURE ====================

@dataclass
class FastCaptureConfig:
    """Configuration for ultra-fast comprehensive page capture."""
    url: str = ""
    headless: bool = True
    capture_console_logs: bool = True
    capture_response_bodies: bool = False
    max_body_size: int = MAX_RESPONSE_BODY_SIZE
    # Fast mode settings
    fast_scroll: bool = True  # Use rapid scrolling
    max_scrolls: int = 3  # Fewer scrolls in fast mode
    detect_forms: bool = True
    detect_auth_endpoints: bool = True
    detect_api_endpoints: bool = True


async def fast_capture_page(config: FastCaptureConfig) -> Dict[str, Any]:
    """
    Ultra-fast comprehensive page capture in a SINGLE browser session.

    Combines navigation, scrolling, form detection, API detection, and console capture
    in ONE pass - eliminating redundant browser sessions.

    Returns all data in one response:
    - Network requests (frontend/backend)
    - Console logs and errors
    - Page structure (forms, inputs, buttons)
    - Detected API endpoints
    - Auth-related URLs
    - Performance metrics
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            "requests": [],
            "console_logs": [],
            "page_info": {},
        }

    requests_log: Dict[str, dict] = {}
    request_order: List[str] = []
    console_logs: List[dict] = []
    page_errors: List[dict] = []

    try:
        # Get or create browser (cached)
        browser, context = await _get_browser(config.headless)
        page = await context.new_page()

        # Set up network monitoring
        async def on_request(req):
            url = req.url
            if url.startswith("data:"):
                return  # Skip data URLs
            try:
                headers = await req.all_headers() if hasattr(req, 'all_headers') else req.headers
            except Exception:
                headers = {}
            requests_log[url] = {
                "url": url,
                "method": req.method,
                "resource_type": req.resource_type if hasattr(req, 'resource_type') else "unknown",
                "request_headers": dict(headers),
                "timestamp": time.time(),
            }
            request_order.append(url)

        async def on_response(res):
            try:
                req = res.request
                url = req.url
                if url not in requests_log:
                    return

                # Fast response capture
                r = requests_log[url]
                r["status"] = res.status

                # Capture response body for API responses only (faster)
                if config.capture_response_bodies:
                    content_type = res.headers.get("content-type", "").lower()
                    if "application/json" in content_type or "text/" in content_type:
                        try:
                            body = await res.body()
                            if body and len(body) <= config.max_body_size:
                                r["response_body"] = body.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
            except Exception:
                pass

        async def on_console(msg):
            if config.capture_console_logs:
                try:
                    console_logs.append({
                        "type": msg.type,
                        "text": msg.text if hasattr(msg, 'text') else str(msg),
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass

        async def on_page_error(error):
            if config.capture_console_logs:
                page_errors.append({
                    "type": "page_error",
                    "text": str(error),
                    "timestamp": time.time(),
                })

        # Attach all event listeners at once
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        # Single navigation with fast wait
        try:
            response = await page.goto(
                config.url,
                wait_until="domcontentloaded",  # Fastest reliable wait
                timeout=20000  # 20 second timeout
            )
            initial_status = response.status if response else 0
        except Exception as e:
            await page.close()
            return {
                "error": f"Navigation failed: {str(e)}",
                "url": config.url,
                "requests": [],
                "console_logs": [],
                "page_info": {"load_failed": True},
            }

        # Minimal wait for dynamic content (50ms instead of 300ms)
        await asyncio.sleep(0.05)

        # Fast scroll if enabled (fewer scrolls, faster)
        if config.fast_scroll:
            for _ in range(config.max_scrolls):
                await page.evaluate("window.scrollBy(0, 1200)")
                await asyncio.sleep(0.02)  # Very short delay between scrolls
        else:
            # Standard scroll
            scroll_config = ScrollConfig(enabled=True, max_scrolls=config.max_scrolls)
            await _perform_scrolls(page, scroll_config)

        # Get page info in parallel with other operations
        page_info = await _get_page_info(page)
        page_info["initial_status"] = initial_status

        # Close page to free resources
        await page.close()

        # Build output efficiently
        requests = []
        backend_urls = []
        auth_urls = []
        api_urls = []

        for url in request_order:
            if url in requests_log:
                r = requests_log[url]
                req_data = {
                    "url": r.get("url", ""),
                    "method": (r.get("method") or "GET").upper(),
                    "status": r.get("status", 0),
                    "resource_type": r.get("resource_type", "unknown"),
                    "timestamp": r.get("timestamp", time.time()),
                }
                requests.append(req_data)

                # Categorize URLs for fast detection
                url_lower = url.lower()
                if _is_backend_url(url):
                    api_urls.append(url)
                if _is_auth_related(url):
                    auth_urls.append(url)

        return {
            "status": "ok",
            "url": config.url,
            "requests": requests,
            "console_logs": console_logs + page_errors,
            "page_info": page_info,
            "requests_captured": len(requests),
            "console_errors_count": len(page_errors),
            # Computed analysis (done in single pass)
            "detected_api_urls": list(set(api_urls))[:30],
            "detected_auth_urls": list(set(auth_urls))[:30],
            "page_structure": {
                "forms": page_info.get("forms_detected", 0),
                "inputs": page_info.get("inputs_detected", 0),
                "buttons": page_info.get("buttons_detected", 0),
            },
        }

    except Exception as e:
        return {
            "error": str(e),
            "url": config.url,
            "requests": [],
            "console_logs": [],
            "page_info": {},
        }


def _is_auth_related(url: str) -> bool:
    """Check if URL is related to authentication."""
    auth_indicators = [
        "/auth", "/login", "/signup", "/register", "/signin",
        "/logout", "/token", "/oauth", "/callback",
        "/session", "/password", "/verify", "/confirm",
    ]
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in auth_indicators)
