-- Migration 105: Add Non Bill Productive and Non Bill Non Productive custom fields
-- These are CHECKBOX fields on Clockify time entries (true/false).
-- They allow direct classification of time entries as NB Productive or NB Non-Productive
-- without relying on project_type lookups or ps_project_mapping fallback logic.

ALTER TABLE clockify_detailed_time_entries
    ADD COLUMN IF NOT EXISTS is_nb_productive BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_nb_non_productive BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN clockify_detailed_time_entries.is_nb_productive IS 'Clockify custom field "Non Bill Productive" checkbox value';
COMMENT ON COLUMN clockify_detailed_time_entries.is_nb_non_productive IS 'Clockify custom field "Non Bill Non Productive" checkbox value';
