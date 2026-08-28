"""AI Analysis handler module.

Modes handled:
  - analyze_project_health  – Bedrock AI analysis of PS + MC Jira vs Clockify data
  - mc_v2_audit             – MC V2 Managed Services methodology progress report
  - mc_v2_customers         – quick customer pod check (no analysis)
  - analyze_forecast        – Bedrock AI analysis of forecast vs actuals
"""

import json
from typing import Any


def analyze_project_health(event: dict, context: Any, secrets: dict) -> dict:
    """Run AI Jira vs Clockify project health analysis.

    event keys:
      week_start  ISO date str | None
      weeks_back  int (default 1)
    """
    # Heavy imports inside function — secrets must already be in os.environ
    from src.integrations.analyze_project_health import run_analysis as run_ph_analysis
    from src.handlers.quicksight import refresh_quicksight_datasets

    from datetime import date as _date
    week_start_str = event.get('week_start')
    if week_start_str:
        week_start_ph = _date.fromisoformat(week_start_str)
        summary = run_ph_analysis(week_start=week_start_ph)
    else:
        weeks_back_ph = event.get('weeks_back', 1)
        summary = run_ph_analysis(weeks_back=weeks_back_ph)

    # Refresh the four AI analysis QuickSight datasets
    ai_dataset_ids = [
        'ai-ps-analysis-by-user',
        'ai-ps-analysis-by-project',
        'ai-mc-analysis-by-user',
        'ai-mc-analysis-by-project',
    ]
    refresh_quicksight_datasets(ai_dataset_ids)

    return {
        'statusCode': 200,
        'body': json.dumps({'analysis_summary': summary}, default=str)
    }


def mc_v2_audit(event: dict, context: Any, secrets: dict) -> dict:
    """Run MC V2 Managed Services methodology progress report.

    event keys:
      week_start  ISO date str | None  (defaults to last Monday)
    """
    # Heavy imports inside function
    from src.integrations.mc_v2_audit import run_mc_v2_audit
    from src.handlers.quicksight import refresh_quicksight_datasets
    from datetime import date as _date, timedelta as _timedelta

    week_start_str = event.get('week_start')
    if week_start_str:
        ws = _date.fromisoformat(week_start_str)
    else:
        today = _date.today()
        ws = today - _timedelta(days=today.weekday() + 7)  # last Monday

    audit_summary = run_mc_v2_audit(ws)
    refresh_quicksight_datasets(['mc-v2-audit-by-customer', 'mc-v2-audit-by-phase', 'mc-v2-audit-grid'])

    return {
        'statusCode': 200,
        'body': json.dumps({'audit_summary': audit_summary}, default=str)
    }


def mc_v2_customers(event: dict, context: Any, secrets: dict) -> dict:
    """Quick customer pod check — returns pod assignments without running full analysis."""
    # Heavy imports inside function
    from src.integrations.mc_v2_audit import _get_mc_customers

    customers = _get_mc_customers()
    return {
        'statusCode': 200,
        'body': json.dumps({'customers': customers}, default=str)
    }


def analyze_forecast(event: dict, context: Any, secrets: dict) -> dict:
    """Run Bedrock AI analysis of forecast vs actuals.

    event keys:
      week_start  ISO date str | None  (defaults to this Monday)
      weeks_back  int (default 4)
    """
    # Heavy imports inside function
    from src.integrations.analyze_forecast import run_forecast_analysis
    from src.handlers.quicksight import refresh_quicksight_datasets
    from datetime import date as _date, timedelta as _timedelta

    week_start_str = event.get('week_start')
    weeks_back = int(event.get('weeks_back', 4))
    if week_start_str:
        ws = _date.fromisoformat(week_start_str)
    else:
        today = _date.today()
        ws = today - _timedelta(days=today.weekday())  # this Monday

    summary = run_forecast_analysis(ws, weeks_back=weeks_back)
    refresh_quicksight_datasets(['ai-forecast-analysis', 'ai-forecast-summary', 'pm-forecast-accuracy'])

    return {
        'statusCode': 200,
        'body': json.dumps({'summary': summary}, default=str)
    }
