import logging

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import newrelic.agent

from app.api.dependencies import get_db_dependency, get_current_user_dependency
from app.services.user_service import UserService
from app.services.game_progress_service import GameProgressService

logger = logging.getLogger(__name__)

router = APIRouter()


class GameProgressResponse(BaseModel):
    virtual_date_offset_days: int = Field(
        ..., alias="virtualDateOffsetDays", description="実際の今日からのオフセット日数"
    )

    class Config:
        populate_by_name = True


@router.get(
    "/game-progress",
    response_model=GameProgressResponse,
    status_code=http_status.HTTP_200_OK,
    summary="GameDay仮想時間進行状態取得",
    description=(
        "ログイン中ユーザーのcompany_idに対応するgame_progressを取得します。"
        "frontendのgetVirtualToday()から利用され、'実際の今日 + virtualDateOffsetDays' として"
        "「仮想今日」を算出するために使用される。"
    ),
    responses={
        401: {"description": "認証が必要です"},
        400: {"description": "CompanyIdが取得できません"},
    },
)
async def get_game_progress(
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> GameProgressResponse:
    newrelic.agent.set_transaction_name('/v0.1/game_progress')

    token = current_user.get("_token")
    user_id = current_user.get("user_id") or current_user.get("sub")
    newrelic.agent.add_custom_attribute('user_id', user_id)

    user_info = UserService.get_user_info(user_id, token)
    if not user_info:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "ユーザー情報を取得できませんでした"},
        )

    company_id = user_info.get("CompanyId") or user_info.get("companyId")
    if company_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": "COMPANY_ID_NOT_FOUND", "message": "ユーザーのCompanyIdが取得できません"},
        )
    company_id = str(company_id)
    newrelic.agent.add_custom_attribute('company_id', company_id)

    progress = GameProgressService.get_active_progress(db, company_id)
    offset_days = progress.virtual_date_offset_days if progress else 0
    newrelic.agent.add_custom_attribute('virtual_date_offset_days', offset_days)

    return GameProgressResponse(virtual_date_offset_days=offset_days)
