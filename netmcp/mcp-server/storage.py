"""Storage factory: DynamoDB or file (TXT/JSONL) from env."""
import os


def get_storage():
    backend = os.getenv("STORAGE_BACKEND", "").strip().lower()
    if not backend and not os.getenv("DYNAMO_TABLE"):
        backend = "files"
    if not backend:
        backend = "dynamodb"
    if backend in ("file", "files", "txt", "jsonl"):
        from storage_file import FileStorage
        path = os.getenv("NETMCP_LOG_FILE", "netmcp_logs.txt")
        return FileStorage(path)
    from db import DynamoDBClient
    return DynamoDBClient()
