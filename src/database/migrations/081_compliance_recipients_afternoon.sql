-- Migration 081: Add afternoon and all as valid report_run values
-- Keeps 'both' as legacy alias for backward compatibility

DO $$
BEGIN
    -- Drop existing check constraint if present
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'compliance_report_recipients'
          AND constraint_type = 'CHECK'
          AND constraint_name = 'compliance_report_recipients_report_run_check'
    ) THEN
        ALTER TABLE compliance_report_recipients
            DROP CONSTRAINT compliance_report_recipients_report_run_check;
    END IF;

    -- Add updated constraint with afternoon and all
    ALTER TABLE compliance_report_recipients
        ADD CONSTRAINT compliance_report_recipients_report_run_check
        CHECK (report_run IN ('morning', 'noon', 'afternoon', 'both', 'all'));
END $$;
