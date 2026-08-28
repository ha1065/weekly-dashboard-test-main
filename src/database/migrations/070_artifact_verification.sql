-- Migration 070: artifact_verification table for MC V2 audit Confluence checks
-- Populated by mc_v2_audit.py Lambda (Confluence API verification step).
-- BLOCKED: Requires CONFLUENCE_API_TOKEN + CONFLUENCE_BASE_URL in Secrets Manager.

CREATE TABLE IF NOT EXISTS artifact_verification (
    id                   SERIAL PRIMARY KEY,
    jira_issue_id        VARCHAR(50) UNIQUE NOT NULL,
    artifact_present     BOOLEAN,
    artifact_url         TEXT,
    artifact_verified_at TIMESTAMPTZ,
    verified_by          VARCHAR(50),
    error_message        TEXT,
    synced_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_artifact_verification_issue
    ON artifact_verification (jira_issue_id);
