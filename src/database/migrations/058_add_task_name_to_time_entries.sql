-- Migration 058: Add task_name column to clockify_detailed_time_entries
ALTER TABLE clockify_detailed_time_entries
    ADD COLUMN IF NOT EXISTS task_name VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_time_entries_task_name
    ON clockify_detailed_time_entries(task_name)
    WHERE task_name IS NOT NULL;
