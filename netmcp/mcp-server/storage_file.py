"""File (TXT/JSONL) storage backend for network logs."""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from util import sanitize_request

LOG_FILE = os.getenv("NETMCP_LOG_FILE", "netmcp_logs.txt")


class FileStorage:
    """Store network requests as JSONL in a text file. One JSON object per line."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or LOG_FILE
        if not os.path.isabs(self.path):
            self.path = os.path.join(os.path.dirname(__file__), self.path)

    def _read_all_sync(self) -> List[dict]:
        if not os.path.exists(self.path):
            return []
        items = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items

    def _append_sync(self, item: dict) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, default=str) + "\n")

    async def save_request(self, data: dict) -> None:
        data = sanitize_request(data)
        item = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": data.get("url", ""),
            "method": (data.get("method") or "GET").upper(),
            "status": int(data.get("status", 0)),
            "response_time_ms": int(data.get("response_time_ms", 0)),
            "request_headers": data.get("request_headers") or {},
            "request_body": data.get("request_body") or "",
            "response_headers": data.get("response_headers") or {},
            "response_body": (str(data.get("response_body") or "")[:5000],
            "resource_type": data.get("resource_type", "unknown"),
            "console_logs": data.get("console_logs") or [],
            "capture_session_id": data.get("capture_session_id", ""),
        }
        await asyncio.to_thread(self._append_sync, item)

    async def save_console_logs(self, session_id: str, logs: List[dict]) -> None:
        """Save console logs as a separate entry for a capture session."""
        if not logs:
            return
        item = {
            "id": f"console_{session_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": "console_logs",
            "method": "CONSOLE",
            "status": 0,
            "response_time_ms": 0,
            "request_headers": {},
            "request_body": "",
            "response_headers": {},
            "response_body": "",
            "console_logs": logs[:100],
            "capture_session_id": session_id,
        }
        await asyncio.to_thread(self._append_sync, item)

    async def get_recent_requests(self, limit: int = 20, include_bodies: bool = False) -> List[Any]:
        def _get():
            items = self._read_all_sync()
            # Filter out console-only items
            items = [i for i in items if i.get("method") != "CONSOLE"]
            items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

            if not include_bodies:
                for item in items:
                    item["request_body"] = ""
                    item["response_body"] = ""

            return items

        return await asyncio.to_thread(_get)

    async def get_console_logs(self, session_id: Optional[str] = None, limit: int = 100) -> List[Any]:
        def _get():
            items = self._read_all_sync()

            # Extract console logs from items
            all_logs = []
            for item in items:
                # Filter by session ID if provided
                if session_id and item.get("capture_session_id") != session_id:
                    continue

                logs = item.get("console_logs", [])
                if logs:
                    sess_id = item.get("capture_session_id", item.get("id"))
                    for log in logs:
                        log_entry = dict(log)
                        log_entry["session_id"] = sess_id
                        log_entry["capture_timestamp"] = item.get("timestamp")
                        all_logs.append(log_entry)

            return sorted(all_logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

        return await asyncio.to_thread(_get)

    async def get_failed_requests(self, limit: int = 20, include_bodies: bool = False) -> List[Any]:
        def _get():
            items = self._read_all_sync()
            items = [i for i in items if (i.get("status") or 0) >= 400 and i.get("method") != "CONSOLE"]
            items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

            if not include_bodies:
                for item in items:
                    item["request_body"] = ""
                    item["response_body"] = ""

            return items

        return await asyncio.to_thread(_get)

    async def get_by_url(self, url: str, include_body: bool = False) -> List[Any]:
        def _get():
            items = self._read_all_sync()
            items = [i for i in items if url in (i.get("url") or "") and i.get("method") != "CONSOLE"]

            if not include_body:
                for item in items:
                    item["request_body"] = ""
                    item["response_body"] = ""

            return items

        return await asyncio.to_thread(_get)

    async def search_requests(
        self,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        url_contains: Optional[str] = None,
        limit: int = 20,
        include_bodies: bool = False,
    ) -> List[Any]:
        def _get():
            items = self._read_all_sync()
            # Filter out console-only items
            items = [i for i in items if i.get("method") != "CONSOLE"]

            if method:
                items = [i for i in items if i.get("method") == method.upper()]
            if status_code is not None:
                items = [i for i in items if i.get("status") == status_code]
            if url_contains:
                items = [i for i in items if url_contains in (i.get("url") or "")]

            items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

            if not include_bodies:
                for item in items:
                    item["request_body"] = ""
                    item["response_body"] = ""

            return items

        return await asyncio.to_thread(_get)

    async def get_slow_requests(self, threshold_ms: int, include_bodies: bool = False) -> List[Any]:
        def _get():
            items = self._read_all_sync()
            items = [i for i in items if (i.get("response_time_ms") or 0) >= threshold_ms and i.get("method") != "CONSOLE"]

            if not include_bodies:
                for item in items:
                    item["request_body"] = ""
                    item["response_body"] = ""

            return items

        return await asyncio.to_thread(_get)

    async def clear_all(self) -> None:
        def _clear():
            if os.path.exists(self.path):
                os.remove(self.path)

        await asyncio.to_thread(_clear)
