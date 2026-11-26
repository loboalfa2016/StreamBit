from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.recommendations import RecommendationsResponse
from app.services.recommendations import get_recommendations_for_user

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get(
    "",
    response_model=RecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener recomendaciones generales o personalizadas de películas disponibles",
)
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_recommendations_for_user(db=db, current_user=current_user, limit=limit)
