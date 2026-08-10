-- Assertion Rules テーブル初期化
-- プロモーション申請などのdescription検証ルールをDB設定化する（Strategy Pattern）
-- gameday_workflow_applicationデータベースに接続して実行される

CREATE TABLE IF NOT EXISTS assertion_rules (
    id VARCHAR NOT NULL,
    application_type VARCHAR NOT NULL,
    target_field VARCHAR NOT NULL,
    rule_type VARCHAR NOT NULL,
    config JSONB NOT NULL,
    error_message VARCHAR,
    "order" INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    company_id VARCHAR,
    CONSTRAINT pk_assertion_rules PRIMARY KEY (id)
);

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_assertion_rules_type_field ON assertion_rules (application_type, target_field);
CREATE INDEX IF NOT EXISTS idx_assertion_rules_company_id ON assertion_rules (company_id);

-- シードデータ:
-- プロモーション申請のdescriptionは「現在の等級->昇進後の等級」（半角の "->" ）で
-- 記載するルール。company_id=NULLの共通デフォルト行は用意せず、各チーム（company_id 1〜50、
-- gameday-workflow-user / workflow-notification のシード規模に合わせる）が最初から
-- 個別のルール行を持つ運用にする。
-- id は company_id から機械的に導出できる決定的な文字列にしている
-- （例: company_id=5 -> "assertion_rule_promotion_description_5"）ため、
-- チームは自分のcompany_idから直接 PATCH /admin/assertion-rules/{id} を叩ける。
INSERT INTO assertion_rules (id, application_type, target_field, rule_type, config, error_message, "order", is_active, company_id)
SELECT
    'assertion_rule_promotion_description_' || company_id::text,
    'promotion',
    'description',
    'regex_pattern',
    '{"pattern": "[A-Za-z]\\d+\\s*->\\s*[A-Za-z]\\d+"}'::jsonb,
    'descriptionは「現在の等級->昇進後の等級」の形式（半角ハイフンと大なり記号）で入力してください（例: L3->L4）',
    1,
    true,
    company_id::text
FROM generate_series(1, 50) AS company_id
ON CONFLICT (id) DO NOTHING;
