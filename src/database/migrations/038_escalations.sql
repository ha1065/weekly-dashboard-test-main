-- Migration 038: Create escalations table for ES Jira board data
CREATE TABLE IF NOT EXISTS escalations (
    id                  SERIAL PRIMARY KEY,
    jira_issue_id       VARCHAR(50) UNIQUE NOT NULL,
    issue_key           VARCHAR(50) NOT NULL,

    -- Customer (from epic)
    customer_name       VARCHAR(255),
    epic_key            VARCHAR(50),
    epic_summary        VARCHAR(500),

    -- Issue fields
    summary             VARCHAR(500),
    status              VARCHAR(100),
    status_category     VARCHAR(50),   -- 'To Do', 'In Progress', 'Done'
    priority            VARCHAR(50),
    assignee_name       VARCHAR(255),
    reporter_name       VARCHAR(255),

    -- Dates
    created_date        TIMESTAMP,
    updated_date        TIMESTAMP,
    resolution_date     TIMESTAMP,

    -- Computed
    days_open           INTEGER,       -- NULL if resolved; else days since created
    days_to_resolve     INTEGER,       -- NULL if still open

    -- Metadata
    synced_at           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_escalations_customer ON escalations(customer_name);
CREATE INDEX IF NOT EXISTS idx_escalations_status   ON escalations(status_category);
CREATE INDEX IF NOT EXISTS idx_escalations_created  ON escalations(created_date);
