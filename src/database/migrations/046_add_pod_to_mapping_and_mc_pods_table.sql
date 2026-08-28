-- Migration 046: Add pod_assignment to ps_project_mapping and create mc_pods table
-- Allows MC projects to be assigned to a pod directly in the Project Mapping UI.

-- Add pod column to existing mapping table
ALTER TABLE ps_project_mapping
    ADD COLUMN IF NOT EXISTS pod_assignment VARCHAR(100);

-- Managed Cloud pod registry (user-managed list)
CREATE TABLE IF NOT EXISTS mc_pods (
    id          SERIAL PRIMARY KEY,
    pod_name    VARCHAR(100) NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed the four initial pods
INSERT INTO mc_pods (pod_name) VALUES
    ('Alpha'),
    ('Bravo'),
    ('A2Z'),
    ('SurePoint')
ON CONFLICT (pod_name) DO NOTHING;
