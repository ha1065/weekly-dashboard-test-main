-- Migration 024: Add MC customer name mappings for pod lookup
-- Maps ps_project_status client names to their Clockify project client names
-- where the names don't match by substring (abbreviations / complete renames)
INSERT INTO ps_project_mapping (ps_client_name, clockify_client_name, is_active, created_at)
VALUES
    ('NVLSP',      'National Veterans Legal Service', true, NOW()),
    ('Utah Real',  'URE',                             true, NOW())
ON CONFLICT (ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name) DO NOTHING;
