-- Migration 015: Grant SELECT permissions to all users
-- Ensures QuickSight data source user can read all tables and views

GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
GRANT USAGE ON SCHEMA public TO PUBLIC;
