-- Game Progress テーブル初期化
-- GameDay演習の仮想時間進行（virtual_date_offset_days）を管理する
-- gameday_workflow_applicationデータベースに接続して実行される

CREATE TABLE IF NOT EXISTS game_progress (
    id VARCHAR NOT NULL,
    company_id VARCHAR NOT NULL,
    virtual_date_offset_days INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_game_progress PRIMARY KEY (id)
);

-- インデックスの作成
-- 「現在の進行状態」は常に WHERE company_id = ? AND is_active = true の1行として取得する
CREATE INDEX IF NOT EXISTS idx_game_progress_company_active ON game_progress (company_id, is_active);

-- updated_at自動更新トリガーの作成（03-init-application.sqlで定義済みの関数を再利用）
DROP TRIGGER IF EXISTS update_game_progress_updated_at ON game_progress;
CREATE TRIGGER update_game_progress_updated_at
    BEFORE UPDATE ON game_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 演習開始時の初期化は運営がチームごとに行う（company_id, virtual_date_offset_days = -365 で1行作成）。
-- 本ファイルではテーブル定義のみを用意し、シードデータは投入しない。
