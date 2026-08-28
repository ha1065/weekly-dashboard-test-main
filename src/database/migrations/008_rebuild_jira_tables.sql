-- Migration 008: Create Jira/PS tables with comprehensive schema
-- Uses IF NOT EXISTS so this migration is safely re-runnable without data loss

-- Drop old tables that were replaced by ps_project_status (no longer used)
DROP TABLE IF EXISTS jira_forecast_mapping CASCADE;
DROP TABLE IF EXISTS jira_issues CASCADE;

-- Jira Projects table (metadata about Jira projects)
CREATE TABLE IF NOT EXISTS jira_projects (
    id SERIAL PRIMARY KEY,
    jira_project_id VARCHAR(50) UNIQUE NOT NULL,
    project_key VARCHAR(50) NOT NULL,
    project_name VARCHAR(255),
    lead_name VARCHAR(255),
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jira_projects_key ON jira_projects(project_key);

-- Professional Services Project Status table (from Jira Service Desk)
CREATE TABLE IF NOT EXISTS ps_project_status (
    id SERIAL PRIMARY KEY,
    jira_issue_id VARCHAR(50) UNIQUE NOT NULL,
    issue_key VARCHAR(50) NOT NULL,
    jira_project_key VARCHAR(50) NOT NULL,

    -- Parsed from summary field: "ClientName - ProjectDescription" or "ClientName ProjectType"
    client_name VARCHAR(255),
    project_name VARCHAR(255),
    summary VARCHAR(500),

    -- Standard Jira fields
    status VARCHAR(100),              -- Current stage: DISCOVER AND ALIGN, BUILD AND IMPLEMENT, etc.
    status_category VARCHAR(50),
    priority VARCHAR(50),
    issue_type VARCHAR(100),
    assignee_name VARCHAR(255),
    created_date TIMESTAMP,
    updated_date TIMESTAMP,
    due_date DATE,

    -- Project classification
    project_type VARCHAR(100),           -- customfield_11880: Migration, AppDev, etc.

    -- Team members
    project_manager VARCHAR(255),        -- customfield_11781
    solution_architect VARCHAR(255),     -- customfield_11533
    engineer VARCHAR(255),               -- customfield_11532
    account_executive VARCHAR(255),      -- customfield_11534
    csm VARCHAR(255),                    -- customfield_11735: Customer Success Manager

    -- Health status fields (Red/Yellow/Green)
    current_health VARCHAR(100),         -- customfield_11263: Current Project Health
    health_overall VARCHAR(50),          -- customfield_11271: Health:
    health_budget VARCHAR(50),           -- customfield_11420: Budget:
    health_scope VARCHAR(50),            -- customfield_11454: Scope:
    health_schedule VARCHAR(50),         -- customfield_11455: Schedule:
    schedule_score VARCHAR(50),          -- customfield_11569: On Time/Late
    escalation TEXT,                     -- customfield_11421: Escalation
    impact TEXT,                         -- customfield_11268: Impact:
    risks_blockers TEXT,                 -- customfield_11489: Risks/Blockers

    -- Budget fields
    budget_hours DECIMAL(10,2),          -- customfield_11780: SOW Hours

    -- Date fields - Planning
    planned_start DATE,                  -- customfield_10049
    planned_end DATE,                    -- customfield_10050
    planned_kickoff DATE,                -- customfield_11527: Planned Kick-off Date
    sow_signing_date DATE,               -- customfield_11531: SOW Signing Date
    expected_completion DATE,            -- customfield_11567: Expected Completion Date
    revised_completion DATE,             -- customfield_11568: Revise Expected Completion Date
    resource_assignment_date DATE,       -- customfield_11914: Resource Assignment Date

    -- Date fields - Actual completion by phase
    actual_kickoff DATE,                 -- customfield_11913: Actual Kick off Date
    actual_completion DATE,              -- customfield_11636: Actual Completion Date
    internal_prep_completion DATE,       -- customfield_11522
    discover_align_completion DATE,      -- customfield_11523
    design_review_completion DATE,       -- customfield_11524
    build_implement_completion DATE,     -- customfield_11525
    launch_enable_completion DATE,       -- customfield_11526

    -- Narrative fields
    project_summary TEXT,                -- customfield_11267: Summary:
    what_we_did TEXT,                    -- customfield_11265
    what_we_will_do_next TEXT,           -- customfield_11266
    mitigation_plan TEXT,                -- customfield_11269
    slippages TEXT,                      -- customfield_11264: Planned vs Actual

    -- Links
    sow_link TEXT,                       -- customfield_10846

    -- Metadata
    week_start DATE,                     -- Monday of the week when issue was last updated
    synced_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ps_project_status_jira_key ON ps_project_status(jira_project_key);
CREATE INDEX IF NOT EXISTS idx_ps_project_status_client ON ps_project_status(client_name);
CREATE INDEX IF NOT EXISTS idx_ps_project_status_status ON ps_project_status(status);
CREATE INDEX IF NOT EXISTS idx_ps_project_status_pm ON ps_project_status(project_manager);
CREATE INDEX IF NOT EXISTS idx_ps_project_status_health ON ps_project_status(health_overall);
CREATE INDEX IF NOT EXISTS idx_ps_project_status_updated ON ps_project_status(updated_date);
CREATE INDEX IF NOT EXISTS idx_ps_project_status_type ON ps_project_status(project_type);
