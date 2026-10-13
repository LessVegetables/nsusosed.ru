from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: Dict[str, str] = {}
    request_id: str = ""
    retry_after: Optional[int] = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
