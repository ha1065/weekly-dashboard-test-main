-- Migration 014: Create ps_project_mapping for PS-to-Clockify mapping
-- Uses IF NOT EXISTS so this migration is safely re-runnable without data loss

-- Drop old unused tables (replaced by ps_project_mapping)
DROP TABLE IF EXISTS jira_issues CASCADE;
DROP TABLE IF EXISTS jira_forecast_mapping CASCADE;

-- Create mapping table linking PS projects to Clockify clients/projects
CREATE TABLE IF NOT EXISTS ps_project_mapping (
    id SERIAL PRIMARY KEY,
    ps_client_name VARCHAR(255) NOT NULL,
    ps_project_name VARCHAR(255),
    clockify_client_name VARCHAR(255) NOT NULL,
    clockify_project_name VARCHAR(255),
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ps_client_name, clockify_client_name)
);

CREATE INDEX IF NOT EXISTS idx_ps_mapping_client ON ps_project_mapping(ps_client_name);
CREATE INDEX IF NOT EXISTS idx_ps_mapping_clockify ON ps_project_mapping(clockify_client_name);

-- Grant read access to all users (needed for QuickSight data source)
GRANT SELECT ON ps_project_mapping TO PUBLIC;
