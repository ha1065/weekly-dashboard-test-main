-- Migration 022: Add pod_assignment to clockify_projects
ALTER TABLE clockify_projects ADD COLUMN IF NOT EXISTS pod_assignment VARCHAR(100);
