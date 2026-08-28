-- Migration 072: Add nb_subcategory field to ps_project_mapping
-- Used by Tab 9 NB Analysis for explicit NB sub-category labeling.
-- Valid values: 'Presales', 'Training', 'Internal Initiatives', 'Overhead', NULL
-- FR ref: OQ-007

ALTER TABLE ps_project_mapping
    ADD COLUMN IF NOT EXISTS nb_subcategory VARCHAR(50);
