from fastmcp import FastMCP
from typing import Optional, Dict, Any, List
import json
import os
import uuid
import re
import time
from urllib.parse import urlparse

# Message when Playwright is not available (e.g. on Lambda)
_NAVIGATE_NO_PLAYWRIGHT = (
    "Playwright is not installed (e.g. on Lambda there is no browser). "
    "To capture full browser network traffic: run NetMCP locally with storage_backend: 'files' in mcp.json and install Playwright (pip install playwright && playwright install chromium). "
    "Alternatively use fetch_and_extract_apis(url) to discover API/backend URLs from the page source without a browser (works on Lambda)."
)


def register_tools(mcp: FastMCP, db):  # db can be DynamoDBClient or FileStorage

    # ==================== SUPER EFFECTIVE INTELLIGENT TOOLS ====================

    @mcp.tool
    async def check_signup_flow(
        url: Optional[str] = None,
        auto_detect: bool = True,
        headless: bool = True,  # Changed default to True for speed
        test_email: str = "test@netmcp.local",
        test_password: str = "TestPass123!",
        enable_scrolling: bool = True,
        capture_response_bodies: bool = False,  # Changed default to False for speed
        fast_mode: bool = True,  # NEW: Enable fast capture mode
    ) -> str:
        """
        SUPER EFFECTIVE: Check signup flow automatically. Just say "check my signup flow" and optionally provide a URL.
        This tool will:
        1. Auto-detect frontend/backend URLs if not provided
        2. Navigate to the signup page
        3. Scroll and capture all network requests
        4. Analyze for signup-related APIs and forms
        5. Report console errors and issues
        6. Suggest next steps for testing

        Set url to override FRONTEND_URL, or leave empty to use configured URL.
        Set fast_mode=true (default) for optimized single-pass capture (recommended).
        """
        from browser_playwright import (
            fast_capture_page,
            FastCaptureConfig,
            PLAYWRIGHT_AVAILABLE,
            cleanup_browser,
        )

        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        try:
            # Get target URL
            target = url or os.getenv("FRONTEND_URL", "").strip()
            if not target:
                return json.dumps({
                    "error": "No URL provided. Set url parameter, FRONTEND_URL in .env, or frontend_url in mcp.json",
                    "hint": "Usage: check_signup_flow(url='https://myapp.com')"
                })
            if not target.startswith(("http://", "https://")):
                target = "https://" + target

            session_id = str(uuid.uuid4())

            # FAST MODE: Single browser session capture (recommended)
            if fast_mode:
                config = FastCaptureConfig(
                    url=target,
                    headless=headless,
                    capture_console_logs=True,
                    capture_response_bodies=capture_response_bodies,
                    fast_scroll=True,
                    max_scrolls=3,
                )
                result = await fast_capture_page(config)

                if result.get("error"):
                    return json.dumps({"error": result["error"], "url": target})

                # Save to database
                entries = result.get("requests", [])
                console_logs = result.get("console_logs", [])

                for e in entries:
                    e["capture_session_id"] = session_id
                    e["test_type"] = "signup_flow"
                    await db.save_request(e)

                if console_logs:
                    await db.save_console_logs(session_id, console_logs)

                # Analyze results
                errors = [log for log in console_logs if log.get("type") in ("error", "page_error")]
                backend_urls = result.get("detected_api_urls", [])
                auth_urls = result.get("detected_auth_urls", [])
                page_structure = result.get("page_structure", {})

                report = {
                    "status": "ok",
                    "session_id": session_id,
                    "target_url": target,
                    "capture_mode": "fast_mode",
                    "summary": {
                        "total_requests": len(entries),
                        "backend_requests": len(backend_urls),
                        "auth_related_requests": len(auth_urls),
                        "console_errors": len(errors),
                        "forms_detected": page_structure.get("forms", 0),
                        "inputs_detected": page_structure.get("inputs", 0),
                    },
                    "console_errors": errors[:20],
                    "backend_urls": backend_urls[:20],
                    "auth_endpoints": auth_urls[:20],
                    "page_structure": page_structure,
                    "recommendations": _generate_signup_recommendations(
                        entries, errors, {"forms_detected": page_structure.get("forms", 0), "inputs_detected": page_structure.get("inputs", 0)}
                    ),
                    "next_steps": [
                        "1. Review console errors above",
                        "2. Check backend URLs for signup/auth endpoints",
                        "3. Use 'get_network_logs' to see all captured requests",
                        "4. Use 'get_failed_requests' to see any failed API calls",
                    ]
                }

                await cleanup_browser()
                return json.dumps(report, indent=2, default=str)

            # LEGACY MODE: Multiple browser sessions (slower, kept for compatibility)
            from browser_playwright import (
                navigate_and_capture_network,
                auto_detect_urls,
                test_signup_flow,
            )

            # Step 1: Auto-detect URLs if requested
            detection_result = None
            if auto_detect:
                detection_result = await auto_detect_urls(target, headless=True)

            # Step 2: Run comprehensive signup flow test
            flow_result = await test_signup_flow(
                target,
                email=test_email,
                password=test_password,
                headless=headless
            )

            # Step 3: Capture with scrolling enabled
            capture_result = await navigate_and_capture_network(
                target,
                headless=headless,
                capture_console_logs=True,
                capture_response_bodies=capture_response_bodies,
                enable_scrolling=enable_scrolling,
                scroll_max=10,
            )

            # Save to database
            entries = capture_result.get("requests", [])
            console_logs = capture_result.get("console_logs", [])

            for e in entries:
                e["capture_session_id"] = session_id
                e["test_type"] = "signup_flow"
                await db.save_request(e)

            if console_logs:
                await db.save_console_logs(session_id, console_logs)

            # Analyze results
            errors = [log for log in console_logs if log.get("type") in ("error", "page_error")]
            backend_requests = [r for r in entries if _is_backend_url(r.get("url", ""))]
            auth_requests = [r for r in entries if _is_auth_related(r.get("url", ""))]

            # Build comprehensive report
            report = {
                "status": "ok",
                "session_id": session_id,
                "target_url": target,
                "capture_mode": "legacy_mode",
                "summary": {
                    "total_requests": len(entries),
                    "backend_requests": len(backend_requests),
                    "auth_related_requests": len(auth_requests),
                    "console_errors": len(errors),
                    "forms_detected": flow_result.get("forms_detected", 0),
                    "inputs_detected": flow_result.get("inputs_detected", 0),
                },
                "auto_detection": detection_result if auto_detect else None,
                "flow_analysis": flow_result,
                "console_errors": errors[:20],  # Limit errors
                "backend_urls": sorted(list(set(r.get("url", "") for r in backend_requests)))[:20],
                "auth_endpoints": sorted(list(set(r.get("url", "") for r in auth_requests)))[:20],
                "recommendations": _generate_signup_recommendations(
                    entries, errors, flow_result
                ),
                "next_steps": [
                    "1. Review console errors above",
                    "2. Check backend URLs for signup/auth endpoints",
                    "3. Use 'get_network_logs' to see all captured requests",
                    "4. Use 'get_failed_requests' to see any failed API calls",
                ]
            }

            await cleanup_browser()
            return json.dumps(report, indent=2, default=str)

        except Exception as e:
            await cleanup_browser()
            return json.dumps({
                "error": str(e),
                "stage": "check_signup_flow",
                "hint": "Make sure Playwright is installed: pip install playwright && playwright install chromium"
            })

    @mcp.tool
    async def analyze_web_app(
        url: Optional[str] = None,
        headless: bool = True,
        scroll_full_page: bool = True,
        capture_response_bodies: bool = False,  # Changed default for speed
        fast_mode: bool = True,  # NEW: Enable fast capture mode
    ) -> str:
        """
        SUPER EFFECTIVE: Comprehensive web app analysis. Just say "analyze my web app" and optionally provide URL.
        Automatically detects:
        - Frontend assets and resources
        - Backend API endpoints
        - Authentication endpoints
        - Console errors and warnings
        - Page structure (forms, inputs, buttons)
        - Performance metrics

        Set fast_mode=true (default) for optimized single-pass capture (recommended).
        """
        from browser_playwright import (
            fast_capture_page,
            FastCaptureConfig,
            PLAYWRIGHT_AVAILABLE,
            cleanup_browser,
        )

        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        try:
            target = url or os.getenv("FRONTEND_URL", "").strip()
            if not target:
                return json.dumps({"error": "No URL provided. Set url parameter or FRONTEND_URL in .env"})
            if not target.startswith(("http://", "https://")):
                target = "https://" + target

            session_id = str(uuid.uuid4())

            # FAST MODE: Single browser session (recommended)
            if fast_mode:
                config = FastCaptureConfig(
                    url=target,
                    headless=headless,
                    capture_console_logs=True,
                    capture_response_bodies=capture_response_bodies,
                    fast_scroll=scroll_full_page,
                    max_scrolls=5,
                )
                result = await fast_capture_page(config)

                if result.get("error"):
                    return json.dumps({"error": result["error"], "url": target})

                # Save to database
                requests = result.get("requests", [])
                console_logs = result.get("console_logs", [])

                for e in requests:
                    e["capture_session_id"] = session_id
                    e["test_type"] = "web_analysis"
                    await db.save_request(e)

                if console_logs:
                    await db.save_console_logs(session_id, console_logs)

                # Categorize requests
                categories = _categorize_requests(requests)
                errors = [log for log in console_logs if log.get("type") in ("error", "page_error", "warning")]
                page_structure = result.get("page_structure", {})

                report = {
                    "status": "ok",
                    "session_id": session_id,
                    "url": target,
                    "capture_mode": "fast_mode",
                    "page_info": {
                        "title": result.get("page_info", {}).get("title", ""),
                        "forms": page_structure.get("forms", 0),
                        "inputs": page_structure.get("inputs", 0),
                        "buttons": page_structure.get("buttons", 0),
                    },
                    "request_summary": {
                        "total": len(requests),
                        "by_category": {k: len(v) for k, v in categories.items()},
                    },
                    "categories": {
                        k: [r.get("url", "") for r in v[:10]]
                        for k, v in categories.items()
                    },
                    "detected_api_urls": result.get("detected_api_urls", []),
                    "detected_auth_urls": result.get("detected_auth_urls", []),
                    "errors": errors[:20],
                    "error_count": len(errors),
                    "key_findings": _generate_findings(requests, errors, result.get("page_info", {})),
                    "recommendations": _generate_recommendations(requests, errors),
                }

                await cleanup_browser()
                return json.dumps(report, indent=2, default=str)

            # LEGACY MODE: Multiple browser sessions (slower)
            from browser_playwright import (
                navigate_and_capture_network,
                auto_detect_urls,
            )

            # Run detection and capture
            detection = await auto_detect_urls(target, headless=headless)
            capture = await navigate_and_capture_network(
                target,
                headless=headless,
                capture_console_logs=True,
                capture_response_bodies=capture_response_bodies,
                enable_scrolling=scroll_full_page,
                scroll_max=15,
            )

            requests = capture.get("requests", [])
            console_logs = capture.get("console_logs", [])
            page_info = capture.get("page_info", {})

            # Save to database
            for e in requests:
                e["capture_session_id"] = session_id
                e["test_type"] = "web_analysis"
                await db.save_request(e)

            if console_logs:
                await db.save_console_logs(session_id, console_logs)

            # Categorize requests
            categories = _categorize_requests(requests)

            # Analyze errors
            errors = [log for log in console_logs if log.get("type") in ("error", "page_error", "warning")]

            report = {
                "status": "ok",
                "session_id": session_id,
                "url": target,
                "capture_mode": "legacy_mode",
                "page_info": {
                    "title": page_info.get("title", ""),
                    "forms": page_info.get("forms_detected", 0),
                    "inputs": page_info.get("inputs_detected", 0),
                    "buttons": page_info.get("buttons_detected", 0),
                },
                "request_summary": {
                    "total": len(requests),
                    "by_category": {k: len(v) for k, v in categories.items()},
                },
                "categories": {
                    k: [r.get("url", "") for r in v[:10]]
                    for k, v in categories.items()
                },
                "errors": errors[:20],
                "error_count": len(errors),
                "key_findings": _generate_findings(requests, errors, page_info),
                "recommendations": _generate_recommendations(requests, errors),
            }

            await cleanup_browser()
            return json.dumps(report, indent=2, default=str)

        except Exception as e:
            await cleanup_browser()
            return json.dumps({"error": str(e)})

    @mcp.tool
    async def smart_navigate(
        url: Optional[str] = None,
        headless: bool = False,
        scroll_page: bool = True,
        click_selectors: Optional[List[str]] = None,
        fill_form_data: Optional[Dict[str, str]] = None,
        wait_for_selector: Optional[str] = None,
        capture_response_bodies: bool = False,
    ) -> str:
        """
        SUPER EFFECTIVE: Smart navigation with scrolling and interaction.
        Can scroll the page, click elements, fill forms, and wait for specific elements.

        Examples:
        - smart_navigate(url="https://example.com", scroll_page=true) - Navigate and scroll
        - smart_navigate(url="https://example.com", click_selectors=["#signup-btn"]) - Click then capture
        - smart_navigate(url="https://example.com", fill_form_data={"#email": "test@test.com", "#password": "pass123"}) - Fill form
        """
        from browser_playwright import (
            capture_network_advanced,
            CaptureConfig,
            ScrollConfig,
            InteractionConfig,
            WaitConfig,
            PLAYWRIGHT_AVAILABLE,
            cleanup_browser,
        )

        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        try:
            target = url or os.getenv("FRONTEND_URL", "").strip()
            if not target:
                return json.dumps({"error": "No URL provided"})
            if not target.startswith(("http://", "https://")):
                target = "https://" + target

            session_id = str(uuid.uuid4())

            # Build interaction config
            interaction = InteractionConfig()
            if click_selectors and len(click_selectors) > 0:
                interaction.click_selector = click_selectors[0]  # Primary click
                interaction.wait_for_navigation = True

            if fill_form_data:
                interaction.fill_form = fill_form_data
                interaction.submit_form = click_selectors[0] if click_selectors else None

            config = CaptureConfig(
                url=target,
                headless=headless,
                capture_console_logs=True,
                capture_response_bodies=capture_response_bodies,
                scroll=ScrollConfig(enabled=scroll_page, max_scrolls=10),
                interaction=interaction,
                wait=WaitConfig(
                    wait_for_selector=wait_for_selector,
                    wait_for_selector_timeout_ms=10000,
                    extra_wait_ms=500,
                ),
            )

            result = await capture_network_advanced(config)

            if result.get("error"):
                await cleanup_browser()
                return json.dumps({"error": result["error"]})

            # Save to database
            entries = result.get("requests", [])
            console_logs = result.get("console_logs", [])

            for e in entries:
                e["capture_session_id"] = session_id
                await db.save_request(e)

            if console_logs:
                await db.save_console_logs(session_id, console_logs)

            # Build response
            response = {
                "status": "ok",
                "session_id": session_id,
                "url": target,
                "requests_captured": len(entries),
                "console_logs_captured": len(console_logs),
                "page_info": result.get("page_info", {}),
                "interactions": result.get("interactions", []),
                "scrolls_performed": len(result.get("scrolls", [])),
            }

            await cleanup_browser()
            return json.dumps(response, indent=2, default=str)

        except Exception as e:
            await cleanup_browser()
            return json.dumps({"error": str(e)})

    @mcp.tool
    async def test_api_endpoint(
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        expected_status: Optional[int] = None,
    ) -> str:
        """
        Test an API endpoint directly (no browser needed).
        Useful for testing backend APIs discovered during navigation.
        """
        import aiohttp
        import asyncio

        try:
            start_time = asyncio.get_event_loop().time()

            async with aiohttp.ClientSession() as session:
                request_kwargs = {}
                if headers:
                    request_kwargs["headers"] = headers
                if body:
                    request_kwargs["data"] = body

                async with session.request(method, url, **request_kwargs) as response:
                    response_body = await response.text()
                    end_time = asyncio.get_event_loop().time()
                    response_time_ms = int((end_time - start_time) * 1000)

                    # Save to database
                    session_id = str(uuid.uuid4())
                    request_data = {
                        "capture_session_id": session_id,
                        "url": url,
                        "method": method.upper(),
                        "status": response.status,
                        "response_time_ms": response_time_ms,
                        "request_headers": headers or {},
                        "request_body": body or "",
                        "response_headers": dict(response.headers),
                        "response_body": response_body[:10000],  # Limit size
                        "resource_type": "api_test",
                    }
                    await db.save_request(request_data)

                    result = {
                        "status": "ok",
                        "session_id": session_id,
                        "url": url,
                        "method": method.upper(),
                        "response_status": response.status,
                        "response_time_ms": response_time_ms,
                        "content_type": response.headers.get("content-type", ""),
                        "response_preview": response_body[:2000] if len(response_body) > 2000 else response_body,
                        "test_passed": expected_status is None or response.status == expected_status,
                    }

                    return json.dumps(result, indent=2, default=str)

        except Exception as e:
            return json.dumps({"error": str(e), "url": url, "method": method})

    # ==================== ORIGINAL TOOLS (Maintained for compatibility) ====================

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
        from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE, cleanup_browser
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

        await cleanup_browser()
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
        from browser_playwright import navigate_and_capture_network, PLAYWRIGHT_AVAILABLE, cleanup_browser
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

        await cleanup_browser()
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

    @mcp.tool
    async def extract_urls_from_page(
        url: Optional[str] = None,
        include_external: bool = False,
    ) -> str:
        """
        Extract all URLs from a page - frontend, backend, images, scripts, etc.
        Organizes by category for easy analysis.
        """
        from browser_playwright import (
            navigate_and_capture_network,
            PLAYWRIGHT_AVAILABLE,
            cleanup_browser,
        )

        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        target = url or os.getenv("FRONTEND_URL", "").strip()
        if not target:
            return json.dumps({"error": "No URL provided"})
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

        try:
            result = await navigate_and_capture_network(
                target,
                headless=True,
                capture_console_logs=False,
                enable_scrolling=True,
                scroll_max=5,
            )

            requests = result.get("requests", [])
            base_domain = _extract_domain(target)

            # Categorize URLs
            categories = {
                "api": [],
                "auth": [],
                "scripts": [],
                "styles": [],
                "images": [],
                "fonts": [],
                "documents": [],
                "external": [],
                "other": [],
            }

            seen = set()
            for req in requests:
                url = req.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)

                resource_type = req.get("resource_type", "unknown")

                # Skip data URLs
                if url.startswith("data:"):
                    continue

                # Check if external
                domain = _extract_domain(url)
                if domain and domain != base_domain and not include_external:
                    categories["external"].append(url)
                    continue

                # Categorize by resource type
                if resource_type == "script":
                    categories["scripts"].append(url)
                elif resource_type == "stylesheet":
                    categories["styles"].append(url)
                elif resource_type == "image":
                    categories["images"].append(url)
                elif resource_type == "font":
                    categories["fonts"].append(url)
                elif resource_type == "document":
                    categories["documents"].append(url)
                elif _is_backend_url(url):
                    categories["api"].append(url)
                elif _is_auth_related(url):
                    categories["auth"].append(url)
                else:
                    categories["other"].append(url)

            await cleanup_browser()

            return json.dumps({
                "status": "ok",
                "page_url": target,
                "base_domain": base_domain,
                "total_urls": len(seen),
                "by_category": {k: len(v) for k, v in categories.items()},
                "urls": categories,
            }, indent=2)

        except Exception as e:
            await cleanup_browser()
            return json.dumps({"error": str(e)})


    @mcp.tool
    async def test_website_comprehensive(
        url: Optional[str] = None,
        headless: bool = True,
        test_pages: Optional[List[str]] = None,
        max_pages: int = 5,
        page_timeout_ms: int = 30000,
    ) -> str:
        """
        Fast comprehensive website test - tests multiple pages in a single browser session.
        Ideal for testing an entire website in 3-10 minutes.

        Tests:
        - Homepage and specified pages
        - All network requests per page
        - Console errors per page
        - API endpoints detected
        - Auth endpoints detected
        - Page structure (forms, inputs)

        Args:
            url: Base URL to test (uses FRONTEND_URL from mcp.json if not provided)
            headless: Run browser in headless mode (default True for speed)
            test_pages: List of relative paths to test (e.g., ["/login", "/signup", "/dashboard"])
            max_pages: Maximum pages to test (default 5, max 10)
            page_timeout_ms: Timeout per page in milliseconds (default 30000)

        Returns:
            Comprehensive test report for all pages tested
        """
        from browser_playwright import (
            fast_capture_page,
            FastCaptureConfig,
            PLAYWRIGHT_AVAILABLE,
            cleanup_browser,
        )

        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        try:
            base_url = url or os.getenv("FRONTEND_URL", "").strip()
            if not base_url:
                return json.dumps({"error": "No URL provided. Set url parameter, FRONTEND_URL in .env, or frontend_url in mcp.json"})
            if not base_url.startswith(("http://", "https://")):
                base_url = "https://" + base_url

            session_id = str(uuid.uuid4())
            start_time = time.time()

            # Default pages to test
            if not test_pages:
                test_pages = ["/"]  # Just homepage by default
            test_pages = test_pages[:max_pages]  # Limit pages

            all_results = []
            all_requests = []
            all_console_logs = []
            all_errors = []
            all_api_urls = set()
            all_auth_urls = set()
            pages_tested = 0

            for page_path in test_pages:
                # Build full URL
                page_url = base_url.rstrip("/") + "/" + page_path.lstrip("/")
                if page_path == "/":
                    page_url = base_url

                # Fast capture for each page
                config = FastCaptureConfig(
                    url=page_url,
                    headless=headless,
                    capture_console_logs=True,
                    capture_response_bodies=False,  # Faster without bodies
                    fast_scroll=True,
                    max_scrolls=2,  # Minimal scrolling for speed
                )

                result = await fast_capture_page(config)

                if result.get("error"):
                    all_results.append({
                        "page": page_path,
                        "url": page_url,
                        "error": result["error"],
                    })
                    continue

                pages_tested += 1
                requests = result.get("requests", [])
                console_logs = result.get("console_logs", [])
                errors_list = [log for log in console_logs if log.get("type") in ("error", "page_error")]

                # Save to database
                for req in requests:
                    req["capture_session_id"] = session_id
                    req["test_type"] = "comprehensive_test"
                    req["page"] = page_path
                    await db.save_request(req)

                if console_logs:
                    await db.save_console_logs(session_id, console_logs)

                # Collect results
                all_requests.extend(requests)
                all_console_logs.extend(console_logs)
                all_errors.extend(errors_list)
                all_api_urls.update(result.get("detected_api_urls", []))
                all_auth_urls.update(result.get("detected_auth_urls", []))

                all_results.append({
                    "page": page_path,
                    "url": page_url,
                    "status": "ok",
                    "requests_count": len(requests),
                    "errors_count": len(errors_list),
                    "page_structure": result.get("page_structure", {}),
                })

            elapsed_time = time.time() - start_time

            # Categorize all requests
            categories = _categorize_requests(all_requests)

            report = {
                "status": "ok",
                "session_id": session_id,
                "base_url": base_url,
                "pages_tested": pages_tested,
                "total_time_seconds": round(elapsed_time, 2),
                "summary": {
                    "total_requests": len(all_requests),
                    "total_console_errors": len(all_errors),
                    "unique_api_endpoints": len(all_api_urls),
                    "unique_auth_endpoints": len(all_auth_urls),
                    "request_categories": {k: len(v) for k, v in categories.items()},
                },
                "pages": all_results,
                "console_errors": all_errors[:30],  # Limit output
                "api_endpoints": sorted(list(all_api_urls))[:20],
                "auth_endpoints": sorted(list(all_auth_urls))[:20],
                "failed_requests": [
                    {"url": r.get("url"), "status": r.get("status"), "page": r.get("page")}
                    for r in all_requests if r.get("status", 0) >= 400
                ][:20],
                "recommendations": _generate_recommendations(all_requests, all_errors),
            }

            await cleanup_browser()
            return json.dumps(report, indent=2, default=str)

        except Exception as e:
            await cleanup_browser()
            return json.dumps({"error": str(e), "stage": "test_website_comprehensive"})

    @mcp.tool
    async def test_full_stack(
        frontend_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        test_frontend_pages: Optional[List[str]] = None,
        test_backend_endpoints: Optional[List[str]] = None,
        headless: bool = True,
    ) -> str:
        """
        Test BOTH frontend and backend from mcp.json configuration.

        Uses frontend_url and backend_url from mcp.json (or parameters).
        Tests frontend pages AND makes direct API calls to backend.

        Args:
            frontend_url: Frontend URL (uses frontend_url from mcp.json if not provided)
            backend_url: Backend URL (uses backend_url from mcp.json if not provided)
            test_frontend_pages: Pages to test on frontend (default: ["/"])
            test_backend_endpoints: Backend endpoints to test (default: ["/rest/v1/", "/auth/v1/"])
            headless: Run browser in headless mode

        Returns:
            Combined frontend + backend test report
        """
        from browser_playwright import (
            fast_capture_page,
            FastCaptureConfig,
            PLAYWRIGHT_AVAILABLE,
            cleanup_browser,
        )
        import aiohttp

        # Get URLs from config (mcp.json) or parameters
        fe_url = frontend_url or os.getenv("FRONTEND_URL", "").strip()
        be_url = backend_url or os.getenv("BACKEND_URL", "").strip()

        if not fe_url and not be_url:
            return json.dumps({
                "error": "No URLs provided. Set frontend_url and backend_url in mcp.json or pass as parameters.",
                "hint": "mcp.json format: {\"netmcp\": {\"frontend_url\": \"https://myapp.com\", \"backend_url\": \"https://api.myapp.com\"}}"
            })

        session_id = str(uuid.uuid4())
        start_time = time.time()
        results = {
            "session_id": session_id,
            "frontend": None,
            "backend": None,
        }

        # Test Frontend (if URL provided and Playwright available)
        if fe_url:
            if not fe_url.startswith(("http://", "https://")):
                fe_url = "https://" + fe_url

            if PLAYWRIGHT_AVAILABLE:
                pages_to_test = test_frontend_pages or ["/"]
                all_fe_requests = []
                all_fe_errors = []

                for page_path in pages_to_test:
                    page_url = fe_url.rstrip("/") + "/" + page_path.lstrip("/")
                    if page_path == "/":
                        page_url = fe_url

                    config = FastCaptureConfig(
                        url=page_url,
                        headless=headless,
                        capture_console_logs=True,
                        capture_response_bodies=False,
                        fast_scroll=True,
                        max_scrolls=2,
                    )

                    result = await fast_capture_page(config)

                    if result.get("error"):
                        continue

                    all_fe_requests.extend(result.get("requests", []))
                    all_fe_errors.extend([l for l in result.get("console_logs", []) if l.get("type") in ("error", "page_error")])

                    # Save requests
                    for req in result.get("requests", []):
                        req["capture_session_id"] = session_id
                        req["test_type"] = "full_stack_frontend"
                        await db.save_request(req)

                results["frontend"] = {
                    "url": fe_url,
                    "pages_tested": len(pages_to_test),
                    "total_requests": len(all_fe_requests),
                    "console_errors": len(all_fe_errors),
                    "error_details": all_fe_errors[:10],
                    "detected_apis": list(set(r.get("url", "") for r in all_fe_requests if _is_backend_url(r.get("url", ""))))[:20],
                }

                await cleanup_browser()

        # Test Backend (direct API calls)
        if be_url:
            if not be_url.startswith(("http://", "https://")):
                be_url = "https://" + be_url

            endpoints_to_test = test_backend_endpoints or ["/rest/v1/", "/auth/v1/", "/"]
            be_results = []

            async with aiohttp.ClientSession() as http_session:
                for endpoint in endpoints_to_test:
                    endpoint_url = be_url.rstrip("/") + "/" + endpoint.lstrip("/")
                    try:
                        start = time.time()
                        async with http_session.get(endpoint_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            elapsed = int((time.time() - start) * 1000)
                            be_results.append({
                                "endpoint": endpoint,
                                "url": endpoint_url,
                                "status": resp.status,
                                "response_time_ms": elapsed,
                                "content_type": resp.headers.get("content-type", ""),
                            })
                            # Save to database
                            await db.save_request({
                                "capture_session_id": session_id,
                                "test_type": "full_stack_backend",
                                "url": endpoint_url,
                                "method": "GET",
                                "status": resp.status,
                                "response_time_ms": elapsed,
                                "resource_type": "api_test",
                            })
                    except Exception as e:
                        be_results.append({
                            "endpoint": endpoint,
                            "url": endpoint_url,
                            "error": str(e),
                        })

            results["backend"] = {
                "url": be_url,
                "endpoints_tested": len(be_results),
                "results": be_results,
                "successful": len([r for r in be_results if r.get("status") and r.get("status") < 400]),
                "failed": len([r for r in be_results if r.get("error") or (r.get("status") and r.get("status") >= 400)]),
            }

        elapsed_time = time.time() - start_time

        results["status"] = "ok"
        results["total_time_seconds"] = round(elapsed_time, 2)
        results["config_source"] = {
            "frontend_url": fe_url or "not configured",
            "backend_url": be_url or "not configured",
            "source": "mcp.json" if (os.getenv("FRONTEND_URL") or os.getenv("BACKEND_URL")) else "parameters",
        }

        return json.dumps(results, indent=2, default=str)

    @mcp.tool
    async def fast_navigate(
        url: Optional[str] = None,
        headless: bool = True,
        capture_console_logs: bool = True,
        capture_response_bodies: bool = False,
        max_scrolls: int = 3,
    ) -> str:
        """
        FAST navigation - optimized single-pass browser capture.
        Up to 10x faster than regular navigate functions.

        Uses:
        - Single browser session (cached)
        - Minimal scrolling (3 scrolls default)
        - Fast page load waiting (domcontentloaded)
        - No unnecessary delays

        Args:
            url: URL to navigate to (uses FRONTEND_URL if not provided)
            headless: Run in headless mode (default True)
            capture_console_logs: Capture browser console logs
            capture_response_bodies: Capture API response bodies
            max_scrolls: Maximum scroll attempts (default 3)

        Returns:
            Network requests, console logs, page info, detected APIs
        """
        from browser_playwright import (
            fast_capture_page,
            FastCaptureConfig,
            PLAYWRIGHT_AVAILABLE,
            cleanup_browser,
        )

        if not PLAYWRIGHT_AVAILABLE:
            return json.dumps({"error": _NAVIGATE_NO_PLAYWRIGHT})

        try:
            target = url or os.getenv("FRONTEND_URL", "").strip()
            if not target:
                return json.dumps({"error": "No URL provided. Set url parameter or FRONTEND_URL in .env"})
            if not target.startswith(("http://", "https://")):
                target = "https://" + target

            session_id = str(uuid.uuid4())
            start_time = time.time()

            config = FastCaptureConfig(
                url=target,
                headless=headless,
                capture_console_logs=capture_console_logs,
                capture_response_bodies=capture_response_bodies,
                fast_scroll=True,
                max_scrolls=max_scrolls,
            )

            result = await fast_capture_page(config)
            elapsed_time = time.time() - start_time

            if result.get("error"):
                return json.dumps({"error": result["error"], "url": target})

            # Save to database
            requests = result.get("requests", [])
            console_logs = result.get("console_logs", [])

            for req in requests:
                req["capture_session_id"] = session_id
                await db.save_request(req)

            if console_logs:
                await db.save_console_logs(session_id, console_logs)

            response = {
                "status": "ok",
                "session_id": session_id,
                "url": target,
                "elapsed_time_seconds": round(elapsed_time, 2),
                "requests_captured": len(requests),
                "console_logs_captured": len(console_logs),
                "console_errors": len([l for l in console_logs if l.get("type") in ("error", "page_error")]),
                "page_structure": result.get("page_structure", {}),
                "detected_api_urls": result.get("detected_api_urls", [])[:20],
                "detected_auth_urls": result.get("detected_auth_urls", [])[:20],
                "page_info": result.get("page_info", {}),
            }

            await cleanup_browser()
            return json.dumps(response, indent=2, default=str)

        except Exception as e:
            await cleanup_browser()
            return json.dumps({"error": str(e)})


# ==================== HELPER FUNCTIONS ====================

def _is_backend_url(url: str) -> bool:
    """Check if URL looks like a backend/API endpoint."""
    backend_indicators = [
        "/api/", "/graphql", "/rest/", "/v1/", "/v2/", "/v3/",
        "/supabase.co", "/firebase", "/execute-api", "/lambda",
        "/webhook", "/callback", "/oauth", "/auth/",
        ".json", ".xml",
    ]
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in backend_indicators)


