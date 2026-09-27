"""game-masterを直接呼ばずに、進行状態の参照・更新をfrontend経由で行うためのトークン。

- 参照: frontendがgame-masterから取得した署名付きスナップショット(仮想日付・当日クリア済みの章)を
  X-Game-Stateヘッダで添えてくるので、署名を検証して値を使う。
- 更新: 承認完了による仮想時間の進行は、署名付きトークンにしてレスポンスに載せ、frontendが
  game-masterへ届ける。
"""

from dataclasses import dataclass
from typing import List, Optional
import logging
import time

from app.services import signed_token

logger = logging.getLogger(__name__)

GAME_STATE_HEADER = "X-Game-State"

GAME_STATE_TYPE = "game-state"
APPROVED_APPLICATION_TYPE = "approved-application"

APPROVED_APPLICATION_TOKEN_TTL_SECONDS = 300


@dataclass(frozen=True)
class GameState:
    company_id: str
    virtual_date_offset_days: int
    cleared_chapters: List[int]


def verify_game_state(token: Optional[str], user_id: Optional[str]) -> Optional[GameState]:
    """game-masterが発行したスナップショットを検証する。

    別のユーザーのスナップショットを使い回せないよう、発行対象のユーザーがリクエストした
    ユーザーと一致する場合だけ受け付ける。検証できない場合はNone(game-masterから取得できなかった
    ときと同じ扱い)。
    """
    payload = signed_token.decode(token)
    if payload is None or payload.get("typ") != GAME_STATE_TYPE:
        return None

    if user_id is None or payload.get("userId") != str(user_id):
        logger.warning("game_master_tokens: スナップショットのユーザーが一致しません")
        return None

    company_id = payload.get("companyId")
    offset_days = payload.get("virtualDateOffsetDays")
    cleared_chapters = payload.get("clearedChapters")
    if (
        not isinstance(company_id, str)
        or not isinstance(offset_days, int)
        or not isinstance(cleared_chapters, list)
        or not all(isinstance(c, int) for c in cleared_chapters)
    ):
        return None

    return GameState(
        company_id=company_id,
        virtual_date_offset_days=offset_days,
        cleared_chapters=cleared_chapters,
    )


def issue_approved_application(
    company_id: str, application_type: str, days: Optional[int]
) -> Optional[str]:
    """承認完了した申請の内容に応じて仮想時間を進めるためのトークンを発行する。"""
    return signed_token.sign(
        {
            "typ": APPROVED_APPLICATION_TYPE,
            "companyId": str(company_id),
            "applicationType": application_type,
            "days": days,
            "exp": int(time.time()) + APPROVED_APPLICATION_TOKEN_TTL_SECONDS,
        }
    )
