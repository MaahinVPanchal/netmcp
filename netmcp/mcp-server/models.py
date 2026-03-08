from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class NetworkRequest(BaseModel):
    url: str
    method: str
    status: int
    response_time_ms: Optional[int] = 0
    request_headers: Optional[Dict[str, str]] = {}
    request_body: Optional[Any] = None
    response_headers: Optional[Dict[str, str]] = {}
    response_body: Optional[Any] = None
    resource_type: Optional[str] = "unknown"


class ConsoleLog(BaseModel):
    type: str  # 'log', 'debug', 'info', 'error', 'warning', 'page_error'
    text: str
    timestamp: float
    location: Optional[Dict[str, Any]] = {}
    source: Optional[str] = "console"


class CaptureResult(BaseModel):
    """Result from browser capture including network requests and console logs."""
    requests: List[NetworkRequest]
    console_logs: List[ConsoleLog]
