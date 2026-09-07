import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.dependencies import get_db_dependency
from app.api.v1.endpoints.internal import verify_internal_api_key
from app.services.chapter_mission_service import ChapterMissionService
from app.services.chapter_progress_service import ChapterProgressService

logger = logging.getLogger(__name__)

router = APIRouter()

TOTAL_TEAMS = 100


class TeamProgressItem(BaseModel):
    company_id: str = Field(..., alias="companyId")
    cleared_chapters: int = Field(..., alias="clearedChapters")

    class Config:
        populate_by_name = True


class TeamProgressResponse(BaseModel):
    total_chapters: int = Field(..., alias="totalChapters")
    teams: List[TeamProgressItem]

    class Config:
        populate_by_name = True


@router.get(
    "/admin/team-progress",
    response_model=TeamProgressResponse,
    summary="[運営用] 全チームの章クリア進捗一覧",
    description=(
        "company_id 1〜100の全チームについて、本日クリア済みの章数をまとめて返す。"
        "GameDayの進捗ボード（大画面表示）向けの集計API。X-API-Keyヘッダーで認証する。"
    ),
)
async def get_team_progress(
    db: Session = Depends(get_db_dependency),
    _: None = Depends(verify_internal_api_key),
) -> TeamProgressResponse:
    total_chapters = len(ChapterMissionService.get_active_missions(db))
    cleared_counts = ChapterProgressService.get_cleared_counts_today(db)

    teams = [
        TeamProgressItem(
            company_id=str(company_id),
            cleared_chapters=cleared_counts.get(str(company_id), 0),
        )
        for company_id in range(1, TOTAL_TEAMS + 1)
    ]

    return TeamProgressResponse(total_chapters=total_chapters, teams=teams)
