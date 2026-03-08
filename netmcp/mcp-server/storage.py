"""Storage factory: DynamoDB or file (TXT/JSONL) from env."""
import os


def get_storage():
    backend = os.getenv("STORAGE_BACKEND", "dynamodb").strip().lower()
    if backend in ("file", "files", "txt", "jsonl"):
        from storage_file import FileStorage
        path = os.getenv("NETMCP_LOG_FILE", "netmcp_logs.txt")
        return FileStorage(path)
    from db import DynamoDBClient
    return DynamoDBClient()
