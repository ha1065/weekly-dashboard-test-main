-- Migration 006: Add Jira integration tables (standalone)
-- These tables have no foreign keys to existing tables

-- Jira Projects
CREATE TABLE IF NOT EXISTS jira_projects (
    id SERIAL PRIMARY KEY,
    jira_project_id VARCHAR(50) UNIQUE NOT NULL,
    project_key VARCHAR(50) NOT NULL,
    project_name VARCHAR(255),
    lead_name VARCHAR(255),
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jira_projects_key ON jira_projects(project_key);

-- Jira Issues
CREATE TABLE IF NOT EXISTS jira_issues (
    id SERIAL PRIMARY KEY,
    jira_issue_id VARCHAR(50) UNIQUE NOT NULL,
    issue_key VARCHAR(50) NOT NULL,
    project_key VARCHAR(50) NOT NULL,
    summary VARCHAR(500),
    status VARCHAR(100),
    status_category VARCHAR(50),
    phase VARCHAR(100),
    priority VARCHAR(50),
    issue_type VARCHAR(100),
    assignee_name VARCHAR(255),
    client_name VARCHAR(255),
    created_date TIMESTAMP,
    updated_date TIMESTAMP,
    due_date DATE,
    week_start DATE,
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jira_issues_project_key ON jira_issues(project_key);
CREATE INDEX IF NOT EXISTS idx_jira_issues_status ON jira_issues(status);
CREATE INDEX IF NOT EXISTS idx_jira_issues_client ON jira_issues(client_name);
CREATE INDEX IF NOT EXISTS idx_jira_issues_updated ON jira_issues(updated_date);

-- Manual mapping table (managed via Streamlit)
CREATE TABLE IF NOT EXISTS jira_forecast_mapping (
    id SERIAL PRIMARY KEY,
    jira_project_key VARCHAR(50) NOT NULL,
    forecast_client_name VARCHAR(255) NOT NULL,
    forecast_project_name VARCHAR(255),
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(jira_project_key, forecast_client_name)
);

CREATE INDEX IF NOT EXISTS idx_jira_mapping_project ON jira_forecast_mapping(jira_project_key);
CREATE INDEX IF NOT EXISTS idx_jira_mapping_client ON jira_forecast_mapping(forecast_client_name);
