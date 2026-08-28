-- Migration 095: Create forecast_config table
-- Stores configurable weights and parameters for the resource forecast model.
-- Replaces the mismatched capacity_model_config/forecast_config split.
-- Maintained via the Streamlit Admin > Forecast Config editor.

CREATE TABLE IF NOT EXISTS forecast_config (
    key         VARCHAR(100) PRIMARY KEY,
    value       NUMERIC(10,4) NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO forecast_config (key, value, description) VALUES
    ('weight_historical_hours',      0.50, 'Weight for Clockify actuals signal in blended forecast (0-1)'),
    ('weight_jira_velocity',         0.30, 'Weight for Jira ticket burn rate signal in blended forecast (0-1)'),
    ('weight_pm_forecast',           0.20, 'Weight for PM-uploaded forecast in blended forecast (0-1)'),
    ('seasonal_correction_enabled',  1,    '1 = apply seasonal factors, 0 = disabled'),
    ('decay_start_weeks',            2.0,  'Weeks before est. completion when forecast hours begin decaying'),
    ('lookback_weeks_default',       8,    'Default historical lookback window in weeks'),
    ('lookback_weeks_min_data',      4,    'Minimum lookback window when data is sparse')
ON CONFLICT (key) DO NOTHING;
