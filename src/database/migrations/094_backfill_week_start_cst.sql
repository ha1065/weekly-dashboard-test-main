-- Migration 065: Backfill entry_date and week_start using CST (America/Chicago) instead of UTC
-- Fixes rows where late-night CST entries were bucketed into the wrong week due to UTC date rollover.

UPDATE clockify_detailed_time_entries
SET
    entry_date = (start_time AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago')::DATE,
    week_start = DATE_TRUNC('week', (start_time AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago'))::DATE
WHERE
    start_time IS NOT NULL
    AND start_time::DATE != (start_time AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago')::DATE;
