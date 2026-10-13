from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from app.schemas.listing import ResidentBrief


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


class ListingDetail(BaseModel):
    id: UUID
    kind: str
    building: Optional[str] = None
    room_number: Optional[int] = None
    floor: Optional[int] = None
    capacity: int
    occupied_count: int
    free_places: int
    answered_count: int
    is_corner: Optional[bool] = None
    windows_count: Optional[int] = None
    view: Optional[str] = None
    layout: Optional[str] = None
    district: Optional[str] = None
    monthly_cost_per_person_rub: Optional[int] = None
    description: Optional[str] = None
    status: str
    residents: List[ResidentBrief] = []
    confirmed_at: datetime
    compatibility: Optional[Compatibility] = None


class ContactResponse(BaseModel):
    type: str
    value: str
    url: Optional[str] = None
