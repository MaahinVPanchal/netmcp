"""Extract API/backend URLs from a page without a browser. Works on Lambda (no Playwright)."""
import asyncio
import re
import urllib.request
from datetime import datetime, timezone
from typing import List, Set
from urllib.parse import urljoin, urlparse

_API_KEYWORDS = ("/api", "supabase", "graphql", "/rest", "webhook", "execute-api")
_FETCH_TIMEOUT = 15
_JS_FETCH_TIMEOUT = 10


def _get_url(url: str, timeout: int = _FETCH_TIMEOUT) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "NetMCP/1.0", "Accept": "text/html,application/javascript,*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _looks_like_api(url: str) -> bool:
    u = url.lower()
    return any(k in u for k in _API_KEYWORDS) or "supabase.co" in u


def _extract_urls_from_text(text: str, base_url: str) -> Set[str]:
    """Extract API-like URLs from HTML or JS source text."""
    found: Set[str] = set()

    # Absolute URLs
    for m in re.finditer(
        r"https?://[a-zA-Z0-9][-a-zA-Z0-9.]*(?::\d+)?(?:/[^\s\"'<>)*,}\]\\]*)?",
        text,
    ):
        u = m.group(0).rstrip(".,;:)'\"]")
        if _looks_like_api(u):
            found.add(u)

    # Relative API paths: "/api/...", "/v1/...", "/graphql"
    for m in re.finditer(r'["\'](/(?:api|v\d+|graphql)[^"\']*)["\']', text):
        path = m.group(1).split("?")[0].rstrip("/") or m.group(1)
        found.add(urljoin(base_url, path))

    # fetch("https://...") and axios.get("https://...")
    for m in re.finditer(r'(?:fetch|axios\.(?:get|post|put|patch|delete))\s*\(\s*[`"\'](https?://[^`"\']+)[`"\']', text):
        found.add(m.group(1))

    return found


def _fetch_js_files(html: str, base_url: str, max_js: int) -> Set[str]:
    """Fetch linked same-origin JS files and extract API URLs from them."""
    found: Set[str] = set()
    base_host = urlparse(base_url).netloc
    fetched = 0

    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I):
        if fetched >= max_js:
            break
        src = m.group(1)
        if src.startswith("//"):
            src = "https:" + src
        elif not src.startswith("http"):
            src = urljoin(base_url, src)

        src_host = urlparse(src).netloc
        # Only fetch same-origin scripts or known API CDNs
        if src_host != base_host and not _looks_like_api(src):
            continue

        try:
            js = _get_url(src, timeout=_JS_FETCH_TIMEOUT)
            found |= _extract_urls_from_text(js, src)
            fetched += 1
        except Exception:
            continue

    return found


async def fetch_and_extract_apis(
    url: str,
    fetch_linked_js: bool = True,
    max_js: int = 5,
) -> List[dict]:
    """
    Fetch a page (and optionally linked JS files), extract API/backend-like URLs,
    and return a list of request-like dicts suitable for db.save_request().

    Works without a browser — safe to use on Lambda.
    """
    if not url.strip():
        return []
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    def _run() -> List[dict]:
        all_urls: Set[str] = set()
        try:
            html = _get_url(url)
        except Exception as exc:
            return [{"url": url, "error": str(exc), "method": "GET", "status": 0}]

        all_urls |= _extract_urls_from_text(html, url)

        if fetch_linked_js and max_js > 0:
            all_urls |= _fetch_js_files(html, url, max_js)

        now = datetime.now(timezone.utc).isoformat()
        out = []
        for u in sorted(all_urls):
            if len(u) < 10 or "javascript:" in u.lower():
                continue
            out.append({
                "url": u,
                "method": "GET",
                "status": 200,
                "response_time_ms": 0,
                "request_headers": {},
                "request_body": "",
                "response_headers": {},
                "response_body": "",
                "timestamp": now,
                "_synthetic": True,
            })
        return out

    return await asyncio.to_thread(_run)
