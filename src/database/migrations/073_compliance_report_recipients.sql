-- Migration 073: compliance_report_recipients
-- Stores email recipients for the Monday morning non-compliance report.
-- report_run: 'morning' = 9am run only, 'both' = 9am + noon run
CREATE TABLE IF NOT EXISTS compliance_report_recipients (
    id           SERIAL PRIMARY KEY,
    email        VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    report_run   VARCHAR(20)  NOT NULL DEFAULT 'morning' CHECK (report_run IN ('morning', 'both')),
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  DEFAULT NOW()
);
