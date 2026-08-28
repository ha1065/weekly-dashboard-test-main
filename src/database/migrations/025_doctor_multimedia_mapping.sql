-- Migration 025: Add Doctor -> Dr Multimedia clockify mapping for pod lookup
INSERT INTO ps_project_mapping (ps_client_name, clockify_client_name, is_active, created_at)
VALUES ('Doctor', 'Dr Multimedia', true, NOW())
ON CONFLICT (ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name) DO NOTHING;
