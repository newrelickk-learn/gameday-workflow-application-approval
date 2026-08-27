import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import newrelic.agent

from app.api.dependencies import get_db_dependency
from app.core.config import settings
from app.services.chapter_progress_service import ChapterProgressService

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_internal_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    if not settings.user_service_api_key or x_api_key != settings.user_service_api_key:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "Invalid internal API key"},
        )


class MarkChapterClearedRequest(BaseModel):
    company_id: str = Field(..., alias="companyId")

    class Config:
        populate_by_name = True


class MarkChapterClearedResponse(BaseModel):
    cleared: bool = True


@router.post(
    "/internal/chapters/{chapter}/mark-cleared",
    response_model=MarkChapterClearedResponse,
    status_code=http_status.HTTP_200_OK,
    summary="[サービス間通信専用] 指定した会社の章クリアを記録する",
    description=(
        "ユーザーのJWTを持たない他サービス（例: gameday-workflow-userのログイン処理）から、"
        "company_idを直接指定して章クリアを記録するための内部API。X-API-Keyヘッダーで認証する。"
    ),
)
async def mark_chapter_cleared(
    chapter: int,
    request: MarkChapterClearedRequest,
    db: Session = Depends(get_db_dependency),
    _: None = Depends(verify_internal_api_key),
) -> MarkChapterClearedResponse:
    newrelic.agent.set_transaction_name('/v0.1/internal/chapters/{chapter}/mark-cleared')
    newrelic.agent.add_custom_attribute('chapter', chapter)
    newrelic.agent.add_custom_attribute('company_id', request.company_id)

    ChapterProgressService.mark_cleared(db, request.company_id, chapter)
    return MarkChapterClearedResponse(cleared=True)
