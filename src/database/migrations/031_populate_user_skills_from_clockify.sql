-- Migration 031: Populate user_skills from clockify_users.skill_area
-- Syncs skill_area custom field from Clockify into user_skills table.
-- Idempotent: deletes clockify_sync rows before re-inserting.

-- Remove previously synced rows so re-runs stay clean
DELETE FROM user_skills WHERE added_by = 'clockify_sync';

-- Insert one row per active user with a skill_area value.
-- skill_area is stored with Postgres array braces e.g. {DevOps} — strip them.
INSERT INTO user_skills (
    clockify_user_id,
    user_name,
    skill_category,
    skill_name,
    added_by,
    created_at,
    updated_at
)
SELECT
    clockify_user_id,
    name AS user_name,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(skill_area, '{', ''), '}', ''), '"', ''), '\', '')) AS skill_category,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(skill_area, '{', ''), '}', ''), '"', ''), '\', '')) AS skill_name,
    'clockify_sync'                  AS added_by,
    NOW()                            AS created_at,
    NOW()                            AS updated_at
FROM clockify_users
WHERE skill_area IS NOT NULL
  AND TRIM(skill_area) != ''
  AND TRIM(skill_area) != '{}'
ORDER BY name;
