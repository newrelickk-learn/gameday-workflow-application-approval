
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

CREATE INDEX IF NOT EXISTS idx_assertion_rules_type_field ON assertion_rules (application_type, target_field);
CREATE INDEX IF NOT EXISTS idx_assertion_rules_company_id ON assertion_rules (company_id);

INSERT INTO assertion_rules (id, application_type, target_field, rule_type, config, error_message, "order", is_active, company_id)
SELECT
    'assertion_rule_promotion_description_' || company_id::text,
    'promotion',
    'description',
    'regex_pattern',
    '{"pattern": "[A-Za-z]\\d+\\s*->\\s*[A-Za-z]\\d+"}'::jsonb,
    'バリデーションルール assertion_rule_promotion_description を満たしていません（pattern mismatch）',
    1,
    true,
    company_id::text
FROM generate_series(1::integer, 50::integer) AS company_id
ON CONFLICT (id) DO NOTHING;
