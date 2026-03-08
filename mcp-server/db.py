import boto3
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Any
import os

from util import sanitize_request

TABLE_NAME = os.getenv("DYNAMO_TABLE", "netmcp-requests")


class DynamoDBClient:
    def __init__(self):
        self.dynamo = boto3.resource(
            "dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        self.table = self.dynamo.Table(TABLE_NAME)

    def _sanitize(self, data: dict) -> dict:
        return sanitize_request(data)

    def _save_request_sync(self, data: dict) -> None:
        data = self._sanitize(data)
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
            "response_body": (data.get("response_body") or "")[:5000],
            "resource_type": data.get("resource_type", "unknown"),
            "console_logs": data.get("console_logs") or [],
            "capture_session_id": data.get("capture_session_id", ""),
            "ttl": int(datetime.now(timezone.utc).timestamp()) + 86400,
        }
        self.table.put_item(Item=item)

    async def save_request(self, data: dict) -> None:
        await asyncio.to_thread(self._save_request_sync, data)

    def _save_console_logs_sync(self, session_id: str, logs: List[dict]) -> None:
        """Save console logs as a separate item for a capture session."""
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
            "console_logs": logs[:100],  # Limit to 100 console logs per session
            "capture_session_id": session_id,
            "ttl": int(datetime.now(timezone.utc).timestamp()) + 86400,
        }
        self.table.put_item(Item=item)

    async def save_console_logs(self, session_id: str, logs: List[dict]) -> None:
        await asyncio.to_thread(self._save_console_logs_sync, session_id, logs)

    def _get_recent_sync(self, limit: int, include_bodies: bool = False) -> List[Any]:
        result = self.table.scan(Limit=limit * 2)
        items = result.get("Items", [])
        while result.get("LastEvaluatedKey"):
            result = self.table.scan(
                Limit=limit * 2, ExclusiveStartKey=result["LastEvaluatedKey"]
            )
            items.extend(result.get("Items", []))

        # Filter out console-only items
        items = [i for i in items if i.get("method") != "CONSOLE"]

        # Sort and limit
        items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

        # Optionally strip bodies to reduce payload size
        if not include_bodies:
            for item in items:
                item["request_body"] = ""
                item["response_body"] = ""

        return items

    async def get_recent_requests(self, limit: int = 20, include_bodies: bool = False) -> List[Any]:
        return await asyncio.to_thread(self._get_recent_sync, limit, include_bodies)

    def _get_console_logs_sync(self, session_id: Optional[str] = None, limit: int = 100) -> List[Any]:
        """Get console logs, optionally filtered by session ID."""
        if session_id:
            result = self.table.scan(
                FilterExpression="#s = :sid",
                ExpressionAttributeNames={"#s": "capture_session_id"},
                ExpressionAttributeValues={":sid": session_id},
            )
        else:
            # Get all items that have console_logs
            result = self.table.scan()

        items = result.get("Items", [])
        while result.get("LastEvaluatedKey"):
            result = self.table.scan(
                ExclusiveStartKey=result["LastEvaluatedKey"]
            )
            items.extend(result.get("Items", []))

        # Extract console logs from items
        all_logs = []
        for item in items:
            logs = item.get("console_logs", [])
            if logs:
                session = item.get("capture_session_id", item.get("id"))
                for log in logs:
                    log_entry = dict(log)
                    log_entry["session_id"] = session
                    log_entry["capture_timestamp"] = item.get("timestamp")
                    all_logs.append(log_entry)

        return sorted(all_logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

    async def get_console_logs(self, session_id: Optional[str] = None, limit: int = 100) -> List[Any]:
        return await asyncio.to_thread(self._get_console_logs_sync, session_id, limit)

    def _get_failed_sync(self, limit: int, include_bodies: bool = False) -> List[Any]:
        result = self.table.scan(
            FilterExpression="#s >= :code",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":code": 400},
            Limit=100,
        )
        items = result.get("Items", [])
        items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

        if not include_bodies:
            for item in items:
                item["request_body"] = ""
                item["response_body"] = ""

        return items

    async def get_failed_requests(self, limit: int = 20, include_bodies: bool = False) -> List[Any]:
        return await asyncio.to_thread(self._get_failed_sync, limit, include_bodies)

    def _get_by_url_sync(self, url: str, include_body: bool = False) -> List[Any]:
        result = self.table.scan(
            FilterExpression="contains(#u, :url)",
            ExpressionAttributeNames={"#u": "url"},
            ExpressionAttributeValues={":url": url},
        )
        items = result.get("Items", [])

        if not include_body:
            for item in items:
                item["request_body"] = ""
                item["response_body"] = ""

        return items

    async def get_by_url(self, url: str, include_body: bool = False) -> List[Any]:
        return await asyncio.to_thread(self._get_by_url_sync, url, include_body)

    def _search_sync(
        self,
        method: Optional[str],
        status_code: Optional[int],
        url_contains: Optional[str],
        limit: int,
        include_bodies: bool = False,
    ) -> List[Any]:
        result = self.table.scan()
        items = result.get("Items", [])
        while result.get("LastEvaluatedKey"):
            result = self.table.scan(
                ExclusiveStartKey=result["LastEvaluatedKey"]
            )
            items.extend(result.get("Items", []))

        # Filter out console-only items
        items = [i for i in items if i.get("method") != "CONSOLE"]

        if method:
            items = [i for i in items if i.get("method") == method.upper()]
        if status_code is not None:
            items = [
                i for i in items if i.get("status") == status_code
            ]
        if url_contains:
            items = [
                i
                for i in items
                if url_contains in (i.get("url") or "")
            ]

        items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

        if not include_bodies:
            for item in items:
                item["request_body"] = ""
                item["response_body"] = ""

        return items

    async def search_requests(
        self,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        url_contains: Optional[str] = None,
        limit: int = 20,
        include_bodies: bool = False,
    ) -> List[Any]:
        return await asyncio.to_thread(
            self._search_sync, method, status_code, url_contains, limit, include_bodies
        )

    def _get_slow_sync(self, threshold_ms: int, include_bodies: bool = False) -> List[Any]:
        result = self.table.scan(
            FilterExpression="#rt >= :threshold",
            ExpressionAttributeNames={"#rt": "response_time_ms"},
            ExpressionAttributeValues={":threshold": threshold_ms},
        )
        items = result.get("Items", [])

        if not include_bodies:
            for item in items:
                item["request_body"] = ""
                item["response_body"] = ""

        return items

    async def get_slow_requests(self, threshold_ms: int, include_bodies: bool = False) -> List[Any]:
        return await asyncio.to_thread(self._get_slow_sync, threshold_ms, include_bodies)

    def _clear_all_sync(self) -> None:
        result = self.table.scan(ProjectionExpression="id")
        items = result.get("Items", [])
        while result.get("LastEvaluatedKey"):
            result = self.table.scan(
                ProjectionExpression="id",
                ExclusiveStartKey=result["LastEvaluatedKey"],
            )
            items.extend(result.get("Items", []))
        with self.table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"id": item["id"]})

    async def clear_all(self) -> None:
        await asyncio.to_thread(self._clear_all_sync)
