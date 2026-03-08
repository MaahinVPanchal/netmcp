"""Shared sanitization for request data before storage."""
from typing import Any, Dict
import os
import json

SENSITIVE_HEADERS = [
    "authorization",
    "cookie",
    "x-api-key",
    "x-auth-token",
    "set-cookie",
]


def sanitize_request(data: dict) -> dict:
    """Redact sensitive headers in request and response."""
    data = dict(data)
    for key in ("request_headers", "response_headers"):
        headers = data.get(key) or {}
        if isinstance(headers, dict):
            headers = dict(headers)
            for h in list(headers.keys()):
                if h.lower() in SENSITIVE_HEADERS:
                    headers[h] = "***REDACTED***"
            data[key] = headers
    return data


def cleanup_old_records(event, context):
    """
    Lambda handler for cleaning old records from DynamoDB.
    Triggered by EventBridge scheduled event.
    """
    import boto3
    from datetime import datetime, timezone, timedelta

    table_name = os.getenv("DYNAMO_TABLE", "netmcp-requests")
    retention_days = int(os.getenv("RETENTION_DAYS", "7"))

    try:
        dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
        table = dynamodb.Table(table_name)

        # TTL should handle cleanup automatically, but this is a fallback
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_iso = cutoff.isoformat()

        # Scan and delete old records (be careful with large tables)
        result = table.scan(
            FilterExpression="#ts < :cutoff",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={":cutoff": cutoff_iso},
            ProjectionExpression="id"
        )

        deleted_count = 0
        items = result.get("Items", [])

        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"id": item["id"]})
                deleted_count += 1

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "success",
                "deleted_count": deleted_count,
                "cutoff": cutoff_iso,
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }


def get_cost_estimate():
    """
    Get estimated monthly cost for NetMCP resources.
    This is a rough estimate based on typical usage patterns.
    """
    estimates = {
        "lambda_requests": {
            "free_tier": 1000000,  # 1M requests free
            "price_per_million": 0.20,
        },
        "lambda_compute": {
            "free_tier_gb_seconds": 400000,  # 400k GB-seconds
            "price_per_gb_second": 0.0000166667,
        },
        "dynamodb_write": {
            "price_per_million": 1.25,  # On-demand
        },
        "dynamodb_read": {
            "price_per_million": 0.25,  # On-demand
        },
        "api_gateway": {
            "free_tier": 1000000000,  # 1B requests free for 12 months
            "price_per_million": 3.50,
        },
    }
    return estimates


def check_storage_limits(data_size: int, max_size_mb: int = 100) -> bool:
    """
    Check if adding this data would exceed storage limits.
    Returns True if within limits, False if would exceed.
    """
    max_bytes = max_size_mb * 1024 * 1024
    return data_size <= max_bytes
