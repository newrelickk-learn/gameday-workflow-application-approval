import logging
from typing import List

from fastapi import APIRouter, Depends, status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import newrelic.agent

from app.api.dependencies import get_current_user_dependency, get_db_dependency
from app.services.chapter_diagnosis_service import ChapterDiagnosisService
from app.services.chapter_progress_service import ChapterProgressService
from app.services.nplus1_quiz_service import NPlusOneQuizService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_company_id(current_user: dict) -> str | None:
    """current_userのトークンからCompanyIdを解決する（game_progress.pyと同じ考え方）"""
    token = current_user.get("_token")
    user_id = current_user.get("user_id") or current_user.get("sub")
    user_info = UserService.get_user_info(user_id, token)
    if not user_info:
        return None
    company_id = user_info.get("CompanyId") or user_info.get("companyId")
    return str(company_id) if company_id is not None else None


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
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> ChapterAnswerCheckResponse:
    """指定した章の原因診断ドロップダウンの選択が正解かどうかを判定します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/{chapter}/check-answer')
    newrelic.agent.add_custom_attribute('chapter', chapter)

    is_correct = ChapterDiagnosisService.check_answer(chapter, request.selected_text)
    newrelic.agent.add_custom_attribute('chapter.answer_correct', is_correct)

    if is_correct:
        company_id = _resolve_company_id(current_user)
        if company_id:
            newrelic.agent.add_custom_attribute('company_id', company_id)
            ChapterProgressService.mark_cleared(db, company_id, chapter)
        else:
            logger.warning(
                "check_chapter_answer: company_idが取得できないためchapter_progressを記録できません。chapter=%s",
                chapter,
            )

    return ChapterAnswerCheckResponse(correct=is_correct)


class NPlusOneQuizOptionsResponse(BaseModel):
    """第2章N+1診断クイズ（3問構成）の選択肢一覧（正解は含まない）"""
    q1: List[str] = Field(..., description="パフォーマンス問題の種類の選択肢（毎回シャッフルされる）")
    q2: List[str] = Field(..., description="問題が発生しているテーブルの選択肢（毎回シャッフルされる）")
    q3: List[str] = Field(..., description="改善方法の選択肢（毎回シャッフルされる）")


class NPlusOneQuizAnswersRequest(BaseModel):
    """第2章N+1診断クイズ（3問構成）で選ばれた選択肢のテキスト"""
    q1: List[str] = Field(..., description="パフォーマンス問題の種類として選んだ内容")
    q2: List[str] = Field(..., description="問題が発生しているテーブルとして選んだ内容（複数選択）")
    q3: List[str] = Field(..., description="改善方法として選んだ内容")


class NPlusOneQuizResultResponse(BaseModel):
    """第2章N+1診断クイズ（3問構成）の判定結果（正解テキスト自体は含まない）"""
    q1: bool = Field(..., description="Q1（パフォーマンス問題の種類）が正解と一致したか")
    q2: bool = Field(..., description="Q2（問題が発生しているテーブル）が正解と一致したか")
    q3: bool = Field(..., description="Q3（改善方法）が正解と一致したか")
    all_correct: bool = Field(..., alias="allCorrect", description="3問すべてが正解と一致したか")

    class Config:
        populate_by_name = True


@router.get(
    "/chapters/2/nplus1-quiz/options",
    response_model=NPlusOneQuizOptionsResponse,
    status_code=http_status.HTTP_200_OK,
    summary="第2章N+1診断クイズ（3問構成）の選択肢一覧",
    description=(
        "選択肢はリポジトリには暗号化された状態でのみ保存されており、"
        "このサービスのコンテナ内でのみ復号される。どれが正解かはレスポンスに含まない。"
    ),
)
async def get_nplus1_quiz_options(
    current_user: dict = Depends(get_current_user_dependency),
) -> NPlusOneQuizOptionsResponse:
    """第2章N+1診断クイズ（3問構成）の選択肢一覧を返します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/2/nplus1-quiz/options')
    options = NPlusOneQuizService.get_shuffled_options()
    return NPlusOneQuizOptionsResponse(**options)


@router.post(
    "/chapters/2/nplus1-quiz/check-answers",
    response_model=NPlusOneQuizResultResponse,
    status_code=http_status.HTTP_200_OK,
    summary="第2章N+1診断クイズ（3問構成）の判定",
    description=(
        "3問すべての回答をまとめて判定する。3問すべてが正解の場合のみ"
        "chapter_progressにクリアを記録する（一部の問だけ正解の場合は記録しない）。"
    ),
)
async def check_nplus1_quiz_answers(
    request: NPlusOneQuizAnswersRequest,
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> NPlusOneQuizResultResponse:
    """第2章N+1診断クイズ（3問構成）の回答をまとめて判定します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/2/nplus1-quiz/check-answers')

    results = NPlusOneQuizService.check_answers(request.q1, request.q2, request.q3)
    all_correct = all(results.values())
    newrelic.agent.add_custom_attribute('chapter.answer_correct', all_correct)

    if all_correct:
        company_id = _resolve_company_id(current_user)
        if company_id:
            newrelic.agent.add_custom_attribute('company_id', company_id)
            ChapterProgressService.mark_cleared(db, company_id, 2)
        else:
            logger.warning(
                "check_nplus1_quiz_answers: company_idが取得できないためchapter_progressを記録できません。"
            )

    return NPlusOneQuizResultResponse(
        q1=results["q1"],
        q2=results["q2"],
        q3=results["q3"],
        allCorrect=all_correct,
    )


class ChapterProgressResponse(BaseModel):
    """今日クリア済みの章番号一覧"""
    cleared_chapters: List[int] = Field(..., alias="clearedChapters")

    class Config:
        populate_by_name = True


@router.get(
    "/chapters/progress",
    response_model=ChapterProgressResponse,
    status_code=http_status.HTTP_200_OK,
    summary="今日クリア済みの章番号一覧",
    description="ログイン中ユーザーのcompany_idについて、今日のUTC日付でクリア済みの章番号一覧を返す。日付が変わるとクリア状態はリセットされる。",
)
async def get_chapter_progress(
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> ChapterProgressResponse:
    """今日クリア済みの章番号一覧を返します"""
    newrelic.agent.set_transaction_name('/v0.1/chapters/progress')

    company_id = _resolve_company_id(current_user)
    if not company_id:
        return ChapterProgressResponse(cleared_chapters=[])

    newrelic.agent.add_custom_attribute('company_id', company_id)
    cleared = ChapterProgressService.get_cleared_chapters_today(db, company_id)
    newrelic.agent.add_custom_attribute('chapter.cleared_count', len(cleared))
    return ChapterProgressResponse(cleared_chapters=cleared)
