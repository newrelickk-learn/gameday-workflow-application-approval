-- Application & Approval Service用のテーブル初期化
-- gameday_workflow_applicationデータベースに接続して実行される

-- 既存のENUM型が存在する場合は削除（後方互換性のため）
DO $$ BEGIN
    DROP TYPE IF EXISTS application_status CASCADE;
END $$;

-- Applicationsテーブルの作成
CREATE TABLE IF NOT EXISTS applications (
    id VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    amount DOUBLE PRECISION,
    start_date DATE,
    end_date DATE,
    days INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    applicant_id VARCHAR NOT NULL,
    applicant_name VARCHAR,
    applicant_department VARCHAR,
    current_step INTEGER,
    total_steps INTEGER,
    next_approver_id VARCHAR,
    next_approver_name VARCHAR,
    next_approver_department VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_applications PRIMARY KEY (id)
);

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_applications_type ON applications (type);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);
CREATE INDEX IF NOT EXISTS idx_applications_applicant_id ON applications (applicant_id);

-- updated_atを自動更新するトリガー関数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- updated_at自動更新トリガーの作成
DROP TRIGGER IF EXISTS update_applications_updated_at ON applications;
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

