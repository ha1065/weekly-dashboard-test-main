-- Migration 030: Consolidate MC V2 audit phase columns
-- - Add narrative (replaces done_summary + remaining_summary)
-- - phase_name will now store "Phase Name (X%)" — completion_pct kept for numeric filtering
-- Drop dependent view first so we can alter the table
DROP VIEW IF EXISTS vw_mc_v2_audit_grid;

ALTER TABLE mc_v2_audit_by_phase
  ADD COLUMN IF NOT EXISTS narrative TEXT;

-- Backfill narrative from existing data (will be regenerated on next audit run)
UPDATE mc_v2_audit_by_phase
   SET narrative = TRIM(
         COALESCE('Completed: ' || done_summary, '') ||
         CASE WHEN done_summary IS NOT NULL AND remaining_summary IS NOT NULL THEN ' ' ELSE '' END ||
         COALESCE('Remaining: ' || remaining_summary, '')
       )
 WHERE narrative IS NULL;

ALTER TABLE mc_v2_audit_by_phase
  DROP COLUMN IF EXISTS done_summary,
  DROP COLUMN IF EXISTS remaining_summary;
