import logging
from typing import List

from fastapi import APIRouter, Depends, status as http_status
from pydantic import BaseModel, Field
import newrelic.agent

from app.api.dependencies import get_current_user_dependency
from app.services.chapter2_answer_service import Chapter2AnswerService

logger = logging.getLogger(__name__)

router = APIRouter()


class Chapter2OptionsResponse(BaseModel):
    """原因診断ドロップダウンの選択肢一覧（正解は含まない）"""
    options: List[str] = Field(..., description="診断の選択肢（毎回シャッフルされる）")


@router.get(
    "/chapters/2/diagnosis-options",
    response_model=Chapter2OptionsResponse,
    status_code=http_status.HTTP_200_OK,
    summary="第2章（申請書一覧のN+1）の原因診断ドロップダウンの選択肢一覧",
    description=(
        "選択肢100件はリポジトリには暗号化された状態でのみ保存されており、"
        "このサービスのコンテナ内でのみ復号される。どれが正解かはレスポンスに含まない。"
    ),
)
async def get_chapter2_options(
    current_user: dict = Depends(get_current_user_dependency),
) -> Chapter2OptionsResponse:
    """第2章の原因診断ドロップダウンの選択肢一覧を返します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/2/diagnosis-options')
    options = Chapter2AnswerService.get_shuffled_options()
    return Chapter2OptionsResponse(options=options)


class Chapter2AnswerCheckRequest(BaseModel):
    """第2章の原因診断ドロップダウンで選ばれた選択肢のテキスト"""
    selected_text: str = Field(..., alias="selectedText", description="選択された診断内容")

    class Config:
        populate_by_name = True


class Chapter2AnswerCheckResponse(BaseModel):
    """判定結果（正解テキスト自体は含まない）"""
    correct: bool = Field(..., description="選択が正解と一致したか")


@router.post(
    "/chapters/2/check-answer",
    response_model=Chapter2AnswerCheckResponse,
    status_code=http_status.HTTP_200_OK,
    summary="第2章（申請書一覧のN+1）の原因診断チェック",
    description=(
        "参加者が選んだ選択肢のテキストが正解と一致するかどうかだけを返す。"
        "正解テキスト自体（New RelicのPerformance Risk Groupsで確認できる情報）は"
        "暗号化された状態でのみサーバー側に保持しており、レスポンスには含めない。"
    ),
)
async def check_chapter2_answer(
    request: Chapter2AnswerCheckRequest,
    current_user: dict = Depends(get_current_user_dependency),
) -> Chapter2AnswerCheckResponse:
    """第2章の原因診断ドロップダウンの選択が正解かどうかを判定します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/2/check-answer')

    is_correct = Chapter2AnswerService.check_answer(request.selected_text)
    newrelic.agent.add_custom_attribute('chapter2.answer_correct', is_correct)

    return Chapter2AnswerCheckResponse(correct=is_correct)
