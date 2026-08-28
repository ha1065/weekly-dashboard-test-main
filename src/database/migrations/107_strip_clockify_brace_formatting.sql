-- Migration 107: Strip Clockify brace formatting from base tables
-- 
-- Problem: Clockify DROPDOWN custom fields return values wrapped in braces: {Bravo}, {"Free Agent"}
-- The Python import layer now strips these at ingest, but older rows still have braced values.
-- This migration cleans all base tables so raw data matches what views already produce.
--
-- Idempotent: safe to run multiple times (REPLACE on clean data is a no-op).
-- Rollback: see docs/migration-107-rollback-instructions.md

-- ============================================================================
-- 1. clockify_users (small table, ~70 rows)
-- ============================================================================
UPDATE clockify_users
SET pod_assignment = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE pod_assignment LIKE '{%' OR pod_assignment LIKE '%}' OR pod_assignment LIKE '%"%' OR pod_assignment LIKE '%\%';

UPDATE clockify_users
SET practice_alignment = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(practice_alignment, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE practice_alignment LIKE '{%' OR practice_alignment LIKE '%}' OR practice_alignment LIKE '%"%' OR practice_alignment LIKE '%\%';

UPDATE clockify_users
SET skill_area = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(skill_area, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE skill_area LIKE '{%' OR skill_area LIKE '%}' OR skill_area LIKE '%"%' OR skill_area LIKE '%\%';

UPDATE clockify_users
SET location = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(location, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE location LIKE '{%' OR location LIKE '%}' OR location LIKE '%"%' OR location LIKE '%\%';

UPDATE clockify_users
SET employment_designation = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(employment_designation, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE employment_designation LIKE '{%' OR employment_designation LIKE '%}' OR employment_designation LIKE '%"%' OR employment_designation LIKE '%\%';

-- ============================================================================
-- 2. clockify_projects (~200 rows)
-- ============================================================================
UPDATE clockify_projects
SET pod_assignment = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE pod_assignment LIKE '{%' OR pod_assignment LIKE '%}' OR pod_assignment LIKE '%"%' OR pod_assignment LIKE '%\%';

UPDATE clockify_projects
SET project_type = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(project_type, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE project_type LIKE '{%' OR project_type LIKE '%}' OR project_type LIKE '%"%' OR project_type LIKE '%\%';

UPDATE clockify_projects
SET professional_services_type = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(professional_services_type, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE professional_services_type LIKE '{%' OR professional_services_type LIKE '%}' OR professional_services_type LIKE '%"%' OR professional_services_type LIKE '%\%';

UPDATE clockify_projects
SET professional_services_phase = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(professional_services_phase, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE professional_services_phase LIKE '{%' OR professional_services_phase LIKE '%}' OR professional_services_phase LIKE '%"%' OR professional_services_phase LIKE '%\%';

-- ============================================================================
-- 3. clockify_detailed_time_entries (~100k+ rows — largest table)
--    Only user-denormalized fields; these come from the user at import time.
-- ============================================================================
UPDATE clockify_detailed_time_entries
SET pod_assignment = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE pod_assignment LIKE '{%' OR pod_assignment LIKE '%}' OR pod_assignment LIKE '%"%' OR pod_assignment LIKE '%\%';

UPDATE clockify_detailed_time_entries
SET practice_alignment = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(practice_alignment, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE practice_alignment LIKE '{%' OR practice_alignment LIKE '%}' OR practice_alignment LIKE '%"%' OR practice_alignment LIKE '%\%';

UPDATE clockify_detailed_time_entries
SET skill_area = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(skill_area, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE skill_area LIKE '{%' OR skill_area LIKE '%}' OR skill_area LIKE '%"%' OR skill_area LIKE '%\%';

-- ============================================================================
-- 4. ps_project_mapping (small table, ~50 rows)
--    pod_assignment is populated from clockify_projects.pod_assignment during auto_populate_mappings
-- ============================================================================
UPDATE ps_project_mapping
SET pod_assignment = TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\', ''))
WHERE pod_assignment IS NOT NULL
  AND (pod_assignment LIKE '{%' OR pod_assignment LIKE '%}' OR pod_assignment LIKE '%"%' OR pod_assignment LIKE '%\%');
