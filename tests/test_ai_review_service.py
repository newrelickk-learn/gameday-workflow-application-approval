"""出張申請のAIレビュー(Amazon Bedrock)の挙動。

Bedrockは呼ばずに、Converse APIのレスポンス形だけを模したダブルを差し込んで検証する。
"""

from typing import Optional

import pytest

from app.core.config import settings
from app.services.ai_review_service import AiReviewService
import app.services.ai_review_service as ai_review_module


class FakeBedrockClient:
    def __init__(self, text: str = "", error: Optional[Exception] = None):
        self._text = text
        self._error = error
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return {"output": {"message": {"content": [{"text": self._text}]}}}


@pytest.fixture
def enable_ai_review(monkeypatch):
    monkeypatch.setattr(settings, "ai_review_enabled", True)


def use_client(monkeypatch, client: FakeBedrockClient) -> FakeBedrockClient:
    monkeypatch.setattr(ai_review_module, "_get_client", lambda: client)
    return client


def test_empty_description_is_rejected_without_calling_bedrock(enable_ai_review, monkeypatch):
    client = use_client(monkeypatch, FakeBedrockClient(text='{"approved": true}'))

    result = AiReviewService.review_business_trip(title="出張", description="   ")

    assert result.approved is False
    assert result.reason == AiReviewService.empty_description_reason()
    assert client.calls == []


def test_approved_response_passes(enable_ai_review, monkeypatch):
    use_client(monkeypatch, FakeBedrockClient(text='{"approved": true, "reason": ""}'))

    result = AiReviewService.review_business_trip(
        title="札幌支社訪問",
        description="札幌支社で新システムの移行計画について、先方の情報システム部と2日間の打ち合わせを行います。",
    )

    assert result.approved is True
    assert result.reason is None


def test_rejected_response_returns_the_reason_from_the_model(enable_ai_review, monkeypatch):
    use_client(
        monkeypatch,
        FakeBedrockClient(text='{"approved": false, "reason": "訪問先と業務内容を追記してください。"}'),
    )

    result = AiReviewService.review_business_trip(title="出張", description="よろしくお願いします")

    assert result.approved is False
    assert result.reason == "訪問先と業務内容を追記してください。"


def test_response_wrapped_in_a_code_fence_is_still_parsed(enable_ai_review, monkeypatch):
    use_client(
        monkeypatch,
        FakeBedrockClient(text='```json\n{"approved": false, "reason": "目的が不明です。"}\n```'),
    )

    result = AiReviewService.review_business_trip(title="出張", description="行きます")

    assert result.approved is False
    assert result.reason == "目的が不明です。"


def test_unparseable_response_is_rejected_with_the_fallback_reason(enable_ai_review, monkeypatch):
    use_client(monkeypatch, FakeBedrockClient(text="判定できませんでした"))

    result = AiReviewService.review_business_trip(title="出張", description="行きます")

    assert result.approved is False
    assert result.reason == AiReviewService.fallback_reason()


def test_bedrock_failure_lets_the_application_through(enable_ai_review, monkeypatch):
    # GameDay当日にAWS側で問題が起きても演習が止まらないよう、通す側に倒す
    use_client(monkeypatch, FakeBedrockClient(error=RuntimeError("AccessDeniedException")))

    result = AiReviewService.review_business_trip(title="出張", description="行きます")

    assert result.approved is True


def test_disabled_flag_skips_the_review_entirely(monkeypatch):
    monkeypatch.setattr(settings, "ai_review_enabled", False)
    client = use_client(monkeypatch, FakeBedrockClient(text='{"approved": false}'))

    result = AiReviewService.review_business_trip(title="出張", description="")

    assert result.approved is True
    assert client.calls == []


def test_review_reason_follows_the_display_language(enable_ai_review, monkeypatch):
    from app.core.i18n import set_current_locale

    use_client(monkeypatch, FakeBedrockClient(text='{"approved": true}'))
    try:
        set_current_locale("en")
        result = AiReviewService.review_business_trip(title="Trip", description="   ")
        assert result.approved is False
        # 空欄の差し戻しは表示言語に合わせて英語で返る
        assert result.reason == "Describe the purpose of the trip, who you will visit, and what you will do there."
    finally:
        set_current_locale("ja")
