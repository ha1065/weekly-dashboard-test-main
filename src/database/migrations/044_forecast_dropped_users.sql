-- Migration 044: Log forecast users dropped due to no Clockify match
CREATE TABLE IF NOT EXISTS forecast_dropped_users (
    id             SERIAL PRIMARY KEY,
    user_name      VARCHAR(255) NOT NULL,
    import_log_id  INTEGER,
    dropped_at     TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fdu_user_name  ON forecast_dropped_users(user_name);
CREATE INDEX IF NOT EXISTS idx_fdu_dropped_at ON forecast_dropped_users(dropped_at);
