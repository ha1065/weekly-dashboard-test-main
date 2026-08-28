-- Migration 012: (One-time cleanup, now a no-op)
-- Originally cleared all forecast data for a fresh start.
-- Converted to no-op to prevent data loss on re-run.
SELECT 1;
