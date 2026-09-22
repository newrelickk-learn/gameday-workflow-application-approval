"""APIが返す文言の多言語対応。

英語で演習を受けられるようにするため、利用者に見せるメッセージはここに集約する。
表示言語はリクエストごとのAccept-Languageヘッダから決まり、ContextVarで持ち回る
(バリデーションの発生箇所すべてにlocaleを引き回さずに済むようにするため)。
"""

from contextvars import ContextVar
from typing import Optional

DEFAULT_LOCALE = "ja"
SUPPORTED_LOCALES = ("ja", "en")

_current_locale: ContextVar[str] = ContextVar("current_locale", default=DEFAULT_LOCALE)

MESSAGES = {
    "approver_not_found": {
        "ja": "承認者が見つかりません",
        "en": "No approver was found",
    },
    "promotion_manager_only": {
        "ja": "プロモーション申請は上長のみが申請可能です",
        "en": "Only a manager can submit a promotion application",
    },
    "start_date_required": {
        "ja": "開始日は必須です",
        "en": "The start date is required",
    },
    "end_date_required": {
        "ja": "終了日は必須です",
        "en": "The end date is required",
    },
    "start_after_end": {
        "ja": "開始日は終了日以前である必要があります",
        "en": "The start date must be on or before the end date",
    },
    "business_trip_advance_notice": {
        "ja": "出張申請は開始日の2週間前までに申請する必要があります",
        "en": "A business trip must be submitted at least two weeks before the start date",
    },
    "business_trip_start_date_required": {
        "ja": "出張申請には開始日が必要です",
        "en": "A business trip application needs a start date",
    },
    "business_trip_end_date_required": {
        "ja": "出張申請には終了日が必要です",
        "en": "A business trip application needs an end date",
    },
    "expense_amount_required": {
        "ja": "経費申請には金額が必要です",
        "en": "An expense application needs an amount",
    },
    "vacation_start_date_required": {
        "ja": "有給休暇申請には開始日が必要です",
        "en": "A paid leave application needs a start date",
    },
    "vacation_end_date_required": {
        "ja": "有給休暇申請には終了日が必要です",
        "en": "A paid leave application needs an end date",
    },
    "amount_must_be_positive": {
        "ja": "金額は正の数である必要があります",
        "en": "The amount must be a positive number",
    },
    "days_must_be_positive": {
        "ja": "日数は正の数である必要があります",
        "en": "The number of days must be a positive number",
    },
    "applicant_mismatch": {
        "ja": "申請者IDは現在のユーザーIDと一致する必要があります",
        "en": "The applicant ID must match the ID of the current user",
    },
    "approval_completed": {
        "ja": "承認が完了し、申請が承認されました",
        "en": "The approval is complete and the application has been approved",
    },
    "application_rejected": {
        "ja": "申請が却下されました",
        "en": "The application was rejected",
    },
    "ai_review_empty_description": {
        "ja": "出張の目的・訪問先・そこで行う業務内容を説明欄に具体的に記入してください。",
        "en": "Describe the purpose of the trip, who you will visit, and what you will do there.",
    },
    "ai_review_fallback": {
        "ja": "説明が具体的ではありません。出張の目的・訪問先・そこで行う業務内容を記入してください。",
        "en": "The description is not specific enough. Add the purpose of the trip, who you will visit, and what you will do there.",
    },
}


def normalize_locale(value: Optional[str]) -> str:
    """Accept-Languageヘッダなどから表示言語を決める。未対応の値は日本語にする。"""
    if not value:
        return DEFAULT_LOCALE

    # "en-US,en;q=0.9" のような形式の先頭だけを見る
    primary = value.split(",")[0].split(";")[0].strip().lower()
    language = primary.split("-")[0]

    return language if language in SUPPORTED_LOCALES else DEFAULT_LOCALE


def set_current_locale(value: Optional[str]) -> str:
    locale = normalize_locale(value)
    _current_locale.set(locale)
    return locale


def get_current_locale() -> str:
    return _current_locale.get()


def t(key: str, locale: Optional[str] = None) -> str:
    """文言を引く。未登録のキーはそのまま返す(表示が消えるより気付きやすいため)。"""
    entry = MESSAGES.get(key)
    if entry is None:
        return key

    return entry.get(locale or get_current_locale()) or entry[DEFAULT_LOCALE]
