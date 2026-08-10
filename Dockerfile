FROM python:3.11-slim

WORKDIR /app

# システム依存関係のインストール
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# New Relic設定ファイルのコピー
COPY newrelic.ini .

# アプリケーションコードのコピー
COPY app/ ./app/

# ポート公開
EXPOSE 8002

ENTRYPOINT ["newrelic-admin", "run-program"]
# アプリケーション起動（New Relicはmain.pyで初期化）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]

