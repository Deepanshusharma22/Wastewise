from __future__ import annotations

from fastapi import APIRouter, Depends

from ...database.supabase_client import SupabaseGateway
from ...schemas.analytics import AnalyticsSummary, CategoryCount
from ...services import analytics_service
from ...utils.security import AuthUser
from ..deps import get_current_user, get_gateway

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsSummary, summary="The caller's scan statistics")
async def analytics(user: AuthUser = Depends(get_current_user), gw: SupabaseGateway = Depends(get_gateway)):
    return await analytics_service.user_analytics(gw, user)


@router.get("/category-distribution", response_model=list[CategoryCount])
async def category_distribution(user: AuthUser = Depends(get_current_user),
                                gw: SupabaseGateway = Depends(get_gateway)):
    return (await analytics_service.user_analytics(gw, user))["category_distribution"]
