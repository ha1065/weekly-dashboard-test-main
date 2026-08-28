-- Migration 002: MC V2 Audit Report tables
-- Creates two tables to store the Managed Services V2 Audit results
-- (status-as-of-week_start progress report per customer, by phase)

CREATE TABLE IF NOT EXISTS mc_v2_audit_by_customer (
    id                   SERIAL PRIMARY KEY,
    week_start           DATE        NOT NULL,
    customer_name        VARCHAR(255) NOT NULL,
    jira_project_key     VARCHAR(50),
    total_phases         INTEGER,
    completed_phases     INTEGER,
    overall_completion_pct NUMERIC(5,1),
    executive_summary    TEXT,
    analyzed_at          TIMESTAMP   DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_mc_v2_audit_customer_week
    ON mc_v2_audit_by_customer (week_start, customer_name);

CREATE TABLE IF NOT EXISTS mc_v2_audit_by_phase (
    id                   SERIAL PRIMARY KEY,
    week_start           DATE        NOT NULL,
    customer_name        VARCHAR(255) NOT NULL,
    jira_project_key     VARCHAR(50),
    phase_name           VARCHAR(255) NOT NULL,
    phase_order          INTEGER,
    total_items          INTEGER,
    done_items           INTEGER,
    in_progress_items    INTEGER,
    todo_items           INTEGER,
    completion_pct       NUMERIC(5,1),
    done_summary         TEXT,
    remaining_summary    TEXT,
    analyzed_at          TIMESTAMP   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_mc_v2_audit_phase_week
    ON mc_v2_audit_by_phase (week_start, customer_name);
