from pydantic import BaseModel
from typing import Optional, Dict, Any


class NetworkRequest(BaseModel):
    url: str
    method: str
    status: int
    response_time_ms: Optional[int] = 0
    request_headers: Optional[Dict[str, str]] = {}
    request_body: Optional[Any] = None
    response_headers: Optional[Dict[str, str]] = {}
    response_body: Optional[Any] = None
