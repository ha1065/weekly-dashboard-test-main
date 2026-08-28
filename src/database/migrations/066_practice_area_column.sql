-- Migration 066: Add practice_area enum column to clockify_users
-- Valid values: 'PS', 'MC', 'Both', 'Internal', 'Exempt', NULL
-- NULL is treated as 'Internal' in all dashboard queries.
-- HUMAN REVIEW REQUIRED: Verify backfill output before deploying Lambda 3.3d.

ALTER TABLE clockify_users
    ADD COLUMN IF NOT EXISTS practice_area VARCHAR(20)
    CHECK (practice_area IN ('PS', 'MC', 'Both', 'Internal', 'Exempt', 'MIT'));

-- Best-effort backfill from practice_alignment free-text field.
-- Map known patterns; leave NULL for unrecognized values (human must correct).
UPDATE clockify_users SET practice_area = CASE
    WHEN practice_alignment ILIKE '%Professional Services%' OR practice_alignment ILIKE '%PS%' THEN 'PS'
    WHEN practice_alignment ILIKE '%Managed Cloud%' OR practice_alignment ILIKE '%MC%' THEN 'MC'
    WHEN practice_alignment ILIKE '%Internal%' OR practice_alignment ILIKE '%Admin%' THEN 'Internal'
    WHEN practice_alignment ILIKE '%Exempt%' THEN 'Exempt'
    ELSE NULL
END
WHERE practice_area IS NULL;
