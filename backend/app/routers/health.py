from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    health_status: dict[str, object] = {
        "status": "healthy",
        "version": "1.0.0",
        "checks": {},
    }

    try:
        db.execute(text("SELECT 1"))
        health_status["checks"] = {"database": "healthy"}
    except Exception:
        health_status["status"] = "degraded"
        health_status["checks"] = {"database": "unhealthy"}

    return health_status
