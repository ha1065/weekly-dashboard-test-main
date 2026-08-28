-- Migration 027: Add category column to ps_project_mapping
-- Stores which tab the mapping was saved from ('PS' or 'MC')
-- NULL = applies to both (backwards compatible for existing rows)
ALTER TABLE ps_project_mapping
  ADD COLUMN IF NOT EXISTS category VARCHAR(10);
