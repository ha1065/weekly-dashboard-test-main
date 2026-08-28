-- Migration 060: Resource Capacity Forecast table
-- Stores 4 weeks actuals + 12 weeks forecasted hours per person/project
-- Populated by Lambda mode: forecast_resources

CREATE TABLE IF NOT EXISTS ps_resource_forecast_v2 (
    id SERIAL PRIMARY KEY,
    clockify_user_id VARCHAR(100) NOT NULL,
    user_name VARCHAR(200) NOT NULL,
    pod_assignment VARCHAR(200),
    practice_alignment VARCHAR(200),
    cloudelligent_title VARCHAR(200),
    skill_area VARCHAR(200),
    client_name VARCHAR(200) NOT NULL,
    project_name VARCHAR(200) NOT NULL,
    project_type VARCHAR(100),
    week_start DATE NOT NULL,
    is_actual BOOLEAN NOT NULL DEFAULT FALSE,
    hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    allocation_pct NUMERIC(5,2),
    remaining_sow_hours NUMERIC(10,2),
    estimated_completion DATE,
    weekly_capacity NUMERIC(5,2),
    capacity_available NUMERIC(10,2),
    generated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clockify_user_id, client_name, project_name, week_start)
);

CREATE INDEX IF NOT EXISTS idx_forecast_v2_user ON ps_resource_forecast_v2(clockify_user_id);
CREATE INDEX IF NOT EXISTS idx_forecast_v2_week ON ps_resource_forecast_v2(week_start);
CREATE INDEX IF NOT EXISTS idx_forecast_v2_project ON ps_resource_forecast_v2(client_name, project_name);

CREATE OR REPLACE VIEW vw_resource_capacity_plan AS
SELECT
    user_name, clockify_user_id, pod_assignment, practice_alignment,
    cloudelligent_title, skill_area, client_name, project_name, project_type,
    week_start, is_actual, hours, allocation_pct, remaining_sow_hours,
    estimated_completion, weekly_capacity, capacity_available,
    CASE WHEN is_actual THEN 'Actual' ELSE 'Forecast' END AS data_type,
    TO_CHAR(week_start, 'Mon DD') AS week_label
FROM ps_resource_forecast_v2
ORDER BY user_name, client_name, project_name, week_start;
