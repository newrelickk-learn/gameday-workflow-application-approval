#!/bin/bash

# gameday_workflow_applicationデータベースを作成するスクリプト
# PostgreSQLコンテナが起動していることを前提とします

echo "gameday_workflow_applicationデータベースを作成中..."

docker exec -i gameday_workflow_db psql -U gameday_user -d postgres <<EOF
-- データベースが存在しない場合のみ作成
SELECT 'CREATE DATABASE gameday_workflow_application'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gameday_workflow_application')\gexec
EOF

if [ $? -eq 0 ]; then
    echo "✓ gameday_workflow_applicationデータベースの作成が完了しました"
else
    echo "✗ データベースの作成に失敗しました"
    exit 1
fi

