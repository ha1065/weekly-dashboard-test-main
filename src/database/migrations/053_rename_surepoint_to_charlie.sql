-- Deactivate SurePoint (renamed to Charlie)
UPDATE mc_pods SET is_active = FALSE WHERE pod_name = 'SurePoint';
-- Ensure Charlie exists and is active
INSERT INTO mc_pods (pod_name, is_active)
VALUES ('Charlie', TRUE)
ON CONFLICT (pod_name) DO UPDATE SET is_active = TRUE;
