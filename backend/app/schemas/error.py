from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: Dict[str, str] = {}
    request_id: str = ""
    retry_after: Optional[int] = None
    # Extra facts the page needs to act on the error (e.g. which room already exists).
    data: Dict[str, Any] = {}


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
