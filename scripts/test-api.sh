#!/bin/bash

# APIテスト用スクリプト
# 使用方法: ./scripts/test-api.sh [BASE_URL] [USER_ID]
# 例: ./scripts/test-api.sh http://localhost:8002 28151

BASE_URL="${1:-http://localhost:8002}"
USER_ID="${2:-28151}"  # デフォルト: 開発エンジニア
# トークンにユーザーIDを含める（スタブ実装でユーザーIDを抽出するため）
TOKEN="${TOKEN:-user-${USER_ID}}"

# ユーザーIDに基づいてユーザー情報を表示
echo "=== Application & Approval Service API テスト ==="
echo "Base URL: $BASE_URL"
echo "User ID: $USER_ID"
echo ""

# ヘルスチェック
echo "1. ヘルスチェック"
echo "GET $BASE_URL/health"
curl -s -X GET "$BASE_URL/health" | jq .
echo -e "\n"

# 申請一覧取得（空の状態）
echo "2. 申請一覧取得（初期状態）"
echo "GET $BASE_URL/applications"
curl -s -X GET "$BASE_URL/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
echo -e "\n"

# 申請作成（出張申請 - 2週間後）
FUTURE_DATE=$(date -v+14d -u +"%Y-%m-%d" 2>/dev/null || date -d "+14 days" -u +"%Y-%m-%d" 2>/dev/null || echo "2024-05-01")
END_DATE=$(date -v+16d -u +"%Y-%m-%d" 2>/dev/null || date -d "+16 days" -u +"%Y-%m-%d" 2>/dev/null || echo "2024-05-03")

echo "3. 申請作成（出張申請 - 開始日: $FUTURE_DATE）"
echo "POST $BASE_URL/applications"
RESPONSE=$(curl -s -X POST "$BASE_URL/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"business-trip\",
    \"title\": \"東京出張申請\",
    \"description\": \"技術カンファレンス参加のため東京へ出張\",
    \"startDate\": \"$FUTURE_DATE\",
    \"endDate\": \"$END_DATE\",
    \"days\": 3,
    \"applicantId\": \"$USER_ID\"
  }")
echo "$RESPONSE" | jq .

# 作成された申請のIDを取得
APPLICATION_ID=$(echo "$RESPONSE" | jq -r '.id')
echo -e "\n作成された申請ID: $APPLICATION_ID\n"

# 申請詳細取得
if [ "$APPLICATION_ID" != "null" ] && [ -n "$APPLICATION_ID" ]; then
  echo "4. 申請詳細取得（ID: $APPLICATION_ID）"
  echo "GET $BASE_URL/applications/$APPLICATION_ID"
  curl -s -X GET "$BASE_URL/applications/$APPLICATION_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" | jq .
  echo -e "\n"
fi

# 申請一覧取得（フィルタリング: status=pending）
echo "5. 申請一覧取得（ステータス: pending）"
echo "GET $BASE_URL/applications?status=pending"
curl -s -X GET "$BASE_URL/applications?status=pending" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
echo -e "\n"

# 申請一覧取得（フィルタリング: applicantId）
echo "6. 申請一覧取得（申請者ID: $USER_ID）"
echo "GET $BASE_URL/applications?applicantId=$USER_ID"
curl -s -X GET "$BASE_URL/applications?applicantId=$USER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
echo -e "\n"

# 経費精算申請の作成
echo "7. 申請作成（経費精算）"
echo "POST $BASE_URL/applications"
curl -s -X POST "$BASE_URL/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"expense\",
    \"title\": \"交通費精算\",
    \"description\": \"出張時の交通費\",
    \"amount\": 85000,
    \"applicantId\": \"$USER_ID\"
  }" | jq .
echo -e "\n"

# プロモーション申請の作成（上長のみ可能）
echo "7-2. 申請作成（プロモーション申請 - 上長のみ）"
echo "POST $BASE_URL/applications"
curl -s -X POST "$BASE_URL/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"promotion\",
    \"title\": \"プロモーション申請\",
    \"description\": \"新商品のプロモーション活動\",
    \"applicantId\": \"$USER_ID\"
  }" | jq .
