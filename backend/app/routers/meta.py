from __future__ import annotations
from fastapi import APIRouter
from app.config import DORMS, FACULTIES

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta")
async def api_meta():
    """Reference lists the forms are built from. Public: nothing here is personal."""
    return {"faculties": FACULTIES, "dorms": DORMS}
