from fastapi import APIRouter

from app.services.scoring_service import score_categories

router = APIRouter()


@router.get("/scores")
def scores() -> dict:
    return {"items": score_categories()}

