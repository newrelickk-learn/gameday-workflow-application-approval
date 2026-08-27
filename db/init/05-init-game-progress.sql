
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

CREATE INDEX IF NOT EXISTS idx_game_progress_company_active ON game_progress (company_id, is_active);

DROP TRIGGER IF EXISTS update_game_progress_updated_at ON game_progress;
CREATE TRIGGER update_game_progress_updated_at
    BEFORE UPDATE ON game_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