def _is_auth_related(url: str) -> bool:
    """Check if URL is related to authentication."""
    auth_indicators = [
        "/auth", "/login", "/signup", "/register", "/signin",
        "/logout", "/token", "/oauth", "/callback",
        "/session", "/password", "/verify", "/confirm",
    ]
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in auth_indicators)


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def _categorize_requests(requests: List[Dict]) -> Dict[str, List[Dict]]:
    """Categorize requests by type."""
    categories = {
        "html_documents": [],
        "scripts": [],
        "stylesheets": [],
        "images": [],
        "fonts": [],
        "api_calls": [],
        "auth_related": [],
        "external": [],
        "other": [],
    }

    for req in requests:
        url = req.get("url", "")
        resource_type = req.get("resource_type", "unknown")

        if resource_type == "document":
            categories["html_documents"].append(req)
        elif resource_type == "script":
            categories["scripts"].append(req)
        elif resource_type == "stylesheet":
            categories["stylesheets"].append(req)
        elif resource_type == "image":
            categories["images"].append(req)
        elif resource_type == "font":
            categories["fonts"].append(req)
        elif _is_backend_url(url):
            categories["api_calls"].append(req)
        elif _is_auth_related(url):
            categories["auth_related"].append(req)
        else:
            categories["other"].append(req)

    return categories


