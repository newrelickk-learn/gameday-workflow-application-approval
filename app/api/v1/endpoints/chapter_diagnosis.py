import logging
from typing import List

from fastapi import APIRouter, Depends, status as http_status
from pydantic import BaseModel, Field
import newrelic.agent

from app.api.dependencies import get_current_user_dependency
from app.services.chapter_diagnosis_service import ChapterDiagnosisService

logger = logging.getLogger(__name__)

router = APIRouter()


class ChapterOptionsResponse(BaseModel):
    """原因診断ドロップダウンの選択肢一覧（正解は含まない）"""
    options: List[str] = Field(..., description="診断の選択肢（毎回シャッフルされる）")


class ChapterAnswerCheckRequest(BaseModel):
    """診断ドロップダウンで選ばれた選択肢のテキスト"""
    selected_text: str = Field(..., alias="selectedText", description="選択された診断内容")

    class Config:
        populate_by_name = True


class ChapterAnswerCheckResponse(BaseModel):
    """判定結果（正解テキスト自体は含まない）"""
    correct: bool = Field(..., description="選択が正解と一致したか")


@router.get(
    "/chapters/{chapter}/diagnosis-options",
    response_model=ChapterOptionsResponse,
    status_code=http_status.HTTP_200_OK,
    summary="指定した章の原因診断ドロップダウンの選択肢一覧",
    description=(
        "選択肢はリポジトリには暗号化された状態でのみ保存されており、"
        "このサービスのコンテナ内でのみ復号される。どれが正解かはレスポンスに含まない。"
    ),
)
async def get_chapter_options(
    chapter: int,
    current_user: dict = Depends(get_current_user_dependency),
) -> ChapterOptionsResponse:
    """指定した章の原因診断ドロップダウンの選択肢一覧を返します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/{chapter}/diagnosis-options')
    newrelic.agent.add_custom_attribute('chapter', chapter)
    options = ChapterDiagnosisService.get_shuffled_options(chapter)
    return ChapterOptionsResponse(options=options)


@router.post(
    "/chapters/{chapter}/check-answer",
    response_model=ChapterAnswerCheckResponse,
    status_code=http_status.HTTP_200_OK,
    summary="指定した章の原因診断チェック",
    description=(
        "参加者が選んだ選択肢のテキストが正解と一致するかどうかだけを返す。"
        "正解テキスト自体（New Relicで確認できる情報）は暗号化された状態でのみ"
        "サーバー側に保持しており、レスポンスには含めない。"
    ),
)
async def check_chapter_answer(
    chapter: int,
    request: ChapterAnswerCheckRequest,
    current_user: dict = Depends(get_current_user_dependency),
) -> ChapterAnswerCheckResponse:
    """指定した章の原因診断ドロップダウンの選択が正解かどうかを判定します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/{chapter}/check-answer')
    newrelic.agent.add_custom_attribute('chapter', chapter)

    is_correct = ChapterDiagnosisService.check_answer(chapter, request.selected_text)
    newrelic.agent.add_custom_attribute('chapter.answer_correct', is_correct)

    return ChapterAnswerCheckResponse(correct=is_correct)
