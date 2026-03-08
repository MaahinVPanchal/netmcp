"""Extract API / backend URLs from a page without a browser. Works on Lambda (no Playwright)."""
import re
import urllib.request
from datetime import datetime, timezone
from typing import List, Set
from urllib.parse import urljoin, urlparse


def _get_url(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "NetMCP/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_urls_from_text(text: str, base_url: str) -> Set[str]:
    """Find URL-like strings and absolute API paths."""
    found: Set[str] = set()
    # Full URLs (https?://...)
    for m in re.finditer(r"https?://[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](?::\d+)?(?:/[^\s\"'<>)*,}\]]*)?", text):
        u = m.group(0).rstrip(".,;:)'\"]")
        if any(x in u.lower() for x in ("/api", "supabase", "graphql", "rest", "webhook", ".co/", "execute-api")):
            found.add(u)
        elif "supabase.co" in u or "execute-api" in u:
            found.add(u)
    # Paths that look like API: "/api/...", "/v1/...", "/graphql"
    for m in re.finditer(r"[\"'](/api[^\"']*|/v\d+/[^\"']*|/graphql[^\"']*)[\"']", text):
        path = m.group(1).split("?")[0].rstrip("/") or m.group(1)
        found.add(urljoin(base_url, path))
    # Common env / config patterns: fetch(`...`)
    for m in re.finditer(r"fetch\s*\(\s*[`\"'](https?://[^`\"']+)[`\"']", text):
        found.add(m.group(1))
    for m in re.finditer(r"axios\.(get|post|put|delete)\s*\(\s*[`\"'](https?://[^`\"']+)[`\"']", text):
        found.add(m.group(2))
    return found


async def fetch_and_extract_apis(url: str, fetch_linked_js: bool = True, max_js: int = 5) -> List[dict]:
    """
    GET the page (and optionally linked JS), extract API/backend-like URLs, return list of
    request-like dicts suitable for db.save_request() so they appear in get_network_logs.
    """
    if not url.strip():
        return []
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    base = url
    all_urls: Set[str] = set()
    try:
        html = _get_url(url)
        all_urls |= _extract_urls_from_text(html, base)
        if fetch_linked_js:
            for m in re.finditer(r'<script[^>]+src=[\"\']([^\"\']+)[\"\']', html, re.I):
                src = m.group(1)
                if src.startswith("//"):
                    src = "https:" + src
                elif not src.startswith("http"):
                    src = urljoin(base, src)
                if urlparse(src).netloc == urlparse(base).netloc or "supabase" in src or "api" in src.lower():
                    try:
                        js = _get_url(src, timeout=10)
                        all_urls |= _extract_urls_from_text(js, src)
                    except Exception:
                        pass
                    max_js -= 1
                    if max_js <= 0:
                        break
    except Exception as e:
        return [{"url": url, "error": str(e), "method": "GET", "status": 0}]
    out = []
    for u in sorted(all_urls):
        if len(u) < 10 or "javascript:" in u:
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_synthetic": True,
        })
    return out