echo -e "\n"

# バリデーションテスト: 出張申請の2週間前チェック（失敗するはず）
echo "7-3. バリデーションテスト（出張申請の2週間前チェック - 失敗するはず）"
echo "POST $BASE_URL/applications"
TODAY=$(date -u +"%Y-%m-%d")
TOMORROW=$(date -v+1d -u +"%Y-%m-%d" 2>/dev/null || date -d "+1 day" -u +"%Y-%m-%d" 2>/dev/null || echo "2024-04-16")
curl -s -X POST "$BASE_URL/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"business-trip\",
    \"title\": \"急な出張申請\",
    \"description\": \"2週間前ではない出張申請\",
    \"startDate\": \"$TOMORROW\",
    \"endDate\": \"$TOMORROW\",
    \"days\": 1,
    \"applicantId\": \"$USER_ID\"
  }" | jq .
echo -e "\n"

# エラーテスト: 不正な申請タイプ
echo "8. エラーテスト（不正な申請タイプ）"
echo "POST $BASE_URL/applications"
curl -s -X POST "$BASE_URL/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"invalid-type\",
    \"title\": \"テスト申請\",
    \"description\": \"テスト\",
    \"applicantId\": \"$USER_ID\"
  }" | jq .
echo -e "\n"

# エラーテスト: プロモーション申請を一般社員が申請（失敗するはず）
echo "8-2. エラーテスト（プロモーション申請を一般社員が申請 - 失敗するはず）"
echo "POST $BASE_URL/applications"
curl -s -X POST "$BASE_URL/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"promotion\",
    \"title\": \"プロモーション申請（一般社員）\",
    \"description\": \"一般社員によるプロモーション申請\",
    \"applicantId\": \"28151\"
  }" | jq .
echo -e "\n"

# エラーテスト: 存在しない申請ID
echo "9. エラーテスト（存在しない申請ID）"
echo "GET $BASE_URL/applications/non-existent-id"
curl -s -X GET "$BASE_URL/applications/non-existent-id" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
echo -e "\n"

# 上長ユーザーでのテスト（プロモーション申請が成功するはず）
if [ "$USER_ID" != "21051" ]; then
  echo "10. 上長ユーザーでのテスト（プロモーション申請 - 成功するはず）"
  echo "POST $BASE_URL/applications"
  curl -s -X POST "$BASE_URL/applications" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "promotion",
      "title": "プロモーション申請（上長）",
      "description": "上長によるプロモーション申請",
      "applicantId": "21051"
    }' | jq .
  echo -e "\n"
fi

# 上長ユーザーでのテスト（プロモーション申請が成功するはず）
if [ "$USER_ID" != "21051" ]; then
  echo "10. 上長ユーザーでのテスト（プロモーション申請 - 成功するはず）"
  echo "POST $BASE_URL/applications"
  curl -s -X POST "$BASE_URL/applications" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "promotion",
      "title": "プロモーション申請（上長）",
      "description": "上長によるプロモーション申請",
      "applicantId": "21051"
    }' | jq .
  echo -e "\n"
fi

echo "=== テスト完了 ==="
echo ""
echo "利用可能なユーザーID:"
echo "  - 開発エンジニア: 28151-28200 (例: 28151)"
echo "  - 上長: 21051-21100 (例: 21051)"
echo "  - 経理: 16051-16100 (例: 16051)"
echo "  - 本部長: 1051-1100 (例: 1051)"
echo ""
echo "使用方法: ./scripts/test-api.sh $BASE_URL 21051  # 上長ユーザーでテスト"
echo ""
echo "利用可能なユーザーID:"
echo "  - 開発エンジニア: 28151-28200 (例: 28151)"
echo "  - 上長: 21051-21100 (例: 21051)"
echo "  - 経理: 16051-16100 (例: 16051)"
echo "  - 本部長: 1051-1100 (例: 1051)"
echo ""
echo "使用方法: ./scripts/test-api.sh $BASE_URL 21051  # 上長ユーザーでテスト"

