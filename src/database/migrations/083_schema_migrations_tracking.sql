-- Migration 083: Schema migrations tracking table
-- Prevents replay of already-applied migrations on Streamlit ECS restart.
-- shared.py:apply_pending_migrations() checks this table before executing each file.
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
