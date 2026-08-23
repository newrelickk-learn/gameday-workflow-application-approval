"""
申請 API のシナリオテスト（他サービスと同じシナリオを網羅）。

- 出張申請: エンジニアで申請 → 201
- 経費申請: エンジニアで申請 → 201
- 休暇申請: エンジニアで申請 → 201
- プロモーション申請: 上長で申請 → 201、エンジニアで申請 → 400 PERMISSION_DENIED
- 一覧・詳細・バリデーションエラー（2週間前、不正タイプ、申請者ID不一致）も確認
- 申請書番号（applicationNumber）の発行フォーマット・連番・検索も確認
"""
import re
from datetime import date, timedelta
from unittest.mock import patch

from app.services.user_service import UserService
from tests.conftest import (
    ENGINEER_USER_ID,
    MANAGER_USER_ID,
    auth_headers,
)


def _future_start_end(days_ahead: int = 14, span_days: int = 3):
    start = date.today() + timedelta(days=days_ahead)
    end = start + timedelta(days=span_days - 1)
    return start.isoformat(), end.isoformat()


# --- 申請作成シナリオ（成功） ---


def test_scenario_business_trip_engineer(client):
    """出張申請: エンジニアで申請 → 201"""
    start, end = _future_start_end(14, 3)
    payload = {
        "type": "business-trip",
        "title": "東京出張申請",
        "description": "技術カンファレンス参加",
        "startDate": start,
        "endDate": end,
        "days": 3,
        "applicantId": ENGINEER_USER_ID,
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "business-trip"
    assert data["status"] == "pending"
    assert data["applicantId"] == ENGINEER_USER_ID
    assert data.get("id")


def test_scenario_expense_engineer(client):
    """経費申請: エンジニアで申請 → 201"""
    payload = {
        "type": "expense",
        "title": "交通費精算",
        "description": "出張時の交通費",
        "amount": 85000,
        "applicantId": ENGINEER_USER_ID,
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "expense"
    assert data["status"] == "pending"
    assert data.get("amount") == 85000


def test_scenario_vacation_engineer(client):
    """休暇申請: エンジニアで申請 → 201"""
    start, end = _future_start_end(7, 2)
    payload = {
        "type": "vacation",
        "title": "有給休暇申請",
        "description": "私用のため",
        "startDate": start,
        "endDate": end,
        "days": 2,
        "applicantId": ENGINEER_USER_ID,
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "vacation"
    assert data["status"] == "pending"


def test_scenario_promotion_manager(client):
    """プロモーション申請: 上長で申請 → 201"""
    payload = {
        "type": "promotion",
        "title": "プロモーション申請",
        "description": "新商品のプロモーション活動",
        "applicantId": MANAGER_USER_ID,
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(MANAGER_USER_ID),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "promotion"
    assert data["status"] == "pending"
    assert data["applicantId"] == MANAGER_USER_ID


# --- 申請作成シナリオ（期待どおり失敗） ---


def test_scenario_promotion_engineer_permission_denied(client):
    """プロモーション申請: エンジニアで申請 → 400 PERMISSION_DENIED"""
    payload = {
        "type": "promotion",
        "title": "プロモーション申請（一般社員）",
        "description": "一般社員によるプロモーション申請",
        "applicantId": ENGINEER_USER_ID,
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("detail", {}).get("error") == "PERMISSION_DENIED"
    assert "上長のみ" in (data.get("detail", {}).get("message") or "")


def test_scenario_business_trip_insufficient_advance(client):
    """出張申請: 2週間前未満 → 400 INSUFFICIENT_ADVANCE_NOTICE"""
    start, end = _future_start_end(1, 1)
    payload = {
        "type": "business-trip",
        "title": "急な出張申請",
        "description": "2週間前ではない出張申請",
        "startDate": start,
        "endDate": end,
        "days": 1,
        "applicantId": ENGINEER_USER_ID,
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("detail", {}).get("error") == "INSUFFICIENT_ADVANCE_NOTICE"


def test_scenario_invalid_application_type(client):
    """不正な申請タイプ → 400 INVALID_APPLICATION_TYPE"""
    payload = {
        "type": "invalid-type",
        "title": "テスト申請",
        "description": "テスト",
        "applicantId": ENGINEER_USER_ID,
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("detail", {}).get("error") == "INVALID_APPLICATION_TYPE"


def test_scenario_applicant_id_mismatch(client):
    """申請者IDがトークンと不一致 → 400 INVALID_APPLICANT_ID"""
    start, end = _future_start_end(14, 1)
    payload = {
        "type": "business-trip",
        "title": "出張",
        "description": "テスト",
        "startDate": start,
        "endDate": end,
        "days": 1,
        "applicantId": MANAGER_USER_ID,  # トークンはエンジニア
    }
    resp = client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("detail", {}).get("error") == "INVALID_APPLICANT_ID"


# --- 一覧・詳細 ---


def test_scenario_list_and_detail(client):
    """申請一覧取得 → 200、申請作成 → 201、詳細取得 → 200"""
    # 一覧（空でもよい）
    list_resp = client.get(
        "/api/v1/applications",
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert list_resp.status_code == 200
    assert isinstance(list_resp.json(), list)

    # 1件作成
    start, end = _future_start_end(14, 2)
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "type": "business-trip",
            "title": "一覧・詳細テスト",
            "description": "テスト",
            "startDate": start,
            "endDate": end,
            "days": 2,
            "applicantId": ENGINEER_USER_ID,
        },
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # 詳細
    detail_resp = client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == app_id
    assert detail_resp.json()["type"] == "business-trip"


def test_scenario_list_filter_by_status(client):
    """申請一覧: status=pending でフィルタ → 200"""
    resp = client.get(
        "/api/v1/applications?status=pending",
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_scenario_list_filter_by_applicant_id(client):
    """申請一覧: applicantId でフィルタ → 200"""
    resp = client.get(
        f"/api/v1/applications?applicantId={ENGINEER_USER_ID}",
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_scenario_list_calls_user_service_batch_once_regardless_of_application_count(client):
    """申請一覧: 同一申請者による複数件の申請があっても、申請者情報のバッチ取得は1回だけ呼ばれる
    （N+1解消の回帰テスト。以前は申請件数分UserService.get_user_infoがループ呼び出しされていた）"""
    start, end = _future_start_end(14, 2)
    for _ in range(3):
        resp = client.post(
            "/api/v1/applications",
            json={
                "type": "business-trip",
                "title": "N+1回帰テスト用申請",
                "description": "テスト",
                "startDate": start,
                "endDate": end,
                "days": 2,
                "applicantId": ENGINEER_USER_ID,
            },
            headers=auth_headers(ENGINEER_USER_ID),
        )
        assert resp.status_code == 201

    with patch.object(
        UserService, "get_users_info", wraps=UserService.get_users_info
    ) as mock_get_users_info:
        list_resp = client.get(
            "/api/v1/applications",
            headers=auth_headers(ENGINEER_USER_ID),
        )

    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 3
    # 申請件数（3件以上）に関わらず、申請者情報のバッチ取得は1回だけ
    assert mock_get_users_info.call_count == 1


def test_scenario_get_nonexistent_application_returns_404(client):
    """存在しない申請IDで詳細取得 → 404"""
    resp = client.get(
        "/api/v1/applications/non-existent-id",
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 404


# --- 申請書番号（applicationNumber） ---


def test_scenario_business_trip_application_number_format(client):
    """出張申請の申請書番号 → BT-\\d{6}形式"""
    start, end = _future_start_end(14, 3)
    resp = client.post(
        "/api/v1/applications",
        json={
            "type": "business-trip",
            "title": "出張申請（番号確認）",
            "description": "テスト",
            "startDate": start,
            "endDate": end,
            "days": 3,
            "applicantId": ENGINEER_USER_ID,
        },
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 201
    application_number = resp.json().get("applicationNumber")
    assert re.match(r"^BT-\d{6}$", application_number or "")


def test_scenario_expense_application_number_format(client):
    """経費申請の申請書番号 → EX-\\d{6}形式"""
    resp = client.post(
        "/api/v1/applications",
        json={
            "type": "expense",
            "title": "経費申請（番号確認）",
            "description": "テスト",
            "amount": 1000,
            "applicantId": ENGINEER_USER_ID,
        },
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 201
    application_number = resp.json().get("applicationNumber")
    assert re.match(r"^EX-\d{6}$", application_number or "")


def test_scenario_application_number_increments_per_company(client):
    """同一会社・同一タイプで複数回作成すると申請書番号が連番で増加する"""
    start, end = _future_start_end(14, 2)
    payload = {
        "type": "vacation",
        "title": "有給休暇申請（連番確認）",
        "description": "テスト",
        "startDate": start,
        "endDate": end,
        "days": 2,
        "applicantId": ENGINEER_USER_ID,
    }
    resp1 = client.post("/api/v1/applications", json=payload, headers=auth_headers(ENGINEER_USER_ID))
    resp2 = client.post("/api/v1/applications", json=payload, headers=auth_headers(ENGINEER_USER_ID))
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    num1 = resp1.json()["applicationNumber"]
    num2 = resp2.json()["applicationNumber"]
    assert num1 != num2
    seq1 = int(num1.split("-")[1])
    seq2 = int(num2.split("-")[1])
    assert seq2 == seq1 + 1


def test_scenario_list_filter_by_application_number(client):
    """申請一覧: applicationNumberでフィルタ → 作成した申請がヒットする"""
    resp = client.post(
        "/api/v1/applications",
        json={
            "type": "expense",
            "title": "経費申請（番号検索確認）",
            "description": "テスト",
            "amount": 2000,
            "applicantId": ENGINEER_USER_ID,
        },
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 201
    application_number = resp.json()["applicationNumber"]
    app_id = resp.json()["id"]

    list_resp = client.get(
        f"/api/v1/applications?applicationNumber={application_number}",
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert list_resp.status_code == 200
    results = list_resp.json()
    assert any(item["id"] == app_id for item in results)


def test_scenario_list_filter_by_nonexistent_application_number(client):
    """申請一覧: 存在しないapplicationNumberでフィルタ → 空配列"""
    resp = client.get(
        "/api/v1/applications?applicationNumber=BT-999999",
        headers=auth_headers(ENGINEER_USER_ID),
    )
    assert resp.status_code == 200
    assert resp.json() == []
