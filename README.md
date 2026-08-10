# Application & Approval Service

GameDay Workflow システムの申請・承認管理サービスAPI

## 技術スタック

- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- pytest

## セットアップ

### 1. 依存関係のインストール

```bash
# 開発環境
make dev-install

# 本番環境
make install
```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下の環境変数を設定してください：

```env
DATABASE_URL=postgresql://user:password@localhost:5432/gameday_workflow
SECRET_KEY=your-secret-key-change-in-production
DEBUG=false
```

### 3. データベースの準備

PostgreSQLデータベースが別プロジェクトのdocker-composeで起動していることを確認してください。

データベーステーブルはアプリケーション起動時に自動的に作成されます。

### 4. アプリケーションの起動

```bash
# ローカルで実行
make run

# Docker Composeで実行
make docker-build  # イメージをビルド
make docker-up     # コンテナを起動
```

## 使用方法

### APIエンドポイント

- `GET /applications` - 申請一覧取得
- `POST /applications` - 申請作成
- `GET /applications/{id}` - 申請詳細取得
- `GET /health` - ヘルスチェック
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc

### テスト

```bash
# テスト実行
make test

# curlでAPIテスト
make test-curl

# または直接スクリプトを実行
./scripts/test-api.sh http://localhost:8002
```

## Makefileコマンド

- `make install` - 本番依存関係をインストール
- `make dev-install` - 開発依存関係をインストール
- `make run` - ローカルでアプリケーションを実行
- `make build` / `make build-local` - Dockerイメージをビルド（ローカル用ARM、docker-compose使用）
- `make build-prod` - Dockerイメージをビルド（本番用x86-64、docker-compose使用）
- `make test` - テストを実行
- `make lint` - リンターを実行
- `make clean` - 一時ファイルを削除
- `make docker-up` - docker-composeでコンテナを起動
- `make docker-down` - docker-composeでコンテナを停止
- `make docker-build` - docker-composeでイメージをビルド
- `make docker-logs` - docker-composeでログを表示
- `make docker-restart` - docker-composeでコンテナを再起動
- `make test-curl` - curlでAPIをテスト

## プロジェクト構成

```
gameday-workflow-application-approval-service/
├── app/
│   ├── api/              # APIエンドポイント
│   ├── core/             # 設定・セキュリティ
│   ├── db/               # データベース設定
│   ├── models/           # SQLAlchemyモデル
│   ├── schemas/          # Pydanticスキーマ
│   ├── services/         # ビジネスロジック
│   └── main.py           # アプリケーションエントリーポイント
├── scripts/              # ユーティリティスクリプト
├── tests/                # テスト
├── Dockerfile            # Dockerイメージ定義
├── docker-compose.yml    # Docker Compose設定（ローカル用）
├── docker-compose.prod.yml # Docker Compose設定（本番用）
├── Makefile              # ビルド・実行コマンド
└── requirements.txt      # 依存関係
```

## 開発

### データベースマイグレーション

Alembicを使用してデータベースマイグレーションを管理します：

```bash
# マイグレーション作成
alembic revision --autogenerate -m "description"

# マイグレーション適用
alembic upgrade head
```

### リンター

```bash
make lint
```

## デプロイ

### Docker Composeビルド

```bash
# ローカル用（ARM）
make build-local
# または
make docker-build

# 本番用（x86-64）
make build-prod

# コンテナの起動・停止
make docker-up    # 起動
make docker-down   # 停止
make docker-logs   # ログ確認
make docker-restart # 再起動
```

### 環境変数

本番環境では以下の環境変数を設定してください：

- `DATABASE_URL` - PostgreSQL接続URL
- `SECRET_KEY` - JWT署名用の秘密鍵
- `DEBUG=false` - デバッグモードを無効化

