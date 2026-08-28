-- Migration 043: Track reasons for missing time submissions per user per week
CREATE TABLE IF NOT EXISTS missing_time_reasons (
    id               SERIAL PRIMARY KEY,
    clockify_user_id VARCHAR(50)  NOT NULL,
    user_name        VARCHAR(255) NOT NULL,
    week_start       DATE         NOT NULL,
    reason           VARCHAR(100),   -- On Leave, Sick, Holiday, Late Submission, etc.
    notes            TEXT,
    recorded_by      VARCHAR(255),
    recorded_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (clockify_user_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_mtr_user_week ON missing_time_reasons(clockify_user_id, week_start);
CREATE INDEX IF NOT EXISTS idx_mtr_week      ON missing_time_reasons(week_start);
