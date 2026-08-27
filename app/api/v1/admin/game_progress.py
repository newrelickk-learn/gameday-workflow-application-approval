from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.dependencies import get_db_dependency, get_current_user_dependency
from app.services.user_service import UserService
from app.services.game_progress_service import GameProgressService

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateGameProgressRequest(BaseModel):
    virtual_date_offset_days: int = Field(..., alias="virtualDateOffsetDays", description="実際の今日からのオフセット日数")

    class Config:
        populate_by_name = True


class GameProgressResponse(BaseModel):
    virtual_date_offset_days: int = Field(..., alias="virtualDateOffsetDays")

    class Config:
        populate_by_name = True


def _resolve_company_id(current_user: dict) -> Optional[str]:
    token = current_user.get("_token")
    user_id = current_user.get("user_id") or current_user.get("sub")
    user_info = UserService.get_user_info(user_id, token)
    if not user_info:
        return None
    company_id = user_info.get("CompanyId") or user_info.get("companyId")
    if company_id is None:
        return None
    return str(company_id)


@router.patch(
    "/admin/game-progress",
    response_model=GameProgressResponse,
    status_code=http_status.HTTP_200_OK,
    summary="GameDay仮想時間進行状態の直接設定（運営用）",
    description=(
        "ログイン中ユーザーのcompany_idに対応するgame_progress.virtual_date_offset_daysを"
        "直接設定します。演習開始前の初期設定（例: -365で1年前からスタート）など、"
        "通常の申請承認による自動進行では表現できない値を設定するために使う。"
        "認証トークンから取得したcompany_id専用の行のみ更新可能（他チームの行は更新できない）。"
    ),
    responses={
        401: {"description": "認証が必要です／CompanyIdが取得できません"},
        404: {"description": "対象company_idのgame_progressが見つかりません"},
    },
)
async def update_game_progress(
    request: UpdateGameProgressRequest,
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> GameProgressResponse:
    company_id = _resolve_company_id(current_user)
    if company_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "ユーザーのCompanyIdが取得できませんでした"},
        )

    progress = GameProgressService.set_offset(db, company_id, request.virtual_date_offset_days)
    if progress is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": "GAME_PROGRESS_NOT_FOUND", "message": "対象company_idのgame_progressが見つかりません"},
        )

    logger.info(
        "GameProgressAdmin: virtual_date_offset_daysを更新しました - company_id=%s, value=%s",
        company_id,
        progress.virtual_date_offset_days,
    )

    return GameProgressResponse(virtual_date_offset_days=progress.virtual_date_offset_days)
