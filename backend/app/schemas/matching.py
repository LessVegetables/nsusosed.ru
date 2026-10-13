from __future__ import annotations
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class DimensionDetail(BaseModel):
    key: str
    candidate_value: int
    room_average: float
    similarity: float
    weight: float
    contribution_points: float
    label: str


class Compatibility(BaseModel):
    score: int
    score_raw: float
    score_version: int
    warnings: List[str] = []
    dimensions: List[DimensionDetail] = []


class MatchItem(BaseModel):
    id: UUID
    kind: str
    building: Optional[str] = None
    room_number: Optional[int] = None
    district: Optional[str] = None
    free_places: int
    answered_count: int
    occupied_count: int
    compatibility: Compatibility


class MatchListResponse(BaseModel):
    items: List[MatchItem]
    total: int
    offset: int
    limit: int
    score_version: int


class ContactResponse(BaseModel):
    telegram_url: str
