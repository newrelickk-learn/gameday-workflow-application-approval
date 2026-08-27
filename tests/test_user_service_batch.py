from unittest.mock import patch, MagicMock

import httpx

from app.services.user_service import UserService
from app.core.config import settings


def test_get_users_info_uses_stub_when_enabled():
    assert settings.user_service_use_stub is True

    result = UserService.get_users_info(["28151", "21051"])

    assert set(result.keys()) == {"28151", "21051"}
    assert result["28151"]["role"] == "engineer"
    assert result["21051"]["role"] == "manager"


def test_get_users_info_with_empty_ids_returns_empty_dict():
    assert UserService.get_users_info([]) == {}
    assert UserService.get_users_info([None, "", "  "]) == {}


def test_get_users_info_deduplicates_ids_before_calling_batch_api():
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [
        {"id": "28151", "name": "開発エンジニア", "role": "engineer", "companyId": 1},
        {"id": "28152", "name": "開発エンジニア2", "role": "engineer", "companyId": 1},
    ]

    with patch.object(settings, "user_service_use_stub", False), \
         patch("app.services.user_service.httpx.get", return_value=mock_response) as mock_get:
        result = UserService.get_users_info(["28151", "28152", "28151", "28152"])

    assert mock_get.call_count == 1
    called_params = mock_get.call_args.kwargs["params"]
    assert sorted(v for _, v in called_params) == ["28151", "28152"]

    assert set(result.keys()) == {"28151", "28152"}
    assert result["28151"]["name"] == "開発エンジニア"


def test_get_users_info_falls_back_for_missing_known_ids():
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [
        {"id": "28151", "name": "開発エンジニア", "role": "engineer", "companyId": 1},
    ]

    with patch.object(settings, "user_service_use_stub", False), \
         patch("app.services.user_service.httpx.get", return_value=mock_response) as mock_get:
        result = UserService.get_users_info(["28151", "21051"])

    assert mock_get.call_count == 1
    assert set(result.keys()) == {"28151", "21051"}
    assert result["21051"]["role"] == "manager"  


def test_get_users_info_falls_back_on_connect_error():
    with patch.object(settings, "user_service_use_stub", False), \
         patch(
             "app.services.user_service.httpx.get",
             side_effect=httpx.ConnectError("connection refused"),
         ) as mock_get:
        result = UserService.get_users_info(["21051", "99999999"])

    assert mock_get.call_count == 1
    assert set(result.keys()) == {"21051"}
