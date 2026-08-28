-- Migration 054: MC ticket activity snapshot
-- Captures weekly Jira ticket activity per MC customer from the CST board.
-- Written at the end of each jira_import run.
CREATE TABLE IF NOT EXISTS mc_ticket_activity_snapshot (
    id              SERIAL PRIMARY KEY,
    week_start      DATE NOT NULL,
    customer_name   VARCHAR(255) NOT NULL,
    jira_project_key VARCHAR(50),
    total_issues    INTEGER DEFAULT 0,
    open_issues     INTEGER DEFAULT 0,
    in_progress_issues INTEGER DEFAULT 0,
    done_issues     INTEGER DEFAULT 0,
    updated_this_week INTEGER DEFAULT 0,  -- issues with updated_date in this week
    health_overall  VARCHAR(50),          -- PM-set health from CST board
    synced_at       TIMESTAMP DEFAULT NOW(),
    UNIQUE (week_start, customer_name)
);

CREATE INDEX IF NOT EXISTS idx_mc_ticket_week ON mc_ticket_activity_snapshot(week_start);
CREATE INDEX IF NOT EXISTS idx_mc_ticket_customer ON mc_ticket_activity_snapshot(customer_name);
