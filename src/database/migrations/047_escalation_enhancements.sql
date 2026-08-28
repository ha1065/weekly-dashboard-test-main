-- Migration 047: Add description and status-change tracking to escalations

ALTER TABLE escalations
    ADD COLUMN IF NOT EXISTS description       TEXT,
    ADD COLUMN IF NOT EXISTS previous_status   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMP;

COMMENT ON COLUMN escalations.description       IS 'Jira issue description (plain text)';
COMMENT ON COLUMN escalations.previous_status   IS 'Status value from the previous sync';
COMMENT ON COLUMN escalations.status_changed_at IS 'Timestamp when status last changed';
