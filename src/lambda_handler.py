"""AWS Lambda handler for scheduled Clockify imports.

This is the thin dispatcher entry point.  Business logic lives in the
src/handlers/ package.  The deployed Handler is:

    src.lambda_handler.lambda_handler

Dispatch table
--------------
Each mode maps to a handler function with the signature:

    def <mode>(event, context, secrets) -> dict

Modes not in the table (None, 'weekly', 'incremental', 'full') fall through
to the full pipeline orchestration in src.handlers.pipeline.run_pipeline.

Note: database imports are done lazily INSIDE each handler function to allow
secrets to be set into os.environ BEFORE src.database.config is imported.
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any

# ── Handler imports ──────────────────────────────────────────────────────────
# (module-level; the functions themselves do lazy heavy imports)
from src.handlers.common import get_secrets, set_environment_from_secrets, send_sns_notification
from src.handlers.pipeline import run_pipeline, snapshot_kpis, forecast_resources
from src.handlers.jira import jira_import, jira_fields
from src.handlers.quicksight import refresh_quicksight_only, create_quicksight_datasets
from src.handlers.ai_analysis import analyze_project_health, mc_v2_audit, mc_v2_customers, analyze_forecast
from src.handlers.escalations import run_escalations_import
from src.handlers.admin import apply_views, run_migration, run_query, run_query_master, fix_report_user, restore_forecasts
from src.handlers.diagnostics import (
    diagnose, diagnose_users, diagnose_contractors, diagnose_dates,
    diagnose_ps, diagnose_forecasts, diagnose_free_agents, diagnose_pod,
    diagnose_report_mapping, debug_secrets, debug_clockify,
)
from src.handlers.notifications import send_run_status_email, send_compliance_report

def _test_status_email(event: dict, context: Any, secrets: dict) -> dict:
    """Send a sample status email without running an import."""
    from datetime import date, timedelta
    from src.handlers.quicksight import get_all_dataset_ids

    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday() + 7)
    week_start = last_monday.date()
    week_end = week_start + timedelta(days=6)
    sample_summary = {
        'mode': 'weekly',
        'status': 'ERRORS',
        'run_date': today,
        'week_start': week_start,
        'week_end': week_end,
        'users_updated': 83,
        'projects_updated': 228,
        'time_entries_updated': 2919,
        'jira_updated': 350,
        'kpi_written': True,
        'kpi_week': str(week_end),
        'spice_triggered': len(get_all_dataset_ids()),
        'compliance_total': 70,
        'compliance_compliant': 64,
        'compliance_noncompliant': 6,
        'errors': [
            "AI analysis: Read timeout on Bedrock endpoint after 60s",
            "MC V2 Audit: Task timed out after 300 seconds",
            "quicksight:DescribeTheme — AccessDenied for resource arn:aws:quicksight:...",
            "SPICE Refresh: already in progress for dataset ai-forecast-summary",
        ],
    }
    send_run_status_email(sample_summary)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Test status email sent',
            'summary': {k: str(v) for k, v in sample_summary.items()}
        })
    }


# ── Dispatch table ───────────────────────────────────────────────────────────
# Maps mode string → handler callable (event, context, secrets) -> dict
MODE_DISPATCH: Dict[str, Any] = {
    # Admin / maintenance
    'apply_views':              apply_views,
    'run_migration':            run_migration,
    'run_query':                run_query,
    'run_query_master':         run_query_master,
    'fix_report_user':          fix_report_user,
    'restore_forecasts':        restore_forecasts,
    # Pipeline utilities
    'snapshot_kpis':            snapshot_kpis,
    'forecast_resources':       forecast_resources,
    # Jira
    'jira_import':              jira_import,
    'jira_fields':              jira_fields,
    # QuickSight
    'refresh_quicksight_only':       refresh_quicksight_only,
    'create_quicksight_datasets':    create_quicksight_datasets,
    # AI analysis
    'analyze_project_health':   analyze_project_health,
    'mc_v2_audit':              mc_v2_audit,
    'mc_v2_customers':          mc_v2_customers,
    'analyze_forecast':         analyze_forecast,
    # Escalations
    'run_escalations_import':   run_escalations_import,
    # Diagnostics
    'diagnose':                 diagnose,
    'diagnose_users':           diagnose_users,
    'diagnose_contractors':     diagnose_contractors,
    'diagnose_dates':           diagnose_dates,
    'diagnose_ps':              diagnose_ps,
    'diagnose_forecasts':       diagnose_forecasts,
    'diagnose_free_agents':     diagnose_free_agents,
    'diagnose_pod':             diagnose_pod,
    'diagnose_report_mapping':  diagnose_report_mapping,
    'debug_secrets':            debug_secrets,
    'debug_clockify':           debug_clockify,
    # Notifications
    'send_compliance_report':   send_compliance_report,
    # Test helper — sends a sample status email without running an import
    'test_status_email':        _test_status_email,
}

# ── Pipeline fall-through modes (no entry in dispatch table) ─────────────────
_PIPELINE_MODES = {None, 'weekly', 'incremental', 'full'}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler for Clockify data import.

    Args:
        event: Lambda event object with optional parameters:
            - mode: 'incremental', 'weekly', 'full', or any named mode
            - weeks_back: Number of weeks to import (for custom mode)
            - notify: Boolean to enable SNS notifications
            - refresh_quicksight: Boolean to trigger QuickSight refresh
            - quicksight_dataset_ids: List of dataset IDs to refresh
        context: Lambda context object

    Returns:
        Dictionary with status code and result message
    """
    print(f"Lambda invoked at {datetime.now().isoformat()}")
    print(f"Event: {json.dumps(event)}")

    mode = event.get('mode', 'incremental')
    notify = event.get('notify', False)
    notification_topic = os.environ.get('NOTIFICATION_TOPIC_ARN', '')

    try:
        # ── Secrets bootstrap (must happen before any DB import) ──────────────
        print("Retrieving secrets from Secrets Manager...")
        secrets = get_secrets()
        set_environment_from_secrets(secrets)
        print("Secrets loaded successfully")

        # ── Dispatch ──────────────────────────────────────────────────────────
        if mode in _PIPELINE_MODES:
            return run_pipeline(event, context, secrets)

        handler_fn = MODE_DISPATCH.get(mode)
        if handler_fn is None:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f"Unknown mode: {mode}"})
            }

        return handler_fn(event, context, secrets)

    except Exception as e:
        error_message = f"""
Weekly Reporting Import Failed

Environment: {os.environ.get('ENVIRONMENT', 'unknown')}
Mode: {mode}
Timestamp: {datetime.now().isoformat()}

Error: {str(e)}

Please check CloudWatch logs for details.
        """

        print(f"Import failed: {str(e)}")

        # Send error notification
        if notify and notification_topic:
            send_sns_notification(
                notification_topic,
                "❌ Weekly Reporting Import Failed",
                error_message
            )

        # Re-raise for Lambda to mark as failed
        raise


# ── Local testing ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Simulate Lambda event
    test_event = {
        'mode': 'incremental',
        'notify': False
    }

    class MockContext:
        def __init__(self):
            self.function_name = "test-function"
            self.memory_limit_in_mb = 512
            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
