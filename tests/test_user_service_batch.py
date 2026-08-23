"""
UserService.get_users_info（バッチ取得）のユニットテスト。

承認者向け申請一覧（GET /applications）で、申請件数分get_user_infoをループ呼び出し
していたN+1問題を解消するために追加したバッチ取得メソッドが、意図通り
「重複除去したIDに対してhttpx.getを1回だけ呼ぶ」ことを検証する。
"""
from unittest.mock import patch, MagicMock

import httpx

from app.services.user_service import UserService
from app.core.config import settings


def test_get_users_info_uses_stub_when_enabled():
    """USER_SERVICE_USE_STUB=trueの場合、外部呼び出しをせずスタブ辞書を返す"""
    assert settings.user_service_use_stub is True

    result = UserService.get_users_info(["28151", "21051"])

    assert set(result.keys()) == {"28151", "21051"}
    assert result["28151"]["role"] == "engineer"
    assert result["21051"]["role"] == "manager"


def test_get_users_info_with_empty_ids_returns_empty_dict():
    assert UserService.get_users_info([]) == {}
    assert UserService.get_users_info([None, "", "  "]) == {}


def test_get_users_info_deduplicates_ids_before_calling_batch_api():
    """重複IDを渡しても、バッチAPI呼び出し（httpx.get）は1回だけ発生する"""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [
        {"id": "28151", "name": "開発エンジニア", "role": "engineer", "companyId": 1},
        {"id": "28152", "name": "開発エンジニア2", "role": "engineer", "companyId": 1},
    ]

    with patch.object(settings, "user_service_use_stub", False), \
         patch("app.services.user_service.httpx.get", return_value=mock_response) as mock_get:
        result = UserService.get_users_info(["28151", "28152", "28151", "28152"])

    # 4件（重複あり）渡しても呼び出しは1回だけ
    assert mock_get.call_count == 1
    called_params = mock_get.call_args.kwargs["params"]
    assert sorted(v for _, v in called_params) == ["28151", "28152"]

    assert set(result.keys()) == {"28151", "28152"}
    assert result["28151"]["name"] == "開発エンジニア"


def test_get_users_info_falls_back_for_missing_known_ids():
    """バッチAPIが一部のIDしか返さなかった場合、欠損分は既知ID範囲でフォールバックされる"""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    # 28151のみ返し、21051（既知の上長ID範囲）は欠損させる
    mock_response.json.return_value = [
        {"id": "28151", "name": "開発エンジニア", "role": "engineer", "companyId": 1},
    ]

    with patch.object(settings, "user_service_use_stub", False), \
         patch("app.services.user_service.httpx.get", return_value=mock_response) as mock_get:
        result = UserService.get_users_info(["28151", "21051"])

    assert mock_get.call_count == 1
    assert set(result.keys()) == {"28151", "21051"}
    assert result["21051"]["role"] == "manager"  # フォールバックのスタブ情報


def test_get_users_info_falls_back_on_connect_error():
    """バッチAPI呼び出し自体が失敗しても例外を投げず、既知ID範囲のみフォールバックする"""
    with patch.object(settings, "user_service_use_stub", False), \
         patch(
             "app.services.user_service.httpx.get",
             side_effect=httpx.ConnectError("connection refused"),
         ) as mock_get:
        result = UserService.get_users_info(["21051", "99999999"])

    assert mock_get.call_count == 1
    # 既知ID範囲(21051)のみフォールバックされ、範囲外(99999999)は結果に含まれない
    assert set(result.keys()) == {"21051"}
