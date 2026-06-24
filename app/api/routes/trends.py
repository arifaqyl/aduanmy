from fastapi import APIRouter, Query

from app.services.trends_service import get_trends

router = APIRouter()


@router.get("/trends")
def trends(limit_terms: int = Query(default=12, ge=5, le=30)) -> dict:
    return get_trends(limit_terms=limit_terms)
