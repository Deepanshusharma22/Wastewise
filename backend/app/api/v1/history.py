from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ...config import Settings, get_settings
from ...database.supabase_client import SupabaseGateway
from ...schemas.prediction import Category, FeedbackIn, FeedbackOut, HistoryDetail, HistoryPage
from ...services import history_service
from ...services.history_service import NotFound
from ...utils.security import AuthUser, get_current_user
from ..deps import get_gateway

router = APIRouter(prefix="/history", tags=["history"])

_NOT_FOUND = {"code": "not_found", "message": "Prediction not found."}


@router.get("", response_model=HistoryPage, summary="List the caller's predictions (paginated, filterable)")
async def list_history(
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(12, ge=1, le=50),
    category: Category | None = None,
    confident: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["newest", "oldest", "confidence_desc", "confidence_asc"] = "newest",
    user: AuthUser = Depends(get_current_user),
    gw: SupabaseGateway = Depends(get_gateway),
    settings: Settings = Depends(get_settings),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, detail={"code": "invalid_date_range", "message": "date_from must be before date_to."})
    return await history_service.list_history(gw, settings, user, page=page, page_size=page_size, category=category,
                                              confident=confident, date_from=date_from, date_to=date_to, sort=sort)


@router.get("/{prediction_id}", response_model=HistoryDetail)
async def get_prediction(prediction_id: UUID, user: AuthUser = Depends(get_current_user),
                         gw: SupabaseGateway = Depends(get_gateway), settings: Settings = Depends(get_settings)):
    try:
        return await history_service.get_detail(gw, settings, user, str(prediction_id))
    except NotFound:
        raise HTTPException(404, detail=_NOT_FOUND)


@router.delete("/{prediction_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a prediction and its stored image")
async def delete_prediction(prediction_id: UUID, user: AuthUser = Depends(get_current_user),
                            gw: SupabaseGateway = Depends(get_gateway), settings: Settings = Depends(get_settings)):
    try:
        await history_service.delete_prediction(gw, settings, user, str(prediction_id))
    except NotFound:
        raise HTTPException(404, detail=_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{prediction_id}/feedback", response_model=FeedbackOut,
            summary="Record whether the prediction was correct (stored for review, not auto-used for training)")
async def put_feedback(prediction_id: UUID, body: FeedbackIn, user: AuthUser = Depends(get_current_user),
                       gw: SupabaseGateway = Depends(get_gateway)):
    if body.user_correctness_feedback and body.corrected_category:
        raise HTTPException(400, detail={"code": "invalid_feedback",
                                         "message": "corrected_category is only allowed when the prediction was wrong."})
    try:
        return await history_service.upsert_feedback(gw, user, str(prediction_id), body.model_dump())
    except NotFound:
        raise HTTPException(404, detail=_NOT_FOUND)
