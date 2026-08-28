-- Migration 017: Add forecast history/versioning table
-- Archives previous forecast snapshots before each new import
-- so users can track how forecasts change over time.

CREATE TABLE IF NOT EXISTS ps_resource_forecast_history (
    history_id SERIAL PRIMARY KEY,
    forecast_id INTEGER,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    clockify_user_id VARCHAR(50),
    user_name VARCHAR(255) NOT NULL,
    location VARCHAR(50),
    project_name VARCHAR(255),
    clockify_project_id VARCHAR(50),
    client_name VARCHAR(255) NOT NULL,
    project_type VARCHAR(100),
    pm_name VARCHAR(255),
    stage VARCHAR(100),
    practice_area VARCHAR(100),
    forecasted_hours FLOAT NOT NULL DEFAULT 0,
    actual_hours FLOAT DEFAULT 0,
    comments TEXT,
    created_by VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    snapshot_id VARCHAR(50) NOT NULL,
    archived_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forecast_history_snapshot
    ON ps_resource_forecast_history(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_forecast_history_week
    ON ps_resource_forecast_history(week_start_date);
CREATE INDEX IF NOT EXISTS idx_forecast_history_archived_at
    ON ps_resource_forecast_history(archived_at);
