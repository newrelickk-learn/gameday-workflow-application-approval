#!/bin/bash

# データベースのENUM型を削除してVARCHAR型に変更するスクリプト
# PostgreSQLコンテナが起動していることを前提とします

echo "applicationsテーブルのstatusカラムをVARCHAR型に変更中..."

docker exec -i gameday_workflow_db psql -U gameday_user -d gameday_workflow_application <<EOF
-- テーブルが存在する場合、ENUM型を削除してVARCHAR型に変更
DO \$\$
BEGIN
    -- テーブルが存在する場合
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'applications') THEN
        -- statusカラムをVARCHAR型に変更
        ALTER TABLE applications ALTER COLUMN status TYPE VARCHAR(20);
        
        -- ENUM型が存在する場合は削除（エラーが発生しても続行）
        DROP TYPE IF EXISTS application_status CASCADE;
        
        RAISE NOTICE 'statusカラムをVARCHAR型に変更しました';
    ELSE
        RAISE NOTICE 'applicationsテーブルが存在しません';
    END IF;
END
\$\$;
EOF

if [ $? -eq 0 ]; then
    echo "✓ statusカラムの型変更が完了しました"
else
    echo "✗ 型変更に失敗しました"
    exit 1
fi

