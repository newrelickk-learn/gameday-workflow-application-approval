"""章クリアの引換券(HMAC署名付きトークン)の発行。

裏クエストやプロモーション(章5)は「申請が成立したこと」自体が達成条件だが、ここから
game-masterを直接呼ぶと申請のトレースにgame-masterが混ざってしまう。そこで申請レスポンスに
署名付きトークンだけを載せ、frontendがそれを持ってgame-masterへクリアを記録しに行く形にしている。

署名が無いとブラウザから任意の章を「クリアした」と申告できてしまうため、鍵が未設定の場合は
トークンを発行しない(signed_token)。
"""

from typing import Optional
import logging
import time

from app.services import signed_token
from app.models.application import ApplicationType

logger = logging.getLogger(__name__)

# 裏クエストの章番号。メインストリーム(0〜5)と衝突しないよう101番台を使う。
HIDDEN_QUEST_EXPENSE = 101
HIDDEN_QUEST_BUSINESS_TRIP = 102
# ランブックの暫定対応を自分の会社に適用できたら達成
HIDDEN_QUEST_APPROVED_LIST_REMEDIATION = 103

HIDDEN_QUEST_BY_APPLICATION_TYPE = {
    # 上長を設定したうえで経費申請を出せたら達成
    ApplicationType.EXPENSE.value: HIDDEN_QUEST_EXPENSE,
    # AIレビューを通過して国内出張申請を出せたら達成
    ApplicationType.BUSINESS_TRIP.value: HIDDEN_QUEST_BUSINESS_TRIP,
}

# 裏クエストごとに必要な申請者のロール。Noneならロールを問わない。
# 経費申請は「上長が未設定のエンジニアが、上長を設定したうえで申請できた」ことが達成条件なので、
# 上長を持っているマネージャーの申請では達成にしない。
REQUIRED_APPLICANT_ROLE_BY_HIDDEN_QUEST = {
    HIDDEN_QUEST_EXPENSE: "engineer",
    HIDDEN_QUEST_BUSINESS_TRIP: None,
}

TOKEN_TTL_SECONDS = 300


def issue(company_id: str, chapter: int, ttl_seconds: int = TOKEN_TTL_SECONDS) -> Optional[str]:
    return signed_token.sign(
        {"companyId": str(company_id), "chapter": chapter, "exp": int(time.time()) + ttl_seconds}
    )


def issue_for_application_type(
    company_id: Optional[str],
    application_type: str,
    applicant_role: Optional[str] = None,
) -> Optional[str]:
    """申請タイプに対応する裏クエストがあればトークンを発行する。

    裏クエストによっては申請者のロールを条件にしているため、合致しない場合は発行しない。
    """
    if company_id is None:
        return None

    chapter = HIDDEN_QUEST_BY_APPLICATION_TYPE.get(application_type)
    if chapter is None:
        return None

    required_role = REQUIRED_APPLICANT_ROLE_BY_HIDDEN_QUEST.get(chapter)
    if required_role is not None and (applicant_role or "").lower() != required_role:
        logger.info(
            f"hidden_quest_token: 申請者のロールが条件に合わないため発行しません。"
            f"chapter={chapter}, required={required_role}, actual={applicant_role}"
        )
        return None

    return issue(str(company_id), chapter)
