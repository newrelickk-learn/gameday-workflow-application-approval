from typing import List, Optional
import logging

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class GameMasterClient:
    """gameday-workflow-game-masterサービスへのHTTPクライアント。

    進捗管理・スコア管理(仮想時間進行/章クリア進捗/章末診断クイズ)はgame-master側に
    切り出されているため、申請作成・承認フローから必要な操作をこのクライアント経由で
    呼び出す。
    """

    @staticmethod
    def get_game_progress(token: Optional[str]) -> Optional[int]:
        """ログイン中ユーザーのcompany_idに対応するvirtual_date_offset_daysを取得する。
        GET /game-progress をユーザーのJWTをそのまま転送して呼ぶ(company_idはgame-master側で
        トークンから解決される)。
        """
        if not HTTPX_AVAILABLE or not token:
            return None

        try:
            url = f"{settings.game_master_service_base_url}/api/v1/game-progress"
            headers = {"Authorization": f"Bearer {token}"}
            response = httpx.get(url, headers=headers, timeout=5.0)
            response.raise_for_status()
            return response.json().get("virtualDateOffsetDays")
        except Exception as e:
            logger.error(f"GameMasterClient: game-progress取得に失敗しました: {e}")
            return None

    @staticmethod
    def get_cleared_chapters_today(token: Optional[str]) -> List[int]:
        """本日クリア済みの章番号一覧を取得する。GET /chapters/progress を呼ぶ。"""
        if not HTTPX_AVAILABLE or not token:
            return []

        try:
            url = f"{settings.game_master_service_base_url}/api/v1/chapters/progress"
            headers = {"Authorization": f"Bearer {token}"}
            response = httpx.get(url, headers=headers, timeout=5.0)
            response.raise_for_status()
            return response.json().get("clearedChapters", [])
        except Exception as e:
            logger.error(f"GameMasterClient: chapters/progress取得に失敗しました: {e}")
            return []

    @staticmethod
    def mark_chapter_cleared(company_id: str, chapter: int) -> bool:
        """指定した会社の章クリアを記録する。
        POST /internal/chapters/{chapter}/mark-cleared をX-API-Keyで呼ぶ。
        """
        if not HTTPX_AVAILABLE:
            return False

        try:
            url = f"{settings.game_master_service_base_url}/api/v1/internal/chapters/{chapter}/mark-cleared"
            headers = {
                "X-API-Key": settings.game_master_service_api_key,
                "Content-Type": "application/json",
            }
            response = httpx.post(url, headers=headers, json={"companyId": company_id}, timeout=5.0)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(
                f"GameMasterClient: mark-cleared呼び出しに失敗しました。"
                f"company_id={company_id}, chapter={chapter}, error={e}"
            )
            return False

    @staticmethod
    def mark_chapter_incorrect(company_id: str, chapter: int) -> bool:
        """指定した会社の不正解を記録する(スコア集計の減点対象)。
        POST /internal/chapters/{chapter}/mark-incorrect をX-API-Keyで呼ぶ。
        すでに当日クリア済みの章はgame-master側で減点対象外になる。
        """
        if not HTTPX_AVAILABLE:
            return False

        try:
            url = f"{settings.game_master_service_base_url}/api/v1/internal/chapters/{chapter}/mark-incorrect"
            headers = {
                "X-API-Key": settings.game_master_service_api_key,
                "Content-Type": "application/json",
            }
            response = httpx.post(url, headers=headers, json={"companyId": company_id}, timeout=5.0)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(
                f"GameMasterClient: mark-incorrect呼び出しに失敗しました。"
                f"company_id={company_id}, chapter={chapter}, error={e}"
            )
            return False

    @staticmethod
    def apply_approved_application(
        company_id: str, application_type: str, days: Optional[int]
    ) -> Optional[int]:
        """承認完了した申請の内容に応じてgame_progressの仮想時間を進める。
        POST /internal/game-progress/apply-approved-application をX-API-Keyで呼ぶ。
        """
        if not HTTPX_AVAILABLE:
            return None

        try:
            url = (
                f"{settings.game_master_service_base_url}"
                "/api/v1/internal/game-progress/apply-approved-application"
            )
            headers = {
                "X-API-Key": settings.game_master_service_api_key,
                "Content-Type": "application/json",
            }
            body = {"companyId": company_id, "applicationType": application_type, "days": days}
            response = httpx.post(url, headers=headers, json=body, timeout=5.0)
            response.raise_for_status()
            return response.json().get("virtualDateOffsetDays")
        except Exception as e:
            logger.error(
                f"GameMasterClient: apply-approved-application呼び出しに失敗しました。"
                f"company_id={company_id}, application_type={application_type}, error={e}"
            )
            return None
