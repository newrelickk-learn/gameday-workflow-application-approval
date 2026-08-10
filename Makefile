.PHONY: help install dev-install run build build-local build-prod test lint clean up down docker-build docker-logs docker-restart test-curl create-db

# 変数定義
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker-compose
DOCKER_COMPOSE_FILE := docker-compose.yml
DOCKER_COMPOSE_PROD_FILE := docker-compose.prod.yml
PORT := 8002

help:
	@echo "利用可能なコマンド:"
	@echo "  make install          - 本番依存関係をインストール"
	@echo "  make dev-install      - 開発依存関係をインストール"
	@echo "  make run              - ローカルでアプリケーションを実行"
	@echo "  make build            - Dockerイメージをビルド（ローカル用ARM）"
	@echo "  make build-prod       - Dockerイメージをビルド（本番用x86-64）"
	@echo "  make test             - テストを実行"
	@echo "  make lint             - リンターを実行"
	@echo "  make clean            - 一時ファイルを削除"
	@echo "  make up               - docker-composeでコンテナを起動"
	@echo "  make down             - docker-composeでコンテナを停止"
	@echo "  make docker-build     - docker-composeでイメージをビルド"
	@echo "  make docker-logs      - docker-composeでログを表示"
	@echo "  make docker-restart   - docker-composeでコンテナを再起動"
	@echo "  make create-db        - gameday_workflow_applicationデータベースを作成"
	@echo "  make fix-enum         - データベースのENUM型をVARCHAR型に変更"
	@echo "  make test-curl        - curlでAPIをテスト"

install:
	$(PIP) install -r requirements.txt

dev-install:
	$(PIP) install -r requirements-dev.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port $(PORT) --reload

build: build-local

build-local:
	@echo "ローカル用（ARM）Dockerイメージをビルド中..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) build

build-prod:
	@echo "本番用（x86-64）Dockerイメージをビルド中..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_PROD_FILE) build

test:
	pytest tests/ -v

lint:
	ruff check app/ tests/
	mypy app/

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

up:
	@echo "docker-composeでコンテナを起動中..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up

down:
	@echo "docker-composeでコンテナを停止中..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down

docker-build:
	@echo "docker-composeでイメージをビルド中..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) build

docker-logs:
	@echo "docker-composeでログを表示中..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) logs -f

docker-restart:
	@echo "docker-composeでコンテナを再起動中..."
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) restart

create-db:
	@echo "gameday_workflow_applicationデータベースを作成中..."
	@./scripts/create_database.sh

fix-enum:
	@echo "データベースのENUM型をVARCHAR型に変更中..."
	@./scripts/fix_enum_type.sh

test-curl:
	@./scripts/test-api.sh

# テスト用curlコンテナの起動
test-curl-up:
	@echo "テスト用curlコンテナを起動中..."
	@$(DOCKER_COMPOSE) --profile test up -d test-curl
	@echo "テスト用curlコンテナが起動しました。"
	@echo "使用方法:"
	@echo "  docker exec -it gameday-workflow-test-curl curl http://gameday_workflow_user_api:80/users/28151"
	@echo "  docker exec -it gameday-workflow-test-curl sh  # シェルに入る"

# テスト用curlコンテナの停止
test-curl-down:
	@echo "テスト用curlコンテナを停止中..."
	@$(DOCKER_COMPOSE) --profile test down test-curl
	@echo "テスト用curlコンテナを停止しました。"

# テスト用curlコンテナでシェルに入る
test-curl-shell:
	@docker exec -it gameday-workflow-test-curl sh