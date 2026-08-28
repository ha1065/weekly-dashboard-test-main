-- Migration 100: Seed run-status email recipient
-- Uses existing 'all' report_run value (covers morning + noon + run_status queries)
-- Note: run_status is handled in the Lambda query by matching 'all' and 'both'

-- Seed chris.xenos as run_status recipient using 'all' (upsert — safe to re-run)
INSERT INTO compliance_report_recipients (email, display_name, report_run, is_active)
VALUES ('chris.xenos@cloudelligent.com', 'Chris Xenos', 'all', TRUE)
ON CONFLICT (email) DO UPDATE
    SET report_run = 'all',
        is_active  = TRUE,
        updated_at = NOW();