def _generate_findings(requests: List[Dict], errors: List[Dict], page_info: Dict) -> List[str]:
    """Generate key findings from analysis."""
    findings = []

    # Check for common issues
    status_codes = set(r.get("status", 0) for r in requests)
    failed_requests = [r for r in requests if r.get("status", 0) >= 400]
    backend_requests = [r for r in requests if _is_backend_url(r.get("url", ""))]

    if failed_requests:
        findings.append(f"Found {len(failed_requests)} failed requests (4xx/5xx)")

    if errors:
        findings.append(f"Found {len(errors)} console errors")

    if backend_requests:
        findings.append(f"Detected {len(backend_requests)} backend API calls")

    if page_info.get("forms_detected", 0) > 0:
        findings.append(f"Found {page_info.get('forms_detected')} forms on the page")

    if not requests:
        findings.append("No network requests captured - page may be using service workers or cache")

    return findings


def _generate_recommendations(requests: List[Dict], errors: List[Dict]) -> List[str]:
    """Generate recommendations based on analysis."""
    recommendations = []

    if errors:
        recommendations.append("Review and fix console errors before deployment")

    failed_requests = [r for r in requests if r.get("status", 0) >= 500]
    if failed_requests:
        recommendations.append(f"Investigate {len(failed_requests)} server errors (5xx)")

    slow_requests = [r for r in requests if r.get("response_time_ms", 0) > 1000]
    if slow_requests:
        recommendations.append(f"Optimize {len(slow_requests)} slow requests (>1s)")

    recommendations.append("Use 'get_failed_requests' to see detailed error information")
    recommendations.append("Use 'get_backend_urls' to see all detected API endpoints")

    return recommendations


def _generate_signup_recommendations(
    requests: List[Dict],
    errors: List[Dict],
    flow_result: Dict
) -> List[str]:
    """Generate recommendations for signup flow testing."""
    recommendations = []

    if errors:
        recommendations.append(f"Fix {len(errors)} console errors before testing signup flow")

    forms = flow_result.get("forms_detected", 0)
    if forms == 0:
        recommendations.append("No forms detected - signup may be on a different page or require login")
    elif forms == 1:
        recommendations.append("1 form detected - likely the signup form")
    else:
        recommendations.append(f"{forms} forms detected - identify which one is for signup")

    backend_requests = [r for r in requests if _is_backend_url(r.get("url", ""))]
    if not backend_requests:
        recommendations.append("No API calls detected - check if backend is configured correctly")
    else:
        recommendations.append(f"{len(backend_requests)} API calls captured - review signup endpoints")

    return recommendations
