from typing import Dict, Iterable, Optional
import logging

# httpxは外部サービス呼び出し時に使用（現在はスタブ実装）
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class ManagerNotFoundError(Exception):
    """
    対象ユーザーの直属マネージャーが見つからない場合の例外

    User Service の `GET /users/{id}/manager` が
    404 + {"error": "MANAGER_NOT_FOUND"} を返した場合（ManagerId未設定等）に発生する。
    ユーザー自体が見つからない場合（404 + {"error": "USER_NOT_FOUND"}）とは区別する。
    """
    pass


class UserService:
    """ユーザー情報取得サービス"""

    @staticmethod
    def _get_user_from_api(user_id: str, token: Optional[str] = None) -> Optional[dict]:
        """
        外部サービスAPIからユーザー情報を取得します
        
        Args:
            user_id: ユーザーID
            token: 認証トークン（オプション）
            
        Returns:
            ユーザー情報の辞書、取得失敗時はNone
        """
        if not HTTPX_AVAILABLE:
            logger.warning("httpxが利用できないため、スタブ実装を使用します")
            return None
        
        try:
            url = f"{settings.user_service_base_url}/users/{user_id}"
            headers = {
                "X-API-Key": settings.user_service_api_key
            }
            # ユーザートークンも追加（オプション）
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            logger.info(f"UserService: 外部サービスAPIを呼び出し中: {url}, base_url={settings.user_service_base_url}")
            response = httpx.get(url, headers=headers, timeout=5.0)
            response.raise_for_status()
            user_info = response.json()
            logger.info(f"UserService: 外部サービスAPIからユーザー情報を取得成功: user_id={user_id}")
            return user_info
        except httpx.ConnectError as e:
            logger.error(f"UserService: 接続エラー - コンテナ名またはポートが間違っている可能性があります。url={url}, error={e}")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"ユーザーが見つかりません: user_id={user_id}")
            elif e.response.status_code == 401:
                logger.error(f"認証エラー: User Service APIがAPI Keyまたはトークンを拒否しました。user_id={user_id}, url={url}")
                # API Keyが正しく設定されているか確認
                if not settings.user_service_api_key:
                    logger.error("USER_SERVICE_API_KEYが設定されていません")
            else:
                logger.error(f"ユーザー情報取得エラー: status={e.response.status_code}, user_id={user_id}, url={url}")
            return None
        except Exception as e:
            logger.error(f"ユーザー情報の取得に失敗しました: {e}")
            return None
    
    @staticmethod
    def get_user_info(user_id: str, token: Optional[str] = None) -> Optional[dict]:
        """
        ユーザー情報を取得します
        User Service API仕様に準拠: GET /users/{id}
        
        Args:
            user_id: ユーザーID
            token: 認証トークン（オプション、外部サービス呼び出し時に使用）
            
        Returns:
            ユーザー情報の辞書（id, name, email, role, departmentを含む）、取得失敗時はNone
        """
        user_id = str(user_id).strip() if user_id is not None else ""
        # スタブ実装を使用する設定の場合
        if settings.user_service_use_stub:
            logger.info(f"UserService: スタブ実装を使用（設定による）。user_id={user_id}")
            return UserService._get_stub_user_info(user_id)
        
        # 外部サービスから取得を試みる
        user_info = UserService._get_user_from_api(user_id, token)
        
        if user_info:
            return user_info
        
        # 外部サービスが利用できない場合
        # スタブ実装が有効な場合のみフォールバック
        if settings.user_service_use_stub:
            logger.warning(f"UserService: 外部サービスが利用できないため、スタブ実装を使用中。user_id={user_id}")
            return UserService._get_stub_user_info(user_id)
        
        # 外部サービス失敗時も、既知のユーザーID範囲（上長21051-21100等）ではスタブでフォールバックする。
        # これにより、ユーザーサービス接続失敗時でもプロモーション申請などの権限判定が動作する。
        try:
            uid = int(user_id)
            if (1051 <= uid <= 1100) or (16051 <= uid <= 16100) or (21051 <= uid <= 21100) or (28151 <= uid <= 28200):
                logger.warning(f"UserService: 外部サービス取得失敗のため、既知ID用スタブでフォールバック。user_id={user_id}")
                return UserService._get_stub_user_info(user_id)
        except (ValueError, TypeError):
            pass
        logger.error(f"UserService: 外部サービスからユーザー情報を取得できませんでした。user_id={user_id}")
        return None

    @staticmethod
    def get_users_info(user_ids: Iterable[str], token: Optional[str] = None) -> Dict[str, dict]:
        """
        複数ユーザーの情報を一括取得します（User Service の GET /users/batch を1回だけ呼び出す）。
        承認者向け申請一覧のように、申請件数分get_user_infoをループ呼び出しするとN+1になる
        箇所で使用する。

        Args:
            user_ids: 取得したいユーザーIDのコレクション（重複していてもよい。内部で重複除去する）
            token: 認証トークン（オプション）

        Returns:
            {user_id(str): user_info_dict} の辞書。見つからなかった・取得できなかったuser_idは
            キーに含まれない（呼び出し元でNone/欠損として扱う想定）。例外は投げない。
        """
        ids = sorted({str(uid).strip() for uid in user_ids if uid is not None and str(uid).strip()})
        if not ids:
            return {}

        # スタブ実装を使用する設定の場合
        if settings.user_service_use_stub:
            logger.info(f"UserService: get_users_info スタブ実装を使用（設定による）。ids={ids}")
            return {uid: UserService._get_stub_user_info(uid) for uid in ids}

        if not HTTPX_AVAILABLE:
            logger.warning("httpxが利用できないため、get_users_infoはフォールバックのみ使用します")
            return UserService._get_users_info_fallback(ids)

        result: Dict[str, dict] = {}
        url = f"{settings.user_service_base_url}/users/batch"
        try:
            headers = {
                "X-API-Key": settings.user_service_api_key
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            params = [("ids", uid) for uid in ids]

            logger.info(f"UserService: バッチ取得APIを呼び出し中: {url}, ids_count={len(ids)}")
            response = httpx.get(url, headers=headers, params=params, timeout=10.0)
            response.raise_for_status()
            users = response.json()
            for user_info in users:
                uid = user_info.get("id")
                if uid is None:
                    uid = user_info.get("Id")
                if uid is not None:
                    result[str(uid)] = user_info
            logger.info(
                f"UserService: バッチ取得成功: requested={len(ids)}, found={len(result)}"
            )
        except httpx.ConnectError as e:
            logger.error(
                f"UserService: バッチ取得の接続エラー - url={url}, error={e}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"UserService: バッチ取得エラー: status={e.response.status_code}, url={url}"
            )
        except Exception as e:
            logger.error(f"UserService: バッチ取得に失敗しました: {e}")

        missing = [uid for uid in ids if uid not in result]
        if missing:
            result.update(UserService._get_users_info_fallback(missing))

        return result

    @staticmethod
    def _get_users_info_fallback(user_ids: Iterable[str]) -> Dict[str, dict]:
        """
        外部サービスから取得できなかった・欠損したuser_idのうち、既知のユーザーID範囲
        （上長21051-21100等）のものだけスタブでフォールバックします。
        get_user_infoが単一ID取得時に行う既知ID範囲フォールバックと同じ範囲・方針です。
        """
        result: Dict[str, dict] = {}
        for user_id in user_ids:
            try:
                uid = int(user_id)
            except (ValueError, TypeError):
                continue
            if (1051 <= uid <= 1100) or (16051 <= uid <= 16100) or (21051 <= uid <= 21100) or (28151 <= uid <= 28200):
                logger.warning(
                    f"UserService: バッチ取得失敗のため、既知ID用スタブでフォールバック。user_id={user_id}"
                )
                result[str(user_id)] = UserService._get_stub_user_info(str(user_id))
        return result

    @staticmethod
    def get_manager(user_id: str, token: Optional[str] = None) -> Optional[dict]:
        """
        ユーザーの直属マネージャー情報を取得します
        User Service API仕様: GET /users/{id}/manager
          - 200: マネージャーのUserDto
          - 404 + {"error": "USER_NOT_FOUND"}: 対象ユーザー自体が存在しない
          - 404 + {"error": "MANAGER_NOT_FOUND", "message": "承認者が見つかりません"}:
            ManagerId未設定等で直属マネージャーが決定できない

        `_get_user_from_api`（GET /users/{id}）とは異なり、404の場合にレスポンスボディの
        `error`コードを見て「ユーザーが存在しない」のか「ManagerIdが未設定」なのかを区別する。
        後者の場合は`ManagerNotFoundError`を発生させ、呼び出し元で明確なエラーとして扱えるようにする。

        Args:
            user_id: 対象ユーザーID
            token: 認証トークン（オプション、外部サービス呼び出し時に使用）

        Returns:
            マネージャー情報の辞書、対象ユーザーが見つからない/外部サービス利用不可の場合はNone

        Raises:
            ManagerNotFoundError: ManagerId未設定等で直属マネージャーが見つからない場合
        """
        user_id = str(user_id).strip() if user_id is not None else ""

        # スタブ実装を使用する設定の場合
        if settings.user_service_use_stub:
            logger.info(f"UserService: get_manager スタブ実装を使用（設定による）。user_id={user_id}")
            return UserService._get_stub_manager_info(user_id)

        if not HTTPX_AVAILABLE:
            logger.warning("httpxが利用できないため、get_managerをスキップします")
            return None

        url = f"{settings.user_service_base_url}/users/{user_id}/manager"
        try:
            headers = {
                "X-API-Key": settings.user_service_api_key
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"

            logger.info(f"UserService: 直属マネージャー取得APIを呼び出し中: {url}")
            response = httpx.get(url, headers=headers, timeout=5.0)

            if response.status_code == 404:
                try:
                    body = response.json()
                except Exception:
                    body = {}
                error_code = body.get("error")
                if error_code == "MANAGER_NOT_FOUND":
                    logger.warning(
                        f"UserService: 直属マネージャーが見つかりません（ManagerId未設定の可能性）。"
                        f"user_id={user_id}"
                    )
                    raise ManagerNotFoundError(body.get("message") or "承認者が見つかりません")
                logger.warning(
                    f"UserService: get_manager対象のユーザーが見つかりません。"
                    f"user_id={user_id}, error={error_code}"
                )
                return None

            response.raise_for_status()
            manager_info = response.json()
            logger.info(f"UserService: 直属マネージャー取得成功: user_id={user_id}")
            return manager_info
        except ManagerNotFoundError:
            raise
        except httpx.ConnectError as e:
            logger.error(f"UserService: 接続エラー（get_manager） - url={url}, error={e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"UserService: HTTPエラー（get_manager） - status={e.response.status_code}, "
                f"user_id={user_id}, url={url}"
            )
            return None
        except Exception as e:
            logger.error(f"UserService: 直属マネージャーの取得に失敗しました: {e}")
            return None

    @staticmethod
    def _get_stub_manager_info(user_id: str) -> Optional[dict]:
        """
        スタブ実装: 直属マネージャー情報を返します
        （company_idに対応する「上長」ロールのスタブユーザーを返す）

        Args:
            user_id: 対象ユーザーID

        Returns:
            マネージャー情報の辞書
        """
        user_info = UserService._get_stub_user_info(user_id)
        company_id = user_info.get("companyId", 1)
        manager_id = str(21051 + company_id - 1)
        return UserService._get_stub_user_info(manager_id)

    @staticmethod
    def _get_stub_user_info(user_id: str) -> dict:
        """
        スタブ実装: ユーザー情報を返します
        
        Args:
            user_id: ユーザーID
            
        Returns:
            ユーザー情報の辞書
        """
        user_id = str(user_id).strip() if user_id is not None else "0"
        # スタブ実装: ユーザーID範囲に基づいて役割を判定
        user_id_int = int(user_id) if user_id.isdigit() else 0
        
        # CompanyIdを計算（ユーザーIDから逆算）
        # 本部長: ID 1051-1100 -> CompanyId 1-50
        # 経理: ID 16051-16100 -> CompanyId 1-50
        # 上長: ID 21051-21100 -> CompanyId 1-50
        # 開発エンジニア: ID 28151-28200 -> CompanyId 1-50
        def calculate_company_id(user_id_int: int) -> int:
            if 1051 <= user_id_int <= 1100:
                return user_id_int - 1051 + 1
            elif 16051 <= user_id_int <= 16100:
                return user_id_int - 16051 + 1
            elif 21051 <= user_id_int <= 21100:
                return user_id_int - 21051 + 1
            elif 28151 <= user_id_int <= 28200:
                return user_id_int - 28151 + 1
            else:
                return 1  # デフォルト
        
        company_id = calculate_company_id(user_id_int)
        
        # 本部長 (director): ID 1051-1100
        if 1051 <= user_id_int <= 1100:
            return {
                "id": user_id,
                "name": "本部長" if user_id_int == 1051 else f"本部長{user_id}",
                "email": "director@example.com" if user_id_int == 1051 else f"director{user_id}@example.com",
                "role": "director",
                "department": "本部",
                "companyId": company_id,
            }
        
        # 経理 (accounting): ID 16051-16100
        if 16051 <= user_id_int <= 16100:
            return {
                "id": user_id,
                "name": "経理" if user_id_int == 16051 else f"経理{user_id}",
                "email": "accounting@example.com" if user_id_int == 16051 else f"accounting{user_id}@example.com",
                "role": "accounting",
                "department": "経理部",
                "companyId": company_id,
            }
        
        # 上長 (manager): ID 21051-21100
        if 21051 <= user_id_int <= 21100:
            return {
                "id": user_id,
                "name": "上長" if user_id_int == 21051 else f"上長{user_id}",
                "email": "manager@example.com" if user_id_int == 21051 else f"manager{user_id}@example.com",
                "role": "manager",
                "department": "管理部",
                "companyId": company_id,
            }
        
        # 開発エンジニア (engineer): ID 28151-28200
        if 28151 <= user_id_int <= 28200:
            return {
                "id": user_id,
                "name": "開発エンジニア" if user_id_int == 28151 else f"開発エンジニア{user_id}",
                "email": "engineer@example.com" if user_id_int == 28151 else f"engineer{user_id}@example.com",
                "role": "engineer",
                "department": "開発組織",
                "companyId": company_id,
            }
        
        # デフォルト: engineerとして扱う
        return {
            "id": user_id,
            "name": f"ユーザー{user_id}",
            "email": f"user{user_id}@example.com",
            "role": "engineer",
            "department": None,
            "companyId": company_id,
        }
    
    @staticmethod
    def get_user_role(user_id: str, token: Optional[str] = None) -> str:
        """
        ユーザーの役割を取得します
        User Service API仕様に準拠: roleは "engineer", "manager", "admin" のいずれか
        
        Args:
            user_id: ユーザーID
            token: 認証トークン（オプション）
            
        Returns:
            ユーザーの役割（"engineer", "manager", "admin"のいずれか、小文字に正規化）
        """
        user_info = UserService.get_user_info(user_id, token)
        if not user_info:
            return "engineer"
        # .NET API は PascalCase (Role) で返す場合があるため両方受け付ける
        role = user_info.get("role") or user_info.get("Role")
        if role is not None and str(role).strip():
            return str(role).strip().lower()
        return "engineer"
    
    @staticmethod
    def is_manager(user_id: str, token: Optional[str] = None) -> bool:
        """
        ユーザーが上長かどうかを判定します
        manager, admin, director, accounting の場合にTrueを返します
        
        Args:
            user_id: ユーザーID
            token: 認証トークン（オプション）
            
        Returns:
            上長（manager/admin/director/accounting）の場合True、それ以外False
        """
        role = UserService.get_user_role(user_id, token)
        is_manager_role = role in ["manager", "admin", "director", "accounting"]
        logger.info(
            "UserService.is_manager: user_id=%s role=%s is_manager=%s",
            user_id,
            role,
            is_manager_role,
        )
        return is_manager_role

