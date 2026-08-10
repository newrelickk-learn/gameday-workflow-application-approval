# テスト手順

## 前提条件

1. PostgreSQLコンテナが起動していること
2. アプリケーションコンテナが起動していること

## テスト実行手順

### 1. データベースの作成（初回のみ）

```bash
make create-db
```

### 2. アプリケーションの起動

```bash
make up
```

### 3. APIテストの実行

#### 方法0: シナリオテスト（pytest）

他サービスと同じシナリオを網羅した申請APIのシナリオテストです。  
**DB**: 未指定時は SQLite メモリを使用（`USER_SERVICE_USE_STUB` / `WORKFLOW_SERVICE_USE_STUB` を有効にしているため外部サービス不要）。  
**実行**: 依存関係インストール後（例: `make dev-install`）、以下で実行。

```bash
make test
# または
pytest tests/ -v
```

- 出張・経費・休暇・プロモーションの4種の申請（成功ケース）
- プロモーションをエンジニアで申請 → 400 PERMISSION_DENIED
- 出張の2週間前未満申請 → 400 INSUFFICIENT_ADVANCE_NOTICE
- 不正タイプ・申請者ID不一致・一覧・詳細・404

#### 方法1: Makefileコマンドを使用

```bash
make test-curl
```

#### 方法2: テストスクリプトを使用（詳細なテスト）

```bash
./scripts/test-api.sh http://localhost:8002
```

### 4. 個別のAPIテスト

#### ヘルスチェック

```bash
curl http://localhost:8002/health
```

#### 申請一覧取得

```bash
curl -X GET "http://localhost:8002/applications" \
  -H "Authorization: Bearer test-token" \
  -H "Content-Type: application/json" | jq .
```

#### 申請作成

```bash
curl -X POST "http://localhost:8002/applications" \
  -H "Authorization: Bearer test-token" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "business-trip",
    "title": "東京出張申請",
    "description": "技術カンファレンス参加のため東京へ出張",
    "startDate": "2024-04-15",
    "endDate": "2024-04-17",
    "days": 3,
    "applicantId": "28151"
  }' | jq .
```

#### 申請詳細取得

```bash
# 上記の申請作成で返されたIDを使用
curl -X GET "http://localhost:8002/applications/{申請ID}" \
  -H "Authorization: Bearer test-token" \
  -H "Content-Type: application/json" | jq .
```

## 期待される結果

- ヘルスチェック: `{"status": "healthy", "version": "1.0.0"}`
- 申請一覧取得: 空の配列 `[]` または申請の配列
- 申請作成: 作成された申請オブジェクト（ID、ステータス等を含む）
- 申請詳細取得: 指定されたIDの申請オブジェクト

## トラブルシューティング

### データベース接続エラー

- PostgreSQLコンテナが起動しているか確認: `docker ps | grep gameday_workflow_db`
- データベースが作成されているか確認: `make create-db` を実行
- ネットワークが正しく設定されているか確認: `docker network ls | grep gameday-workflow-network`

### アプリケーションが起動しない

- ログを確認: `make docker-logs`
- コンテナの状態を確認: `docker ps -a | grep application-approval-service`

