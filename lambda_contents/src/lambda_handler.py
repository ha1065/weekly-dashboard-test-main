"""AWS Lambda handler for scheduled Clockify imports.

This module provides the Lambda handler that integrates with AWS services
for secure, automated data imports.
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any

# Note: Database imports are done lazily inside functions to allow
# secrets to be set before database config is loaded


def get_secrets() -> Dict[str, str]:
    """Retrieve secrets from AWS Secrets Manager."""
    secret_name = os.environ.get('SECRET_NAME')
    region_name = os.environ.get('AWS_REGION', 'us-east-1')

    # Create a Secrets Manager client
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error retrieving secrets: {e}")
        raise


def get_db_endpoint() -> str:
    """Get database endpoint from SSM Parameter Store."""
    parameter_name = os.environ.get('DB_ENDPOINT_PARAMETER')
    if not parameter_name:
        # Fallback to DB_HOST env var if parameter name not set
        return os.environ.get('DB_HOST', '')

    ssm = boto3.client('ssm')
    try:
        response = ssm.get_parameter(Name=parameter_name)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error retrieving DB endpoint from SSM: {e}")
        # Fallback to DB_HOST env var
        return os.environ.get('DB_HOST', '')


def set_environment_from_secrets(secrets: Dict[str, str]):
    """Set environment variables from secrets and build connection string."""
    # Get database info from environment variables and SSM
    db_host = get_db_endpoint()
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'weekly_reporting')
    db_user = os.environ.get('DB_USER', 'report_user')
    db_password = secrets.get('db_password', '')

    # Build connection string using pg8000 driver (pure Python, Lambda compatible)
    database_url = f"postgresql+pg8000://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    os.environ['DATABASE_URL'] = database_url
    os.environ['CLOCKIFY_API_KEY'] = secrets.get('clockify_api_key', '')
    os.environ['CLOCKIFY_WORKSPACE_ID'] = secrets.get('clockify_workspace_id', '')
    # Jira settings (optional)
    os.environ['JIRA_BASE_URL'] = secrets.get('jira_base_url', '')
    os.environ['JIRA_API_EMAIL'] = secrets.get('jira_api_email', '')
    os.environ['JIRA_API_TOKEN'] = secrets.get('jira_api_token', '')
    os.environ['JIRA_PROJECT_KEYS'] = secrets.get('jira_project_keys', '')
    os.environ['JIRA_PHASE_FIELD_ID'] = secrets.get('jira_phase_field_id', '')


def send_sns_notification(topic_arn: str, subject: str, message: str):
    """Send notification via SNS."""
    if not topic_arn:
        return

    sns = boto3.client('sns')
    try:
        sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print(f"Failed to send SNS notification: {e}")


def send_run_status_email(run_summary: dict):
    """Send a post-run status email summarising the import results.

    Uses SES (sesv2) for rich HTML formatting.  Recipients are read from the
    compliance_report_recipients table (report_run = 'run_status' or 'all').
    Falls back to the NOTIFICATION_RECIPIENTS env var if no DB rows are found.
    Never raises — all failures are logged and swallowed.

    Args:
        run_summary: dict with keys:
            mode            str   'weekly' | 'incremental'
            run_date        datetime
            week_start      date | None   (weekly only)
            week_end        date | None   (weekly only)
            users_updated   int
            projects_updated int
            time_entries_updated int
            jira_updated    int
            kpi_written     bool
            kpi_week        str  (date string, weekly only)
            spice_triggered int
            compliance_total int
            compliance_compliant int
            compliance_noncompliant int
            errors          list[str]
            status          str  'SUCCESS' | 'ERRORS'
    """
    from zoneinfo import ZoneInfo

    mode = run_summary.get('mode', 'unknown')
    status = run_summary.get('status', 'SUCCESS')
    errors = run_summary.get('errors', [])
    run_date = run_summary.get('run_date', datetime.now())

    # ── Format dates ────────────────────────────────────────────────────────
    ct = ZoneInfo('America/Chicago')
    if run_date.tzinfo is None:
        from datetime import timezone as _tz
        run_date_ct = run_date.replace(tzinfo=_tz.utc).astimezone(ct)
    else:
        run_date_ct = run_date.astimezone(ct)

    run_date_str = run_date_ct.strftime('%A, %B %-d, %Y — %-I:%M %p CT')

    week_start = run_summary.get('week_start')
    week_end = run_summary.get('week_end')
    if week_start and week_end:
        week_range = f"{week_start.strftime('%B %-d')} – {week_end.strftime('%B %-d, %Y')}"
    elif week_start:
        week_range = week_start.strftime('%B %-d, %Y')
    else:
        week_range = 'N/A'

    # ── Determine next run date ──────────────────────────────────────────────
    from datetime import timedelta
    today = run_date_ct.date()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_until_monday)
    next_run_str = next_monday.strftime('%A, %B %-d, %Y') + ' at 9:00 AM CT'

    # ── Status badge (icon finalised after error classification below) ────────
    status_label = 'SUCCESS' if status == 'SUCCESS' else 'ERRORS DETECTED'
    # subject and status_icon are set after error classification below

    # ── Colours ─────────────────────────────────────────────────────────────
    HEADER_BG   = '#1a3a5c'
    STATUS_OK   = '#27ae60'
    STATUS_ERR  = '#c0392b'
    ROW_ALT     = '#f8f9fa'
    BORDER      = '#dee2e6'
    status_color = STATUS_OK if status == 'SUCCESS' else STATUS_ERR

    # ── KPI row ─────────────────────────────────────────────────────────────
    kpi_written = run_summary.get('kpi_written', False)
    kpi_week    = run_summary.get('kpi_week', '')
    kpi_icon    = '✅' if kpi_written else '⚠️ Not written'
    kpi_label   = f"✅ Written for {kpi_week}" if kpi_written else '⚠️ Not written'

    # ── Compliance row ───────────────────────────────────────────────────────
    comp_total       = run_summary.get('compliance_total', 0)
    comp_compliant   = run_summary.get('compliance_compliant', 0)
    comp_noncompliant = run_summary.get('compliance_noncompliant', 0)
    comp_pct = f"{(comp_compliant / comp_total * 100):.1f}%" if comp_total else 'N/A'

    # ── SPICE row ────────────────────────────────────────────────────────────
    spice_count = run_summary.get('spice_triggered', 0)
    spice_label = f"✅ All triggered successfully" if (spice_count > 0 and status == 'SUCCESS') else f"{spice_count} triggered"

    # ── Errors section — classify and enrich each error ─────────────────────
    def _classify_error(raw: str) -> dict:
        """Return a dict with stage, severity, impact, action derived from the raw error string."""
        r = str(raw)
        rl = r.lower()

        # INFO — non-blocking, known gaps
        if 'quicksight:describetheme' in rl or 'accessdenied' in rl and 'describetheme' in rl:
            return dict(stage='QuickSight Theme', severity='INFO',
                        error=r, impact='No dashboard impact — pre-existing IAM gap.',
                        action='No action needed.')
        if 'already in progress' in rl:
            return dict(stage='SPICE Refresh', severity='INFO',
                        error=r, impact='Dataset refresh was already running from a prior trigger.',
                        action='No action needed — dataset is refreshing.')

        # WARNING — partial failure, non-critical stage
        if 'read timeout' in rl and ('bedrock' in rl or 'ai' in rl or 'analysis' in rl):
            return dict(stage='AI Analysis (Bedrock)', severity='WARNING',
                        error=r, impact='AI project health analysis skipped. Core data import unaffected.',
                        action='Will retry next Monday. Re-run manually: {"mode":"analyze_project_health"}')
        if 'task timed out' in rl and ('bedrock' in rl or 'mc_v2' in rl or 'mc v2' in rl or 'audit' in rl):
            return dict(stage='AI Analysis / MC V2 Audit', severity='WARNING',
                        error=r, impact='AI analysis incomplete. Core Clockify and Jira data was imported.',
                        action='Re-run: {"mode":"mc_v2_audit"} or {"mode":"analyze_project_health"}')
        if 'task timed out' in rl:
            return dict(stage='Lambda Timeout', severity='WARNING',
                        error=r, impact='One or more non-critical stages may be incomplete.',
                        action='Check CloudWatch logs for the last stage reached.')
        if 'must be owner of view' in rl or 'must be owner' in rl:
            return dict(stage='Database Views', severity='WARNING',
                        error=r, impact='View recreation skipped. Existing views are still operational.',
                        action='Run manually: {"mode":"apply_views"} with a superuser connection.')
        if 'kpi snapshot' in rl:
            return dict(stage='KPI Snapshot', severity='WARNING',
                        error=r, impact='Weekly KPI tile may show stale or missing values in QuickSight.',
                        action='Re-run: {"mode":"snapshot_kpis"}')
        if 'spice' in rl or 'ingestion' in rl or 'quicksight' in rl:
            return dict(stage='SPICE Refresh', severity='WARNING',
                        error=r, impact='One or more QuickSight datasets may show stale data.',
                        action='Refresh manually from the Streamlit Data Management page.')
        if 'jira' in rl:
            return dict(stage='Jira Import', severity='WARNING',
                        error=r, impact='PS/MC project status data may be stale.',
                        action='Re-run: {"mode":"jira_import"}')
        if 'escalation' in rl:
            return dict(stage='Escalations Import', severity='WARNING',
                        error=r, impact='Escalations dashboard may be stale.',
                        action='Re-run: {"mode":"run_escalations_import"}')

        # CRITICAL — core import stages
        if 'clockify' in rl or 'import' in rl or 'database' in rl or 'connection' in rl:
            return dict(stage='Clockify Import', severity='CRITICAL',
                        error=r, impact='Time entry data may be missing or stale. Dashboards will show incorrect hours.',
                        action='Check CloudWatch logs. Re-run: {"mode":"weekly"}')

        # Default: treat unknown errors as CRITICAL to surface them
        return dict(stage='Unknown', severity='CRITICAL',
                    error=r, impact='Unknown impact — review CloudWatch logs.',
                    action='Check CloudWatch logs for this Lambda invocation.')

    _SEV_COLOR   = {'CRITICAL': '#c0392b', 'WARNING': '#e67e22', 'INFO': '#2980b9'}
    _SEV_ICON    = {'CRITICAL': '🔴', 'WARNING': '🟡', 'INFO': '🔵'}

    if errors:
        classified = [_classify_error(e) for e in errors]
        n_critical = sum(1 for c in classified if c['severity'] == 'CRITICAL')
        n_warning  = sum(1 for c in classified if c['severity'] == 'WARNING')
        n_info     = sum(1 for c in classified if c['severity'] == 'INFO')

        # Summary line
        if n_critical:
            err_summary = f'🔴 {n_critical} critical error{"s" if n_critical > 1 else ""}, {n_warning} warning{"s" if n_warning != 1 else ""}'
        elif n_warning:
            err_summary = f'🟡 {n_warning} warning{"s" if n_warning > 1 else ""}, 0 critical'
        else:
            err_summary = f'🔵 {len(classified)} info notice{"s" if len(classified) != 1 else ""}, 0 critical'

        error_rows = ''
        for c in classified:
            sev_col  = _SEV_COLOR.get(c['severity'], '#555')
            sev_icon = _SEV_ICON.get(c['severity'], '')
            error_rows += f"""
              <tr>
                <td style="border:1px solid #dee2e6;padding:8px 10px;white-space:nowrap;font-weight:700;color:{sev_col}">{sev_icon} {c['severity']}</td>
                <td style="border:1px solid #dee2e6;padding:8px 10px;color:#555;white-space:nowrap">{c['stage']}</td>
                <td style="border:1px solid #dee2e6;padding:8px 10px;font-family:monospace;font-size:12px;color:#c0392b;word-break:break-all">{c['error']}</td>
                <td style="border:1px solid #dee2e6;padding:8px 10px;color:#555">{c['impact']}</td>
                <td style="border:1px solid #dee2e6;padding:8px 10px;color:#2c3e50;font-style:italic">{c['action']}</td>
              </tr>"""

        errors_html = f"""
          <p style="margin:0 0 8px;font-weight:600">{err_summary}</p>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px">
            <tr style="background:#f0f0f0">
              <th style="border:1px solid #dee2e6;padding:7px 10px;text-align:left">Severity</th>
              <th style="border:1px solid #dee2e6;padding:7px 10px;text-align:left">Stage</th>
              <th style="border:1px solid #dee2e6;padding:7px 10px;text-align:left">Error</th>
              <th style="border:1px solid #dee2e6;padding:7px 10px;text-align:left">Impact</th>
              <th style="border:1px solid #dee2e6;padding:7px 10px;text-align:left">Action</th>
            </tr>
            {error_rows}
          </table>"""
    else:
        err_summary = '✅ No errors'
        errors_html = '<p style="color:#27ae60;margin:0">✅ No errors</p>'

    # ── Derive subject and status icon now that severity is known ─────────────
    if status == 'SUCCESS':
        status_icon = '✅'
    elif errors and all(_classify_error(e)['severity'] in ('WARNING', 'INFO') for e in errors):
        status_icon = '⚠️'
        status_label = 'WARNINGS ONLY'
    else:
        status_icon = '❌'

    date_str_subj = run_date_ct.strftime('%B %-d, %Y')
    if mode == 'incremental':
        subject = f"Incremental Refresh — {status_icon} {status_label} — {date_str_subj}"
    else:
        subject = f"Weekly Reporting Import — {status_icon} {status_label} — {date_str_subj}"

    # ── Import results section (weekly vs incremental) ───────────────────────
    if mode == 'weekly':
        import_section = f"""
        <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse;margin-bottom:20px">
          <tr style="background:{HEADER_BG};color:#ffffff">
            <td colspan="2" style="padding:10px 14px;font-weight:bold;font-size:14px;letter-spacing:0.5px">
              IMPORT RESULTS
            </td>
          </tr>
          <tr><td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Reporting Week</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{week_range}</td></tr>
          <tr style="background:{ROW_ALT}">
              <td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Clockify Users</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{run_summary.get('users_updated', 0):,} updated</td></tr>
          <tr><td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Clockify Projects</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{run_summary.get('projects_updated', 0):,} updated</td></tr>
          <tr style="background:{ROW_ALT}">
              <td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Time Entries</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{run_summary.get('time_entries_updated', 0):,} updated</td></tr>
          <tr><td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Jira PS Projects</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{run_summary.get('jira_updated', 0):,} updated</td></tr>
          <tr style="background:{ROW_ALT}">
              <td style="border:1px solid {BORDER};padding:8px 12px;color:#555">KPI Snapshot</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{kpi_label}</td></tr>
        </table>

        <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse;margin-bottom:20px">
          <tr style="background:{HEADER_BG};color:#ffffff">
            <td colspan="2" style="padding:10px 14px;font-weight:bold;font-size:14px;letter-spacing:0.5px">
              COMPLIANCE SNAPSHOT
            </td>
          </tr>
          <tr><td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Total Active Staff</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{comp_total:,}</td></tr>
          <tr style="background:{ROW_ALT}">
              <td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Compliant</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500;color:{STATUS_OK}">{comp_compliant:,} ({comp_pct})</td></tr>
          <tr><td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Non-Compliant</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500;color:{STATUS_ERR if comp_noncompliant else '#555'}">{comp_noncompliant:,}</td></tr>
        </table>
"""
    else:
        # Incremental — compact summary
        import_section = f"""
        <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse;margin-bottom:20px">
          <tr style="background:{HEADER_BG};color:#ffffff">
            <td colspan="2" style="padding:10px 14px;font-weight:bold;font-size:14px;letter-spacing:0.5px">
              INCREMENTAL REFRESH RESULTS
            </td>
          </tr>
          <tr><td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Time Entries</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{run_summary.get('time_entries_updated', 0):,} updated</td></tr>
          <tr style="background:{ROW_ALT}">
              <td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Jira PS Projects</td>
              <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{run_summary.get('jira_updated', 0):,} updated</td></tr>
        </table>
"""

    # ── Full HTML ────────────────────────────────────────────────────────────
    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px">
<div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">

  <!-- Header -->
  <div style="background:{HEADER_BG};padding:20px 24px">
    <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600">
      Weekly Reporting — Import Summary
    </h1>
    <p style="margin:6px 0 0;color:#a8c4e0;font-size:13px">
      Run date: {run_date_str}
    </p>
  </div>

  <!-- Status banner -->
  <div style="background:{status_color};padding:12px 24px">
    <p style="margin:0;color:#ffffff;font-size:16px;font-weight:600">
      {status_icon} {status_label}
    </p>
  </div>

  <!-- Body -->
  <div style="padding:20px 24px">
    {import_section}

    <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse;margin-bottom:20px">
      <tr style="background:{HEADER_BG};color:#ffffff">
        <td colspan="2" style="padding:10px 14px;font-weight:bold;font-size:14px;letter-spacing:0.5px">
          SPICE REFRESH
        </td>
      </tr>
      <tr><td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Datasets Triggered</td>
          <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{spice_count:,}</td></tr>
      <tr style="background:{ROW_ALT}">
          <td style="border:1px solid {BORDER};padding:8px 12px;color:#555">Status</td>
          <td style="border:1px solid {BORDER};padding:8px 12px;font-weight:500">{spice_label}</td></tr>
    </table>

    <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse;margin-bottom:20px">
      <tr style="background:{HEADER_BG};color:#ffffff">
        <td style="padding:10px 14px;font-weight:bold;font-size:14px;letter-spacing:0.5px">
          ERRORS / WARNINGS
        </td>
      </tr>
      <tr><td style="border:1px solid {BORDER};padding:10px 14px">{errors_html}</td></tr>
    </table>

    <p style="color:#555;font-size:13px;margin-top:24px;padding-top:12px;border-top:1px solid {BORDER}">
      Next scheduled run: <strong>{next_run_str}</strong>
    </p>
  </div>

  <!-- Footer -->
  <div style="background:#f8f9fa;padding:12px 24px;border-top:1px solid {BORDER}">
    <p style="margin:0;color:#888;font-size:11px">
      Sent automatically by the Cloudelligent Weekly Reporting System
      &nbsp;|&nbsp; AWS Account 961341524729
    </p>
  </div>

</div>
</body>
</html>"""

    # ── Resolve recipients ───────────────────────────────────────────────────
    recipient_emails = []
    try:
        from sqlalchemy import text
        from src.database.config import engine
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT email FROM compliance_report_recipients
                WHERE is_active = TRUE
                  AND report_run IN ('run_status', 'all', 'both')
            """)).fetchall()
            recipient_emails = [r[0] for r in rows]
    except Exception as db_err:
        print(f"[run_status_email] Could not query recipients from DB: {db_err}")

    # Fallback: env var or hardcoded admin address
    if not recipient_emails:
        fallback = os.environ.get('NOTIFICATION_RECIPIENTS', 'chris.xenos@cloudelligent.com')
        recipient_emails = [e.strip() for e in fallback.split(',') if e.strip()]
        print(f"[run_status_email] Using fallback recipients: {recipient_emails}")

    if not recipient_emails:
        print("[run_status_email] No recipients — email skipped")
        return

    # ── Send via SES ─────────────────────────────────────────────────────────
    try:
        ses = boto3.client('sesv2', region_name='us-east-1')
        ses.send_email(
            FromEmailAddress='reports@cloudelligent.com',
            Destination={'ToAddresses': recipient_emails},
            Content={'Simple': {
                'Subject': {'Data': subject},
                'Body': {'Html': {'Data': html_body}}
            }}
        )
        print(f"[run_status_email] Sent '{subject}' to {recipient_emails}")
    except Exception as ses_err:
        print(f"[run_status_email] SES send failed (non-fatal): {ses_err}")


def get_all_dataset_ids(environment: str = 'production') -> list:
    """Return all QuickSight SPICE dataset IDs to refresh.

    Includes both CloudFormation-managed datasets (suffixed with 'prod')
    and manually-created datasets (UUIDs or custom IDs).
    """
    return [
        # CloudFormation-managed datasets (use 'prod' suffix)
        'clockify-pod-performance-prod',
        'clockify-missing-time-submissions-prod',
        'time-compliance-current-week-prod',       # vw_weekly_compliance_report (all staff + status)
        # Manually-created datasets (fixed IDs)
        'clockify-missing-time-submissions',
        '7833b3c6-cec4-4956-b02a-2316198187cb',  # vw_contractor_weekly_trend
        'c84d2b1f-de9d-42cd-a389-e425a100c4d4',  # vw_contractor_time_summary
        '3bdc816d-4df6-4db7-b3e6-64e230f28f14',  # vw_forecast_over_40_hours
        '42098a5b-a94f-41d5-8300-396f1fec66bf',  # vw_forecast_summary
        'fc56c886-f0d2-4935-8b32-f0862325d3f0',  # vw_forecast_vs_actual
        '8900f5dc-687e-4d5b-9f91-5efd0cd1daed',  # ps_resource_forecasts
        'ps-project-status-view',                  # ps_project_status
        'data-freshness',                          # data_freshness
        'non-billable-analysis',                   # vw_non_billable_project_analysis
        'free-agent-availability',                 # vw_free_agent_availability
        # AI project health analysis datasets (created manually in QuickSight)
        'ai-ps-analysis-by-user',
        'ai-ps-analysis-by-project',
        'ai-mc-analysis-by-user',
        'ai-mc-analysis-by-project',
        # PS Profitability datasets
        'ps-profitability-2026',
        'ps-profitability-weekly-2026',
        'ps-profitability-chart',
        # MC V2 Audit datasets
        'mc-v2-audit-by-customer',
        'mc-v2-audit-by-phase',
        'mc-v2-audit-grid',
        # Project hours by assignment
        'project-hours-by-assignment',
        # Practice group performance (Project Hours tab)
        'practice-group-performance',
        # AI Forecast Analysis datasets
        'ai-forecast-analysis',
        'ai-forecast-summary',
        'pm-forecast-accuracy',
        # Escalations datasets
        'escalations-detail',
        'escalations-by-customer',
        # PS stage week-over-week trend
        'ps-stage-trend',
        # Productive utilization
        'productive-utilization',
        # Missing time history (weekly compliance + reasons)
        'missing-time-history',
        # Current-week compliance report (all users, compliant + non-compliant)
        'time-compliance-current-week',
        # Project time detail (last 4 weeks, filterable)
        'project-time-detail',
        # Customer status assignments (active Jira queue, resource per row)
        'customer-status-assignments',
        # Project directory (one row per resource per project)
        'project-directory',
        # COO dashboards — new datasets (2026-04)
        'kpi-weekly-snapshots-prod',
        'project-hours-summary-prod',
        'project-hours-current-week-prod',
        'category-hours-summary-prod',
        # MC Service Delivery
        'mc-ticket-activity',
    ]


def refresh_quicksight_datasets(dataset_ids: list):
    """Trigger QuickSight SPICE refresh for datasets.

    Args:
        dataset_ids: List of QuickSight dataset IDs to refresh
    """
    if not dataset_ids:
        return

    quicksight = boto3.client('quicksight')
    account_id = boto3.client('sts').get_caller_identity()['Account']

    results = []
    for dataset_id in dataset_ids:
        try:
            ingestion_id = f"ingestion-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{dataset_id}"
            response = quicksight.create_ingestion(
                DataSetId=dataset_id,
                IngestionId=ingestion_id,
                AwsAccountId=account_id
            )
            results.append({
                'dataset_id': dataset_id,
                'status': 'triggered',
                'ingestion_id': ingestion_id
            })
            print(f"Triggered QuickSight refresh for dataset {dataset_id}")
        except Exception as e:
            print(f"Failed to refresh dataset {dataset_id}: {e}")
            results.append({
                'dataset_id': dataset_id,
                'status': 'failed',
                'error': str(e)
            })

    return results


def apply_database_views(master_url: str = None) -> Dict[str, Any]:
    """Apply database views from SQL file.

    Uses master_url (postgres superuser) when provided so that DROP VIEW on
    views owned by postgres does not fail with 'must be owner of view'.
    Falls back to the report_user DATABASE_URL if master_url is not supplied.
    """
    from pathlib import Path
    from sqlalchemy import create_engine, text

    print("Applying database views...")

    # Prefer master URL (postgres superuser) to handle DROP VIEW on postgres-owned views.
    # Fall back to report_user DATABASE_URL if master URL is unavailable.
    if master_url:
        print("Using master database URL (superuser) for view recreation")
        engine = create_engine(master_url)
    else:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL not set - call set_environment_from_secrets first")
        print("Using report_user DATABASE_URL (master_url not available)")
        engine = create_engine(database_url)

    sql_file = Path(__file__).parent / "database" / "create_views.sql"

    with open(sql_file, 'r') as f:
        sql_content = f.read()

    with engine.begin() as connection:
        connection.execute(text(sql_content))

    # Grant permissions separately (DROP VIEW removes grants)
    try:
        with engine.begin() as connection:
            connection.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC"))
            connection.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))
    except Exception as e:
        print(f"Warning: Could not grant permissions: {e}")

    print("Database views applied successfully")
    return {'status': 'success', 'message': 'Views applied successfully'}


def diagnose_import_logs() -> Dict[str, Any]:
    """Diagnose import_logs table to debug missing last_updated fields."""
    from sqlalchemy import create_engine, text

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set")

    engine = create_engine(database_url)

    results = {}
    with engine.connect() as connection:
        # Check total records
        total = connection.execute(text("SELECT COUNT(*) FROM import_logs")).scalar()
        results['total_records'] = total

        # Check distinct statuses
        statuses = connection.execute(text(
            "SELECT DISTINCT status, COUNT(*) FROM import_logs GROUP BY status"
        )).fetchall()
        results['statuses'] = [{'status': s[0], 'count': s[1]} for s in statuses]

        # Check distinct import_categories
        categories = connection.execute(text(
            "SELECT DISTINCT import_category, COUNT(*) FROM import_logs GROUP BY import_category"
        )).fetchall()
        results['categories'] = [{'category': c[0], 'count': c[1]} for c in categories]

        # Check recent time_entries imports
        recent = connection.execute(text("""
            SELECT import_type, import_category, status, completed_at
            FROM import_logs
            WHERE import_category = 'time_entries'
            ORDER BY completed_at DESC NULLS LAST
            LIMIT 5
        """)).fetchall()
        results['recent_time_entries'] = [
            {'type': r[0], 'category': r[1], 'status': r[2], 'completed_at': str(r[3]) if r[3] else None}
            for r in recent
        ]

        # Test the actual CTE query (matching the view format - Central Time)
        cte_result = connection.execute(text("""
            SELECT (completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago')::DATE AS last_updated_date,
                   TO_CHAR(completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago', 'HH:MI AM') AS last_updated_time
            FROM import_logs
            WHERE import_category = 'time_entries'
              AND status = 'success'
            ORDER BY completed_at DESC
            LIMIT 1
        """)).fetchone()
        if cte_result:
            results['cte_query_result'] = {
                'last_updated_date': str(cte_result[0]) if cte_result[0] else None,
                'last_updated_time': cte_result[1]
            }
        else:
            results['cte_query_result'] = None

    return results


def diagnose_user_data() -> Dict[str, Any]:
    """Diagnose user data including status, pod assignments, and custom fields."""
    from sqlalchemy import create_engine, text

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set")

    engine = create_engine(database_url)

    results = {}
    with engine.connect() as connection:
        # Check user status counts
        statuses = connection.execute(text("""
            SELECT status, COUNT(*) as user_count
            FROM clockify_users
            GROUP BY status
            ORDER BY user_count DESC
        """)).fetchall()
        results['user_statuses'] = [{'status': s[0], 'count': s[1]} for s in statuses]

        # Get distinct raw pod_assignment values for active users
        pods = connection.execute(text("""
            SELECT pod_assignment, COUNT(*) as user_count
            FROM clockify_users
            WHERE status = 'active'
            GROUP BY pod_assignment
            ORDER BY user_count DESC
        """)).fetchall()
        results['active_user_pods'] = [{'pod_assignment': p[0], 'count': p[1]} for p in pods]

        # Get distinct practice_alignment values
        practices = connection.execute(text("""
            SELECT practice_alignment, COUNT(*) as user_count
            FROM clockify_users
            WHERE status = 'active'
            GROUP BY practice_alignment
            ORDER BY user_count DESC
        """)).fetchall()
        results['practice_alignments'] = [{'practice_alignment': p[0], 'count': p[1]} for p in practices]

        # Get distinct skill_area values
        skills = connection.execute(text("""
            SELECT skill_area, COUNT(*) as user_count
            FROM clockify_users
            WHERE status = 'active'
            GROUP BY skill_area
            ORDER BY user_count DESC
        """)).fetchall()
        results['skill_areas'] = [{'skill_area': s[0], 'count': s[1]} for s in skills]

        # Sample some users with their custom fields
        sample = connection.execute(text("""
            SELECT name, status, pod_assignment, practice_alignment, skill_area, daily_capacity
            FROM clockify_users
            ORDER BY updated_at DESC
            LIMIT 10
        """)).fetchall()
        results['sample_users'] = [
            {'name': u[0], 'status': u[1], 'pod': u[2], 'practice': u[3], 'skill': u[4], 'capacity': float(u[5]) if u[5] else None}
            for u in sample
        ]

        # Check the view output
        view_sample = connection.execute(text("""
            SELECT name, pod_assignment, practice_alignment, skill_area, submission_status
            FROM vw_missing_time_submissions
            LIMIT 10
        """)).fetchall()
        results['view_sample'] = [
            {'name': v[0], 'pod': v[1], 'practice': v[2], 'skill': v[3], 'status': v[4]}
            for v in view_sample
        ]

        # Get submission status counts
        status_counts = connection.execute(text("""
            SELECT submission_status, COUNT(*) as user_count
            FROM vw_missing_time_submissions
            GROUP BY submission_status
            ORDER BY
                CASE submission_status
                    WHEN 'No Time Submitted' THEN 1
                    WHEN 'Less Than 50%' THEN 2
                    WHEN 'Less Than 90%' THEN 3
                    WHEN 'Complete' THEN 4
                END
        """)).fetchall()
        results['submission_status_counts'] = [
            {'status': s[0], 'count': s[1]}
            for s in status_counts
        ]

        # Get week being evaluated
        week_info = connection.execute(text("""
            SELECT week_start_date, last_updated_date, last_updated_time
            FROM vw_missing_time_submissions
            LIMIT 1
        """)).fetchone()
        if week_info:
            results['week_info'] = {
                'week_start': str(week_info[0]),
                'last_updated_date': str(week_info[1]) if week_info[1] else None,
                'last_updated_time': week_info[2]
            }

        # Get all users from the missing time view
        all_missing = connection.execute(text("""
            SELECT name, email, hours_submitted, submission_status
            FROM vw_missing_time_submissions
            ORDER BY name
        """)).fetchall()
        results['all_missing_users'] = [
            {'name': u[0], 'email': u[1], 'hours': float(u[2]) if u[2] else 0, 'status': u[3]}
            for u in all_missing
        ]

    return results


def update_analysis_week_parameter(week_start_date):
    """Update pWeekStart parameter default in COO analysis to the new week."""
    try:
        import boto3 as _boto3
        qs = _boto3.client('quicksight', region_name='us-east-1')
        account_id = _boto3.client('sts').get_caller_identity()['Account']
        analysis_id = 'coo-operational-analysis-prod'

        resp = qs.describe_analysis_definition(AwsAccountId=account_id, AnalysisId=analysis_id)
        defn = resp['Definition']

        new_default = f'{week_start_date}T00:00:00Z'
        for p in defn.get('ParameterDeclarations', []):
            dtp = p.get('DateTimeParameterDeclaration', {})
            if dtp.get('Name') in ('pWeekStart', 'pWeekEnd'):  # handle both during rename transition
                dtp['DefaultValues']['StaticValues'] = [new_default]
                break

        name = qs.describe_analysis(AwsAccountId=account_id, AnalysisId=analysis_id)['Analysis']['Name']
        theme_arn = f'arn:aws:quicksight:us-east-1:{account_id}:theme/cloudelligent-brand-theme'
        qs.update_analysis(AwsAccountId=account_id, AnalysisId=analysis_id, Name=name,
            ThemeArn=theme_arn, Definition=defn)
        print(f'Updated COO analysis week parameter to {new_default}')
    except Exception as e:
        print(f'Failed to update analysis parameter (non-fatal): {e}')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler for Clockify data import.

    Args:
        event: Lambda event object with optional parameters:
            - mode: 'incremental', 'weekly', 'full', or 'apply_views'
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

    # Get configuration from event
    mode = event.get('mode', 'incremental')
    weeks_back = event.get('weeks_back', None)
    notify = event.get('notify', False)
    dataset_ids = event.get('quicksight_dataset_ids', [])  # Optional override; empty = refresh all
    notification_topic = os.environ.get('NOTIFICATION_TOPIC_ARN', '')

    try:
        # Retrieve and set secrets
        print("Retrieving secrets from Secrets Manager...")
        secrets = get_secrets()
        set_environment_from_secrets(secrets)
        print("Secrets loaded successfully")

        # Handle apply_views mode
        if mode == 'apply_views':
            result = apply_database_views(master_url=secrets.get('master_database_url'))
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }

        # Handle snapshot_kpis mode — compute and store weekly KPI snapshot
        if mode == 'snapshot_kpis':
            from src.integrations.kpi_snapshot import run as kpi_run
            from datetime import date as _date
            week_str = event.get('week_start')
            week_start = _date.fromisoformat(week_str) if week_str else None
            result = kpi_run(week_start=week_start)
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f"KPI snapshot written for {result['week_start_date']}",
                    'week_start_date': str(result['week_start_date']),
                })
            }

        if mode == 'forecast_resources':
            from src.integrations.forecast_resources import run_resource_forecast
            from src.database.config import engine
            with engine.connect() as conn:
                result = run_resource_forecast(conn)
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f"Resource forecast complete: {result['people']} people, {result['projects']} projects",
                    **result
                })
            }

        # Handle run_escalations_import mode — create table/views + import ES data
        if mode == 'run_escalations_import':
            from sqlalchemy import create_engine, text as sa_text
            db_url = os.environ.get('DATABASE_URL')
            engine = create_engine(db_url)
            ddl = """
                CREATE TABLE IF NOT EXISTS escalations (
                    id                  SERIAL PRIMARY KEY,
                    jira_issue_id       VARCHAR(50) UNIQUE NOT NULL,
                    issue_key           VARCHAR(50) NOT NULL,
                    customer_name       VARCHAR(255),
                    epic_key            VARCHAR(50),
                    epic_summary        VARCHAR(500),
                    summary             VARCHAR(500),
                    status              VARCHAR(100),
                    status_category     VARCHAR(50),
                    priority            VARCHAR(50),
                    assignee_name       VARCHAR(255),
                    reporter_name       VARCHAR(255),
                    created_date        TIMESTAMP,
                    updated_date        TIMESTAMP,
                    resolution_date     TIMESTAMP,
                    days_open           INTEGER,
                    days_to_resolve     INTEGER,
                    synced_at           TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_escalations_customer ON escalations(customer_name);
                CREATE INDEX IF NOT EXISTS idx_escalations_status   ON escalations(status_category);
                CREATE INDEX IF NOT EXISTS idx_escalations_created  ON escalations(created_date);
                CREATE OR REPLACE VIEW vw_escalations AS
                SELECT issue_key, customer_name, epic_key, summary, status, status_category,
                       priority, assignee_name, reporter_name,
                       created_date::date AS created_date, updated_date::date AS updated_date,
                       resolution_date::date AS resolution_date,
                       days_open, days_to_resolve,
                       EXTRACT(YEAR FROM created_date)::int  AS created_year,
                       EXTRACT(MONTH FROM created_date)::int AS created_month,
                       TO_CHAR(created_date, 'YYYY-MM')      AS created_month_label,
                       CASE WHEN status_category = 'Done'        THEN 'Resolved'
                            WHEN status_category = 'In Progress' THEN 'Active'
                            ELSE 'Open' END                   AS escalation_state
                FROM escalations WHERE customer_name IS NOT NULL;
                CREATE OR REPLACE VIEW vw_escalations_by_customer AS
                SELECT customer_name,
                       COUNT(*)                                                                  AS total_escalations,
                       COUNT(*) FILTER (WHERE status_category != 'Done')                        AS open_escalations,
                       COUNT(*) FILTER (WHERE status_category = 'Done')                         AS resolved_escalations,
                       COUNT(*) FILTER (WHERE priority IN ('High','Highest'))                   AS high_priority_count,
                       ROUND(AVG(days_to_resolve) FILTER (WHERE days_to_resolve IS NOT NULL),1) AS avg_days_to_resolve,
                       ROUND(AVG(days_open)       FILTER (WHERE days_open IS NOT NULL),1)       AS avg_days_open,
                       MAX(created_date)::date AS most_recent_escalation,
                       MIN(created_date)::date AS first_escalation
                FROM escalations WHERE customer_name IS NOT NULL GROUP BY customer_name;
                GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
            """
            with engine.begin() as conn:
                for stmt in [s.strip() for s in ddl.split(';') if s.strip()]:
                    conn.execute(sa_text(stmt))
            print("Escalations DDL applied")
            from src.integrations.import_escalations import run_escalations_import
            esc_result = run_escalations_import()
            print(f"Escalations import result: {esc_result}")
            refresh_quicksight_datasets(['escalations-detail', 'escalations-by-customer'])
            return {
                'statusCode': 200,
                'body': json.dumps({'escalations': esc_result})
            }

        # Handle refresh_quicksight_only mode
        if mode == 'refresh_quicksight_only':
            dataset_ids = event.get('quicksight_dataset_ids', [])
            results = refresh_quicksight_datasets(dataset_ids)
            return {
                'statusCode': 200,
                'body': json.dumps({'refreshed': results})
            }

        # Handle fix_report_user mode — create/reset report_user using master credentials
        # Uses 'master_database_url' key from Secrets Manager to connect as postgres.
        # Creates report_user if it doesn't exist, resets password to match db_password in secret,
        # and grants all required privileges on the weekly_reporting database.
        if mode == 'fix_report_user':
            from sqlalchemy import create_engine, text as sa_text
            master_url = secrets.get('master_database_url', '')
            target_password = secrets.get('db_password', '')
            if not master_url:
                return {'statusCode': 400, 'body': json.dumps({'error': 'master_database_url not found in secret'})}
            if not target_password:
                return {'statusCode': 400, 'body': json.dumps({'error': 'db_password not found in secret'})}
            db_name = os.environ.get('DB_NAME', 'weekly_reporting')
            master_engine = create_engine(master_url)
            actions_taken = []
            try:
                with master_engine.begin() as conn:
                    # Check if report_user exists
                    exists = conn.execute(
                        sa_text("SELECT 1 FROM pg_roles WHERE rolname = 'report_user'")
                    ).fetchone()
                    if not exists:
                        conn.execute(sa_text(f"CREATE USER report_user WITH PASSWORD '{target_password}'"))
                        actions_taken.append('created report_user')
                    else:
                        conn.execute(sa_text(f"ALTER USER report_user WITH PASSWORD '{target_password}'"))
                        actions_taken.append('reset report_user password')
                    # Grant database-level privileges (must be done outside table-level transaction)
                    conn.execute(sa_text(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO report_user"))
                    actions_taken.append(f'granted all on database {db_name}')
                # Grant schema and table/sequence privileges (separate transaction)
                with master_engine.begin() as conn:
                    conn.execute(sa_text("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO report_user"))
                    conn.execute(sa_text("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO report_user"))
                    conn.execute(sa_text("GRANT USAGE ON SCHEMA public TO report_user"))
                    conn.execute(sa_text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO report_user"))
                    conn.execute(sa_text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO report_user"))
                    actions_taken.append('granted table/sequence/schema privileges')
                # Verify: connect as report_user
                verify_url = os.environ.get('DATABASE_URL', '')
                verify_engine = create_engine(verify_url)
                with verify_engine.connect() as vconn:
                    current_user = vconn.execute(sa_text("SELECT current_user")).scalar()
                    table_count = vconn.execute(sa_text(
                        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
                    )).scalar()
                verify_engine.dispose()
                master_engine.dispose()
                actions_taken.append(f'verified login as {current_user}, visible tables: {table_count}')
                return {'statusCode': 200, 'body': json.dumps({'status': 'success', 'actions': actions_taken})}
            except Exception as fix_e:
                master_engine.dispose()
                return {'statusCode': 500, 'body': json.dumps({'error': str(fix_e), 'actions_taken': actions_taken})}

        # Handle run_query mode — execute a read-only SELECT and return rows
        if mode == 'run_query':
            from sqlalchemy import text
            from src.database.config import engine
            sql = event.get('sql', '')
            if not sql:
                return {'statusCode': 400, 'body': json.dumps({'error': 'sql parameter required'})}
            is_write = sql.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'VACUUM', 'REINDEX'))
            ctx = engine.begin() if is_write else engine.connect()
            with ctx as conn:
                result = conn.execute(text(sql))
                cols = list(result.keys()) if result.returns_rows else []
                rows = [list(r) for r in result.fetchall()] if result.returns_rows else []
            return {'statusCode': 200, 'body': json.dumps({'columns': cols, 'rows': rows}, default=str)}

        # Handle create_quicksight_datasets mode — creates manually-managed datasets
        if mode == 'create_quicksight_datasets':
            qs = boto3.client('quicksight', region_name='us-east-1')
            account_id = boto3.client('sts').get_caller_identity()['Account']
            data_source_arn = f'arn:aws:quicksight:us-east-1:{account_id}:datasource/weekly-reporting-postgres'

            # Grant QuickSight admin users full dataset permissions
            # (list_users requires a permission the Lambda role doesn't have; use known ARNs)
            user_arns = [
                f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AWSAdministratorAccess_ed420cc098d02bac/chris.xenos',
                f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AdministratorAccess_2be0458d4fa377aa/tahir.nisar',
                f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AdministratorAccess_2be0458d4fa377aa/s.furlong',
                f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AWSAdministratorAccess_ed420cc098d02bac/fatima',
            ]
            permissions = [
                {
                    'Principal': arn,
                    'Actions': [
                        'quicksight:DescribeDataSet',
                        'quicksight:DescribeDataSetPermissions',
                        'quicksight:PassDataSet',
                        'quicksight:DescribeIngestion',
                        'quicksight:ListIngestions',
                        'quicksight:UpdateDataSet',
                        'quicksight:DeleteDataSet',
                        'quicksight:CreateIngestion',
                        'quicksight:CancelIngestion',
                        'quicksight:UpdateDataSetPermissions',
                    ]
                }
                for arn in user_arns
            ]

            datasets_to_create = [
                {
                    'DataSetId': 'project-hours-by-assignment',
                    'Name': 'Project Hours by Assignment',
                    'ViewName': 'vw_project_hours_by_assignment',
                    'InputColumns': [
                        {'Name': 'week_start', 'Type': 'DATETIME'},
                        {'Name': 'category', 'Type': 'STRING'},
                        {'Name': 'customer_name', 'Type': 'STRING'},
                        {'Name': 'pod', 'Type': 'STRING'},
                        {'Name': 'clockify_client', 'Type': 'STRING'},
                        {'Name': 'project_name', 'Type': 'STRING'},
                        {'Name': 'resource_count', 'Type': 'INTEGER'},
                        {'Name': 'total_hours', 'Type': 'DECIMAL'},
                        {'Name': 'billable_hours', 'Type': 'DECIMAL'},
                        {'Name': 'non_billable_hours', 'Type': 'DECIMAL'},
                        {'Name': 'non_billable_productive_hours', 'Type': 'DECIMAL'},
                    ],
                },
                {
                    'DataSetId': 'project-time-detail',
                    'Name': 'Project Time Detail',
                    'ViewName': 'vw_project_time_detail',
                    'InputColumns': [
                        {'Name': 'clockify_entry_id', 'Type': 'STRING'},
                        {'Name': 'entry_date', 'Type': 'DATETIME'},
                        {'Name': 'week_start_date', 'Type': 'DATETIME'},
                        {'Name': 'client_name', 'Type': 'STRING'},
                        {'Name': 'project_name', 'Type': 'STRING'},
                        {'Name': 'project_type', 'Type': 'STRING'},
                        {'Name': 'pod_assignment', 'Type': 'STRING'},
                        {'Name': 'task_name', 'Type': 'STRING'},
                        {'Name': 'description', 'Type': 'STRING'},
                        {'Name': 'user_name', 'Type': 'STRING'},
                        {'Name': 'billable', 'Type': 'BIT'},
                        {'Name': 'duration_hours', 'Type': 'DECIMAL'},
                    ],
                },
                {
                    'DataSetId': 'project-directory',
                    'Name': 'Project Directory',
                    'ViewName': 'vw_project_directory',
                    'InputColumns': [
                        {'Name': 'issue_key', 'Type': 'STRING'},
                        {'Name': 'client_name', 'Type': 'STRING'},
                        {'Name': 'project_name', 'Type': 'STRING'},
                        {'Name': 'category', 'Type': 'STRING'},
                        {'Name': 'project_type', 'Type': 'STRING'},
                        {'Name': 'status', 'Type': 'STRING'},
                        {'Name': 'status_category', 'Type': 'STRING'},
                        {'Name': 'health', 'Type': 'STRING'},
                        {'Name': 'actual_start_date', 'Type': 'DATETIME'},
                        {'Name': 'expected_end_date', 'Type': 'DATETIME'},
                        {'Name': 'revised_completion_date', 'Type': 'DATETIME'},
                        {'Name': 'budget_hours', 'Type': 'DECIMAL'},
                        {'Name': 'jira_board_link', 'Type': 'STRING'},
                        {'Name': 'sow_link', 'Type': 'STRING'},
                        {'Name': 'role', 'Type': 'STRING'},
                        {'Name': 'resource_name', 'Type': 'STRING'},
                    ],
                },
                {
                    'DataSetId': 'customer-status-assignments',
                    'Name': 'Customer Status Assignments',
                    'ViewName': 'vw_customer_status_assignments',
                    'InputColumns': [
                        {'Name': 'issue_key', 'Type': 'STRING'},
                        {'Name': 'client_name', 'Type': 'STRING'},
                        {'Name': 'project_name', 'Type': 'STRING'},
                        {'Name': 'category', 'Type': 'STRING'},
                        {'Name': 'project_type', 'Type': 'STRING'},
                        {'Name': 'status', 'Type': 'STRING'},
                        {'Name': 'status_category', 'Type': 'STRING'},
                        {'Name': 'priority', 'Type': 'STRING'},
                        {'Name': 'actual_start_date', 'Type': 'DATETIME'},
                        {'Name': 'expected_end_date', 'Type': 'DATETIME'},
                        {'Name': 'revised_completion_date', 'Type': 'DATETIME'},
                        {'Name': 'assignment_role', 'Type': 'STRING'},
                        {'Name': 'resource_name', 'Type': 'STRING'},
                    ],
                },
            ]

            results = []
            for ds in datasets_to_create:
                try:
                    qs.create_data_set(
                        AwsAccountId=account_id,
                        DataSetId=ds['DataSetId'],
                        Name=ds['Name'],
                        ImportMode='SPICE',
                        PhysicalTableMap={
                            ds['DataSetId']: {
                                'RelationalTable': {
                                    'DataSourceArn': data_source_arn,
                                    'Schema': 'public',
                                    'Name': ds['ViewName'],
                                    'InputColumns': ds['InputColumns'],
                                }
                            }
                        },
                        LogicalTableMap={
                            f"{ds['DataSetId']}-logical": {
                                'Alias': ds['Name'],
                                'Source': {'PhysicalTableId': ds['DataSetId']},
                            }
                        },
                        Permissions=permissions,
                    )
                    results.append({'dataset_id': ds['DataSetId'], 'status': 'created'})
                    print(f"Created QuickSight dataset: {ds['DataSetId']}")
                except qs.exceptions.ResourceExistsException:
                    results.append({'dataset_id': ds['DataSetId'], 'status': 'already_exists'})
                    print(f"Dataset already exists: {ds['DataSetId']}")
                except Exception as e:
                    results.append({'dataset_id': ds['DataSetId'], 'status': 'error', 'error': str(e)})
                    print(f"Error creating dataset {ds['DataSetId']}: {e}")

            return {
                'statusCode': 200,
                'body': json.dumps({'datasets': results})
            }

        # Handle diagnose mode
        if mode == 'diagnose':
            result = diagnose_import_logs()
            return {
                'statusCode': 200,
                'body': json.dumps(result, default=str)
            }

        # Handle diagnose_users mode
        if mode == 'diagnose_users':
            result = diagnose_user_data()
            return {
                'statusCode': 200,
                'body': json.dumps(result, default=str)
            }

        # Handle diagnose_contractors mode
        if mode == 'diagnose_contractors':
            from sqlalchemy import create_engine, text

            database_url = os.environ.get('DATABASE_URL')
            engine = create_engine(database_url)

            result = {}
            with engine.connect() as connection:
                # Check employment_designation values
                designations = connection.execute(text("""
                    SELECT employment_designation, COUNT(*) as user_count
                    FROM clockify_users
                    WHERE status = 'active'
                    GROUP BY employment_designation
                    ORDER BY user_count DESC
                """)).fetchall()
                result['employment_designations'] = [{'designation': d[0], 'count': d[1]} for d in designations]

                # Check contractor weekly trend view
                trend = connection.execute(text("""
                    SELECT * FROM vw_contractor_weekly_trend
                """)).fetchall()
                result['weekly_trend'] = [
                    {'week': str(t[0]), 'weeks_ago': t[2], 'label': t[3], 'hours': float(t[4]) if t[4] else 0, 'contractors': t[6]}
                    for t in trend
                ]

                # Check contractor summary view
                summary = connection.execute(text("""
                    SELECT * FROM vw_contractor_time_summary LIMIT 10
                """)).fetchall()
                result['contractor_summary'] = [
                    {'name': s[0], 'pod': s[1], 'last_week_hours': float(s[4]) if s[4] else 0, 'avg_4_week': float(s[6]) if s[6] else 0}
                    for s in summary
                ]

            return {
                'statusCode': 200,
                'body': json.dumps(result, default=str)
            }

        # Handle diagnose_dates mode - check latest entry dates and POD data
        if mode == 'diagnose_dates':
            from sqlalchemy import create_engine, text

            database_url = os.environ.get('DATABASE_URL')
            engine = create_engine(database_url)

            result = {}
            with engine.connect() as connection:
                # Check latest entry dates
                latest = connection.execute(text("""
                    SELECT MAX(entry_date) as max_date, MIN(entry_date) as min_date, COUNT(*) as total
                    FROM clockify_detailed_time_entries
                """)).fetchone()
                result['entry_date_range'] = {
                    'latest': str(latest[0]) if latest[0] else None,
                    'earliest': str(latest[1]) if latest[1] else None,
                    'total_entries': latest[2]
                }

                # Check entries by week
                weekly = connection.execute(text("""
                    SELECT DATE_TRUNC('week', entry_date)::date as week_start,
                           COUNT(*) as entry_count,
                           SUM(duration_hours) as total_hours
                    FROM clockify_detailed_time_entries
                    WHERE entry_date >= CURRENT_DATE - INTERVAL '4 weeks'
                    GROUP BY DATE_TRUNC('week', entry_date)
                    ORDER BY week_start DESC
                """)).fetchall()
                result['entries_by_week'] = [
                    {'week': str(w[0]), 'entries': w[1], 'hours': float(w[2]) if w[2] else 0}
                    for w in weekly
                ]

                # Check POD data for last 2 weeks
                pod_data = connection.execute(text("""
                    SELECT pod_assignment,
                           COUNT(*) as entries,
                           SUM(duration_hours) as hours
                    FROM clockify_detailed_time_entries
                    WHERE entry_date >= CURRENT_DATE - INTERVAL '2 weeks'
                      AND pod_assignment IS NOT NULL
                    GROUP BY pod_assignment
                    ORDER BY hours DESC
                """)).fetchall()
                result['pod_data_recent'] = [
                    {'pod': p[0], 'entries': p[1], 'hours': float(p[2]) if p[2] else 0}
                    for p in pod_data
                ]

            return {
                'statusCode': 200,
                'body': json.dumps(result, default=str)
            }

        # Handle debug_secrets mode - show what secrets/env vars are set
        if mode == 'debug_secrets':
            # Show what environment variables are set (mask sensitive values)
            jira_base_url = os.environ.get('JIRA_BASE_URL', '')
            jira_email = os.environ.get('JIRA_API_EMAIL', '')
            jira_token = os.environ.get('JIRA_API_TOKEN', '')
            jira_keys = os.environ.get('JIRA_PROJECT_KEYS', '')

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'secrets_retrieved': True,
                    'env_vars': {
                        'JIRA_BASE_URL': jira_base_url,
                        'JIRA_API_EMAIL': jira_email,
                        'JIRA_API_TOKEN': f"{jira_token[:10]}..." if len(jira_token) > 10 else '(empty or short)',
                        'JIRA_PROJECT_KEYS': jira_keys
                    },
                    'raw_secrets_jira_keys': list(secrets.keys()) if secrets else []
                })
            }

        # Handle diagnose_ps mode - check PS project status data
        if mode == 'diagnose_ps':
            from sqlalchemy import text
            from src.database.config import engine

            with engine.connect() as conn:
                # Check table count
                table_count = conn.execute(text("SELECT COUNT(*) FROM ps_project_status")).scalar()

                # Check view count (use savepoint so failure doesn't abort transaction)
                try:
                    view_count = conn.execute(text("SELECT COUNT(*) FROM vw_ps_project_status")).scalar()
                except Exception as e:
                    view_count = f"Error: {str(e)}"
                    conn.rollback()

                # Get sample data
                sample = conn.execute(text(
                    "SELECT client_name, project_name, status, health_overall, issue_type FROM ps_project_status LIMIT 5"
                )).fetchall()

                # Check ps_resource_forecasts
                try:
                    forecast_count = conn.execute(text("SELECT COUNT(*) FROM ps_resource_forecasts")).scalar()
                    forecast_weeks = conn.execute(text(
                        "SELECT COUNT(DISTINCT week_start_date) as week_count, MIN(week_start_date) as earliest, MAX(week_start_date) as latest FROM ps_resource_forecasts"
                    )).fetchone()
                    forecast_info = {
                        'total_records': forecast_count,
                        'unique_weeks': forecast_weeks[0] if forecast_weeks else 0,
                        'earliest_week': str(forecast_weeks[1]) if forecast_weeks and forecast_weeks[1] else None,
                        'latest_week': str(forecast_weeks[2]) if forecast_weeks and forecast_weeks[2] else None
                    }
                except Exception as e:
                    forecast_info = f"Error: {str(e)}"

                # Check last update times
                try:
                    ps_last_sync = conn.execute(text(
                        "SELECT MAX(synced_at) FROM ps_project_status"
                    )).scalar()
                    forecast_last_update = conn.execute(text(
                        "SELECT MAX(created_at) FROM ps_resource_forecasts"
                    )).scalar()
                    last_updates = {
                        'ps_project_status_last_sync': str(ps_last_sync) if ps_last_sync else None,
                        'ps_resource_forecasts_last_update': str(forecast_last_update) if forecast_last_update else None
                    }
                except Exception as e:
                    last_updates = f"Error: {str(e)}"

                # Check issue_type distribution
                issue_types = conn.execute(text(
                    "SELECT issue_type, COUNT(*) as cnt FROM ps_project_status GROUP BY issue_type ORDER BY cnt DESC"
                )).fetchall()

                # Check how many records pass the Streamlit filter
                filtered_count = conn.execute(text(
                    "SELECT COUNT(*) FROM ps_project_status WHERE client_name IS NOT NULL AND category = 'PS'"
                )).scalar()

                # Get Jira client names and Clockify client names for mapping comparison
                jira_clients = conn.execute(text(
                    "SELECT DISTINCT client_name FROM ps_project_status WHERE client_name IS NOT NULL ORDER BY client_name"
                )).fetchall()
                clockify_clients = conn.execute(text(
                    "SELECT DISTINCT client_name FROM clockify_projects WHERE client_name IS NOT NULL ORDER BY client_name"
                )).fetchall()
                existing_mappings = conn.execute(text(
                    "SELECT ps_client_name, ps_project_name, clockify_client_name, clockify_project_name FROM ps_project_mapping WHERE is_active = TRUE"
                )).fetchall()

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'ps_project_status_count': table_count,
                        'vw_ps_project_status_count': view_count,
                        'sample_data': [dict(row._mapping) for row in sample],
                        'issue_type_distribution': [{'issue_type': r[0], 'count': r[1]} for r in issue_types],
                        'filtered_count_excl_managed_services': filtered_count,
                        'ps_resource_forecasts': forecast_info,
                        'last_updates': last_updates,
                        'jira_client_names': [r[0] for r in jira_clients],
                        'clockify_client_names': [r[0] for r in clockify_clients],
                        'existing_mappings': [dict(row._mapping) for row in existing_mappings]
                    }, default=str)
                }

        # Handle restore_forecasts mode - restore forecast data from history
        if mode == 'restore_forecasts':
            from sqlalchemy import text
            from src.database.config import engine

            snapshot_id = event.get('snapshot_id')

            with engine.begin() as conn:
                if not snapshot_id:
                    # Find the most recent snapshot
                    row = conn.execute(text(
                        "SELECT snapshot_id, COUNT(*) as cnt, ROUND(SUM(forecasted_hours)::numeric,1) as hrs "
                        "FROM ps_resource_forecast_history GROUP BY snapshot_id ORDER BY snapshot_id::int DESC LIMIT 1"
                    )).fetchone()
                    if not row:
                        return {'statusCode': 400, 'body': json.dumps({'error': 'No history snapshots found'})}
                    snapshot_id = row[0]

                # Check current live count
                live_count = conn.execute(text("SELECT COUNT(*) FROM ps_resource_forecasts")).scalar()

                # Restore from history
                result = conn.execute(text("""
                    INSERT INTO ps_resource_forecasts
                        (week_start_date, week_end_date, clockify_user_id, user_name,
                         location, project_name, clockify_project_id, client_name,
                         project_type, pm_name, stage, practice_area,
                         forecasted_hours, actual_hours, comments, created_by,
                         created_at, updated_at)
                    SELECT
                        week_start_date, week_end_date, clockify_user_id, user_name,
                        location, project_name, clockify_project_id, client_name,
                        project_type, pm_name, stage, practice_area,
                        forecasted_hours, actual_hours, comments, created_by,
                        created_at, updated_at
                    FROM ps_resource_forecast_history
                    WHERE snapshot_id = :sid
                    ON CONFLICT (user_name, week_start_date, client_name, project_name) DO UPDATE
                    SET forecasted_hours = EXCLUDED.forecasted_hours,
                        updated_at = NOW()
                """), {'sid': str(snapshot_id)})

                restored = result.rowcount
                new_count = conn.execute(text("SELECT COUNT(*) FROM ps_resource_forecasts")).scalar()

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'snapshot_id': str(snapshot_id),
                    'records_restored': restored,
                    'previous_live_count': live_count,
                    'new_live_count': new_count
                })
            }

        # Handle diagnose_forecasts mode - check forecast data
        if mode == 'diagnose_forecasts':
            from sqlalchemy import text
            from src.database.config import engine

            with engine.connect() as conn:
                # Get date range summary
                date_summary = conn.execute(text(
                    """SELECT week_start_date, COUNT(*) as record_count
                       FROM ps_resource_forecasts
                       GROUP BY week_start_date
                       ORDER BY week_start_date"""
                )).fetchall()

                # Check for duplicates
                duplicates = conn.execute(text(
                    """SELECT user_name, week_start_date, client_name, project_name,
                              COUNT(*) as dup_count
                       FROM ps_resource_forecasts
                       GROUP BY user_name, week_start_date, client_name, project_name
                       HAVING COUNT(*) > 1
                       LIMIT 10"""
                )).fetchall()

                # Get data from the over 40 hours view
                over_40_view = conn.execute(text(
                    """SELECT user_name, week_start_date, week_label, client_name,
                              project_manager, client_hours, total_weekly_hours, client_count
                       FROM vw_forecast_over_40_hours
                       ORDER BY total_weekly_hours DESC, week_start_date, user_name
                       LIMIT 20"""
                )).fetchall()

                # Get detailed breakdown for users over 40
                if over_40_view:
                    first_user = over_40_view[0][0]
                    first_week = over_40_view[0][1]
                    user_detail = conn.execute(text(
                        """SELECT user_name, week_start_date, client_name, project_name,
                                  forecasted_hours, forecast_id
                           FROM ps_resource_forecasts
                           WHERE user_name = :user_name AND week_start_date = :week_date
                           ORDER BY client_name"""
                    ), {"user_name": first_user, "week_date": first_week}).fetchall()
                else:
                    user_detail = []

                # Check forecast history (archived snapshots)
                history_snapshots = conn.execute(text(
                    """SELECT snapshot_id, archived_at,
                              COUNT(*) as record_count,
                              ROUND(SUM(forecasted_hours)::numeric, 1) as total_hours,
                              MIN(week_start_date) as min_week,
                              MAX(week_start_date) as max_week
                       FROM ps_resource_forecast_history
                       GROUP BY snapshot_id, archived_at
                       ORDER BY archived_at DESC
                       LIMIT 10"""
                )).fetchall()

                # Recent forecast import logs
                forecast_imports = conn.execute(text(
                    """SELECT log_id, import_type, status, records_imported, records_updated,
                              started_at, completed_at, error_message
                       FROM import_logs
                       WHERE import_category = 'forecasts'
                       ORDER BY completed_at DESC
                       LIMIT 10"""
                )).fetchall()

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'date_summary': [dict(row._mapping) for row in date_summary],
                        'duplicates': [dict(row._mapping) for row in duplicates],
                        'over_40_view': [dict(row._mapping) for row in over_40_view],
                        'first_user_detail': [dict(row._mapping) for row in user_detail],
                        'history_snapshots': [dict(row._mapping) for row in history_snapshots],
                        'forecast_imports': [dict(row._mapping) for row in forecast_imports],
                    }, default=str)
                }

        # Handle diagnose_free_agents mode - check free agent availability data
        if mode == 'diagnose_free_agents':
            from sqlalchemy import text
            from src.database.config import engine

            with engine.connect() as conn:
                # Free agents in Clockify
                clockify_agents = conn.execute(text("""
                    SELECT name, LOWER(name) AS name_lower,
                           TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\\', '')) AS pod,
                           daily_capacity * 5 AS weekly_capacity
                    FROM clockify_users
                    WHERE status = 'active'
                      AND TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\\', '')) = 'Free Agent'
                    ORDER BY name
                """)).fetchall()

                # Forecast user names for current and next 2 weeks
                forecast_names = conn.execute(text("""
                    SELECT DISTINCT user_name, LOWER(user_name) AS user_name_lower, week_start_date,
                           SUM(forecasted_hours) AS total_hours
                    FROM ps_resource_forecasts
                    WHERE week_start_date >= DATE_TRUNC('week', CURRENT_DATE)::DATE
                      AND week_start_date < DATE_TRUNC('week', CURRENT_DATE)::DATE + INTERVAL '3 weeks'
                    GROUP BY user_name, LOWER(user_name), week_start_date
                    ORDER BY week_start_date, user_name
                """)).fetchall()

                # Unmatched: free agents with no forecast match this week
                unmatched = conn.execute(text("""
                    SELECT cu.name AS clockify_name,
                           COALESCE(fc.user_name, '(no match)') AS forecast_name,
                           COALESCE(fc.total_hours, 0) AS forecasted_hours
                    FROM (
                        SELECT name, LOWER(name) AS name_lower, daily_capacity * 5 AS weekly_capacity
                        FROM clockify_users
                        WHERE status = 'active'
                          AND TRIM(REPLACE(REPLACE(REPLACE(REPLACE(pod_assignment, '{', ''), '}', ''), '"', ''), '\\', '')) = 'Free Agent'
                    ) cu
                    LEFT JOIN (
                        SELECT LOWER(user_name) AS user_name_lower, user_name,
                               SUM(forecasted_hours) AS total_hours
                        FROM ps_resource_forecasts
                        WHERE week_start_date = DATE_TRUNC('week', CURRENT_DATE)::DATE
                        GROUP BY LOWER(user_name), user_name
                    ) fc ON cu.name_lower = fc.user_name_lower
                    ORDER BY cu.name
                """)).fetchall()

                # Actual view output for current week
                view_output = conn.execute(text("""
                    SELECT user_name, weekly_capacity, week_start_date,
                           forecasted_hours, available_hours
                    FROM vw_free_agent_availability
                    WHERE week_start_date = DATE_TRUNC('week', CURRENT_DATE)::DATE
                    ORDER BY user_name
                """)).fetchall()

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'clockify_free_agents': [
                            {'name': r[0], 'name_lower': r[1], 'pod': r[2], 'weekly_capacity': float(r[3]) if r[3] else 0}
                            for r in clockify_agents
                        ],
                        'forecast_names_next_3_weeks': [
                            {'user_name': r[0], 'name_lower': r[1], 'week': str(r[2]), 'total_hours': float(r[3]) if r[3] else 0}
                            for r in forecast_names
                        ],
                        'unmatched_this_week': [
                            {'clockify_name': r[0], 'forecast_name': r[1], 'forecasted_hours': float(r[2]) if r[2] else 0}
                            for r in unmatched
                        ],
                        'view_output_this_week': [
                            {'user': r[0], 'capacity': float(r[1]) if r[1] else 0, 'week': str(r[2]),
                             'forecasted': float(r[3]) if r[3] else 0, 'available': float(r[4]) if r[4] else 0}
                            for r in view_output
                        ],
                    }, default=str)
                }

        # Handle diagnose_pod mode - check pod performance data
        if mode == 'diagnose_pod':
            from sqlalchemy import text
            from src.database.config import engine

            with engine.connect() as conn:
                # Check last week calculation
                week_info = conn.execute(text(
                    """SELECT
                        CURRENT_DATE as today,
                        DATE_TRUNC('week', CURRENT_DATE)::DATE as current_week_start,
                        (DATE_TRUNC('week', CURRENT_DATE)::DATE - 7)::DATE as last_week_start,
                        (DATE_TRUNC('week', CURRENT_DATE)::DATE - 14)::DATE as two_weeks_ago_start"""
                )).fetchone()

                # Check time entries for last week
                last_week_start = week_info[2]
                time_entries = conn.execute(text(
                    """SELECT
                        COUNT(*) as total_entries,
                        COUNT(DISTINCT clockify_user_id) as unique_users,
                        SUM(duration_hours) as total_hours,
                        COUNT(DISTINCT pod_assignment) as pod_count
                    FROM clockify_detailed_time_entries
                    WHERE DATE_TRUNC('week', entry_date)::DATE = :last_week"""
                ), {"last_week": last_week_start}).fetchone()

                # Check pod performance view
                pod_performance = conn.execute(text(
                    """SELECT pod_name, last_week_hours, avg_4_week_hours, last_week_resources
                    FROM vw_pod_performance_analysis
                    ORDER BY pod_name"""
                )).fetchall()

                # Check sample entries by pod for last week
                sample_by_pod = conn.execute(text(
                    """SELECT
                        COALESCE(pod_assignment, 'Unassigned') as pod,
                        COUNT(*) as entry_count,
                        SUM(duration_hours) as hours
                    FROM clockify_detailed_time_entries
                    WHERE DATE_TRUNC('week', entry_date)::DATE = :last_week
                    GROUP BY COALESCE(pod_assignment, 'Unassigned')
                    ORDER BY hours DESC"""
                ), {"last_week": last_week_start}).fetchall()

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'week_info': dict(week_info._mapping),
                        'last_week_entries': dict(time_entries._mapping),
                        'pod_performance_view': [dict(row._mapping) for row in pod_performance],
                        'entries_by_pod': [dict(row._mapping) for row in sample_by_pod]
                    }, default=str)
                }

        # Handle jira_fields mode - discover available Jira fields
        if mode == 'jira_fields':
            from src.integrations.jira_client import JiraClient
            client = JiraClient()

            # Get all field definitions
            all_fields = client.get_field_definitions()
            custom_fields = [
                {'id': f['id'], 'name': f['name'], 'custom': f.get('custom', False)}
                for f in all_fields
                if f.get('custom', False)
            ]

            # Search for link-related fields
            link_fields = [
                f for f in custom_fields
                if any(kw in f['name'].lower() for kw in ['link', 'url', 'board', 'jira'])
            ]

            # Fetch sample issues and survey for board link fields
            sample_issue = {}
            board_link_survey = []
            try:
                from src.database.config import settings as cfg
                project_keys = event.get('project_keys') or cfg.jira_project_keys
                if project_keys:
                    keys_str = ','.join(project_keys) if isinstance(project_keys, list) else project_keys
                    result = client.search_issues(
                        jql=f'project in ({keys_str}) ORDER BY updated DESC',
                        max_results=1
                    )
                    if result.get('issues'):
                        issue = result['issues'][0]
                        fields = issue.get('fields', {})
                        sample_issue = {
                            'key': issue.get('key'),
                            'summary': fields.get('summary'),
                            'custom_fields': {
                                k: v for k, v in fields.items()
                                if k.startswith('customfield_') and v is not None
                            }
                        }

                    # Survey 20 issues for any link-type fields
                    board_link_ids = ['customfield_10816', 'customfield_11528', 'customfield_11814',
                                      'customfield_11046', 'customfield_11047', 'customfield_11045']
                    all_result = client.search_issues(
                        jql=f'project in ({keys_str}) ORDER BY updated DESC',
                        max_results=20
                    )
                    for iss in all_result.get('issues', []):
                        f = iss.get('fields', {})
                        links_found = {}
                        for bid in board_link_ids:
                            val = f.get(bid)
                            if val is not None:
                                links_found[bid] = str(val)[:200]
                        if links_found:
                            board_link_survey.append({
                                'key': iss.get('key'),
                                'summary': str(f.get('summary', ''))[:60],
                                'links': links_found
                            })
            except Exception as e:
                sample_issue = {'error': str(e)}

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'total_custom_fields': len(custom_fields),
                    'link_related_fields': link_fields,
                    'all_custom_fields': sorted(custom_fields, key=lambda x: x['name']),
                    'sample_issue': sample_issue,
                    'board_link_survey': board_link_survey
                }, default=str)
            }

        # Handle jira_import mode
        if mode == 'jira_import':
            from src.integrations.import_jira_data import run_jira_import
            from sqlalchemy import text, create_engine as ce

            project_keys = event.get('project_keys', None)
            full_sync = event.get('full_sync', False)
            week_start_override = event.get('week_start')
            if week_start_override:
                from datetime import date
                week_start_override = date.fromisoformat(week_start_override)

            result = run_jira_import(
                project_keys=project_keys,
                full_sync=full_sync,
                week_start_override=week_start_override
            )

            # Post-import verification: query DB directly to check persistence
            verification = {}
            try:
                db_url = os.environ.get('DATABASE_URL')
                verify_engine = ce(db_url)
                with verify_engine.connect() as conn:
                    ps_count = conn.execute(text("SELECT COUNT(*) FROM ps_project_status")).scalar()
                    mapping_count = conn.execute(text("SELECT COUNT(*) FROM ps_project_mapping WHERE is_active = TRUE")).scalar()
                    jira_count = conn.execute(text("SELECT COUNT(*) FROM jira_projects")).scalar()

                    # Check actual table columns to detect schema mismatch
                    columns = conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'ps_project_status' ORDER BY ordinal_position"
                    )).fetchall()

                    # Check import logs for this run
                    recent_logs = conn.execute(text(
                        "SELECT log_id, import_category, status, records_imported, error_message "
                        "FROM import_logs WHERE import_category IN ('ps_project_status', 'jira_projects', 'ps_project_mapping') "
                        "ORDER BY completed_at DESC LIMIT 6"
                    )).fetchall()

                    verification = {
                        'ps_project_status_count': ps_count,
                        'ps_project_mapping_count': mapping_count,
                        'jira_projects_count': jira_count,
                        'ps_project_status_columns': [c[0] for c in columns],
                        'recent_import_logs': [
                            {'log_id': r[0], 'category': r[1], 'status': r[2], 'imported': r[3], 'error': r[4]}
                            for r in recent_logs
                        ]
                    }
                verify_engine.dispose()
            except Exception as e:
                verification = {'error': str(e)}

            result['verification'] = verification

            # Optionally refresh QuickSight datasets after import
            if event.get('refresh_quicksight', False):
                # Use dataset_ids from event if provided, otherwise refresh all
                qs_dataset_ids = event.get('dataset_ids') or get_all_dataset_ids()
                qs_results = refresh_quicksight_datasets(qs_dataset_ids)
                result['quicksight_refresh'] = qs_results

            # Optionally take KPI snapshot after import (for noon import chaining)
            if event.get('snapshot_kpis', False):
                try:
                    from src.integrations.kpi_snapshot import run as kpi_run
                    kpi_result = kpi_run()
                    result['kpi_snapshot'] = {'week_start_date': str(kpi_result['week_start_date'])}
                    print(f"KPI snapshot taken for {kpi_result['week_start_date']}")
                except Exception as kpi_e:
                    result['kpi_snapshot'] = {'error': str(kpi_e)}
                    print(f"KPI snapshot failed: {kpi_e}")

            return {
                'statusCode': 200,
                'body': json.dumps(result, default=str)
            }

        # Handle run_migration mode - execute SQL migration files
        # Uses master_database_url (postgres superuser) when available so that DDL
        # (CREATE TABLE, CREATE INDEX, etc.) succeeds even if report_user lacks schema CREATE.
        if mode == 'run_migration':
            from pathlib import Path
            from sqlalchemy import create_engine, text

            migration_file = event.get('migration_file', '')
            if not migration_file:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'migration_file parameter required'})
                }

            migrations_dir = Path(__file__).parent / 'database' / 'migrations'
            sql_file = migrations_dir / migration_file

            if not sql_file.exists():
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': f'Migration file not found: {migration_file}'})
                }

            try:
                with open(sql_file, 'r') as f:
                    sql_content = f.read()

                # Prefer master URL (postgres superuser) for DDL operations
                master_url = secrets.get('master_database_url') if secrets else None
                if master_url:
                    print(f"run_migration: using master_database_url for {migration_file}")
                    mig_engine = create_engine(master_url)
                else:
                    print(f"run_migration: master_database_url not available, falling back to report_user")
                    from src.database.config import engine as mig_engine

                with mig_engine.begin() as connection:
                    connection.execute(text(sql_content))

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'status': 'success',
                        'message': f'Migration {migration_file} applied successfully'
                    })
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': str(e)})
                }

        # Handle send_compliance_report mode — send non-compliance email
        if mode == 'send_compliance_report':
            from datetime import date as _date, timedelta
            from sqlalchemy import text
            from src.database.config import engine

            run_type = event.get('run', 'morning')
            if run_type not in ('morning', 'noon', 'afternoon'):
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'Invalid run: {run_type}. Must be "morning", "noon", or "afternoon"'})
                }

            # Data freshness guard — refuse to send if data is more than 3 hours stale
            import datetime as _dt
            from datetime import timezone as _tz
            with engine.connect() as _fc:
                _last_sync = _fc.execute(text(
                    "SELECT MAX(synced_at) FROM clockify_detailed_time_entries"
                )).scalar()

            if _last_sync is None:
                return {
                    'statusCode': 503,
                    'body': json.dumps({'error': 'No Clockify data in database — import has never run'})
                }

            _now = _dt.datetime.now(_tz.utc)
            _sync_utc = _last_sync if _last_sync.tzinfo else _last_sync.replace(tzinfo=_tz.utc)
            _age_hours = (_now - _sync_utc).total_seconds() / 3600

            if _age_hours > 3:
                print(f'[compliance_email] SKIPPING — data is {_age_hours:.1f} hours stale (last sync: {_last_sync})')
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'skipped': True,
                        'reason': f'Data is {_age_hours:.1f} hours stale. Last sync: {str(_last_sync)}. Run import first.',
                        'last_sync': str(_last_sync)
                    })
                }

            with engine.connect() as conn:
                # Query non-compliant users for the most recently completed week
                last_week_start = (_date.today() - timedelta(days=_date.today().weekday() + 7)).isoformat()
                non_compliant = conn.execute(text("""
                    SELECT u.name, u.pod_assignment, u.practice_area,
                           COALESCE(SUM(te.duration_hours), 0) AS hours_submitted
                    FROM clockify_users u
                    LEFT JOIN clockify_detailed_time_entries te
                        ON te.clockify_user_id = u.clockify_user_id
                        AND te.week_start = :week_start
                    WHERE u.status = 'active'
                      AND u.daily_capacity > 0
                      AND COALESCE(u.time_submission, '') != 'No'
                      AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
                      AND COALESCE(u.practice_area, 'Internal') != 'Exempt'
                      AND NOT COALESCE(u.reporting_excluded, FALSE)
                    GROUP BY u.name, u.pod_assignment, u.practice_area
                    HAVING COALESCE(SUM(te.duration_hours), 0) = 0
                    ORDER BY u.pod_assignment, u.name
                """), {'week_start': last_week_start}).fetchall()

                # Query recipients for this run type
                # 'both' is legacy alias for 'all'; 'all' matches every run
                recipients = conn.execute(text("""
                    SELECT email, display_name FROM compliance_report_recipients
                    WHERE is_active = TRUE
                      AND (report_run IN ('both', 'all') OR report_run = :run)
                """), {'run': run_type}).fetchall()

            if not recipients:
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'No active recipients configured'})
                }

            recipient_emails = [r[0] for r in recipients]
            rows_data = [
                {'name': row[0], 'pod': row[1] or '(unassigned)', 'practice': row[2] or '(not set)'}
                for row in non_compliant
            ]

            # Build HTML email
            if rows_data:
                html_rows = ''.join([
                    f'<tr><td>{row["name"]}</td><td>{row["pod"]}</td><td>{row["practice"]}</td></tr>'
                    for row in rows_data
                ])
                body_text = f'<p>Week of {last_week_start} — {len(rows_data)} staff have not submitted time.</p>'
                table_html = f"""<table border="1" cellpadding="6" style="border-collapse:collapse">
                  <tr style="background:#f0f0f0"><th>Name</th><th>POD</th><th>Practice Area</th></tr>
                  {html_rows}
                </table>"""
            else:
                body_text = '<p>All staff have submitted their time for the week.</p>'
                table_html = ''

            html_body = f"""<h2>Timesheet Non-Compliance Report</h2>
{body_text}
{table_html}
<p style="color:#888;font-size:12px">Sent by Cloudelligent Weekly Reporting System</p>"""

            # Send via SES
            subject = f'Missing Time Report — Week of {last_week_start}'
            ses = boto3.client('sesv2', region_name='us-east-1')
            try:
                ses.send_email(
                    FromEmailAddress='reports@cloudelligent.com',
                    Destination={'ToAddresses': recipient_emails},
                    Content={'Simple': {
                        'Subject': {'Data': subject},
                        'Body': {'Html': {'Data': html_body}}
                    }}
                )
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'sent_to': len(recipient_emails),
                        'non_compliant': len(rows_data)
                    })
                }
            except ses.exceptions.ClientError as e:
                print(f"SES error: {str(e)}")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Email service unavailable',
                        'detail': str(e)
                    })
                }

        # Handle analyze_project_health mode — AI Jira vs Clockify analysis
        if mode == 'analyze_project_health':
            from src.integrations.analyze_project_health import run_analysis as run_ph_analysis

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

        # Diagnostic: show which Clockify projects are included in PS/MC reports and via which tier
        if mode == 'diagnose_report_mapping':
            from sqlalchemy import text
            from src.database.config import engine

            results = {}
            with engine.connect() as conn:
                for category in ('PS', 'MC'):
                    if category == 'MC':
                        issue_filter = "p.category = 'MC'"
                        pss_filter   = "pss.category = 'MC'"
                        opp_filter   = "p2.category = 'PS'"
                    else:
                        issue_filter = "p.category = 'PS'"
                        pss_filter   = "pss.category = 'PS'"
                        opp_filter   = "p2.category = 'MC'"

                    rows = conn.execute(text(f"""
                        SELECT
                            te.client_name,
                            te.project_name,
                            CASE
                                WHEN EXISTS (
                                    SELECT 1 FROM ps_project_mapping m
                                    JOIN ps_project_status p
                                      ON LOWER(p.client_name) = LOWER(m.ps_client_name)
                                     AND (m.ps_project_name IS NULL OR LOWER(p.project_name) = LOWER(m.ps_project_name))
                                     AND {issue_filter}
                                     AND NOT (p.status_category = 'Done' AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                                     AND p.status != 'ON HOLD'
                                    WHERE m.is_active = TRUE
                                      AND (m.category IS NULL OR m.category = '{category}')
                                      AND LOWER(te.client_name) = LOWER(m.clockify_client_name)
                                      AND (m.clockify_project_name IS NULL OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
                                ) THEN 'Tier 1 – explicit mapping'
                                ELSE 'Tier 2 – client name match'
                            END AS match_tier,
                            COALESCE(pss.client_name, '') AS ps_client,
                            COALESCE(pss.issue_type, '') AS ps_issue_type,
                            COALESCE(pss.status, '') AS ps_status
                        FROM clockify_detailed_time_entries te
                        LEFT JOIN ps_project_status pss
                               ON LOWER(pss.client_name) = LOWER(te.client_name)
                              AND {pss_filter}
                        WHERE te.entry_date >= CURRENT_DATE - INTERVAL '21 days'
                          AND (
                            EXISTS (
                                SELECT 1 FROM ps_project_mapping m
                                JOIN ps_project_status p
                                  ON LOWER(p.client_name) = LOWER(m.ps_client_name)
                                 AND {issue_filter}
                                 AND NOT (p.status_category = 'Done' AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                                 AND p.status != 'ON HOLD'
                                WHERE m.is_active = TRUE
                                  AND (m.category IS NULL OR m.category = '{category}')
                                  AND LOWER(te.client_name) = LOWER(m.clockify_client_name)
                                  AND (m.clockify_project_name IS NULL OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
                            )
                            OR (
                                EXISTS (
                                    SELECT 1 FROM ps_project_status p
                                    WHERE {issue_filter}
                                      AND NOT (p.status_category = 'Done' AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                                      AND p.status != 'ON HOLD'
                                      AND LOWER(te.client_name) = LOWER(p.client_name)
                                )
                                AND NOT EXISTS (
                                    SELECT 1 FROM ps_project_mapping m
                                    JOIN ps_project_status p2
                                      ON LOWER(p2.client_name) = LOWER(m.ps_client_name)
                                     AND (m.ps_project_name IS NULL OR LOWER(p2.project_name) = LOWER(m.ps_project_name))
                                     AND ({opp_filter})
                                    WHERE m.is_active = TRUE
                                      AND LOWER(te.client_name) = LOWER(m.clockify_client_name)
                                      AND (m.clockify_project_name IS NULL OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
                                )
                            )
                          )
                        GROUP BY te.client_name, te.project_name, match_tier, pss.client_name, pss.issue_type, pss.status
                        ORDER BY match_tier, te.client_name, te.project_name
                    """)).fetchall()

                    results[category] = [
                        {
                            'clockify_client': r[0],
                            'clockify_project': r[1],
                            'match_tier': r[2],
                            'ps_status_client': r[3],
                            'ps_issue_type': r[4],
                            'ps_status': r[5],
                        }
                        for r in rows
                    ]

            return {
                'statusCode': 200,
                'body': json.dumps(results, default=str)
            }

        # Quick customer pod check — returns pod assignments without running full analysis
        if mode == 'mc_v2_customers':
            from src.integrations.mc_v2_audit import _get_mc_customers
            customers = _get_mc_customers()
            return {
                'statusCode': 200,
                'body': json.dumps({'customers': customers}, default=str)
            }

        # Handle mc_v2_audit mode — MC V2 Managed Services methodology progress report
        if mode == 'mc_v2_audit':
            from src.integrations.mc_v2_audit import run_mc_v2_audit
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

        # Handle analyze_forecast mode — Bedrock AI analysis of forecast vs actuals
        if mode == 'analyze_forecast':
            from src.integrations.analyze_forecast import run_forecast_analysis
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


        # Handle test_status_email mode — send a sample status email without running an import
        if mode == 'test_status_email':
            from datetime import date, timedelta
            today = datetime.now()
            last_monday = today - timedelta(days=today.weekday() + 7)
            week_start = last_monday.date()
            week_end = week_start + timedelta(days=6)
            sample_summary = {
                'mode': 'weekly',
                'status': 'SUCCESS',
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
                'status': 'ERRORS',
            }
            send_run_status_email(sample_summary)
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Test status email sent',
                    'summary': {k: str(v) for k, v in sample_summary.items()}
                })
            }

        # Handle debug_clockify mode - show raw Clockify API fields
        if mode == 'debug_clockify':
            from src.integrations.clockify_client import ClockifyClient
            import requests

            client = ClockifyClient()

            # Query users with different status filters
            base_url = f"https://api.clockify.me/api/v1/workspaces/{client.workspace_id}/users"
            headers = {"X-Api-Key": client.api_key, "Content-Type": "application/json"}

            result = {
                'workspace_id': client.workspace_id,
                'queries': {}
            }

            # Query with different status values
            for status_filter in ['ACTIVE', 'INACTIVE', 'PENDING', 'DECLINED', 'ALL']:
                try:
                    all_users = []
                    page = 1
                    while True:
                        params = {"status": status_filter, "page": page, "page-size": 100}
                        response = requests.get(base_url, headers=headers, params=params)
                        response.raise_for_status()
                        users = response.json()
                        if not users:
                            break
                        all_users.extend(users)
                        if len(users) < 100:
                            break
                        page += 1

                    result['queries'][status_filter] = {
                        'count': len(all_users),
                        'sample_names': [u.get('name') for u in all_users[:5]]
                    }

                    # For INACTIVE query, show all users
                    if status_filter == 'INACTIVE':
                        result['queries'][status_filter]['all_inactive_users'] = [
                            {'name': u.get('name'), 'email': u.get('email'), 'status': u.get('status')}
                            for u in all_users
                        ]
                except Exception as e:
                    result['queries'][status_filter] = {'error': str(e)}

            return {
                'statusCode': 200,
                'body': json.dumps(result, default=str)
            }


        # Determine import parameters
        incremental = (mode == 'incremental')
        if mode == 'weekly' and weeks_back is None:
            weeks_back = 1
        elif mode == 'full' and weeks_back is None:
            weeks_back = 52

        print(f"Starting import - Mode: {mode}, Incremental: {incremental}, Weeks: {weeks_back}")

        # ── Initialise run summary (populated as stages complete) ────────────
        from datetime import date as _date, timedelta as _timedelta
        run_errors: list = []
        run_start = datetime.now()
        today_d = run_start.date()
        last_monday = today_d - _timedelta(days=today_d.weekday() + 7)
        run_summary = {
            'mode': mode,
            'status': 'SUCCESS',
            'run_date': run_start,
            'week_start': last_monday if mode == 'weekly' else None,
            'week_end': last_monday + _timedelta(days=6) if mode == 'weekly' else None,
            'users_updated': 0,
            'projects_updated': 0,
            'time_entries_updated': 0,
            'jira_updated': 0,
            'kpi_written': False,
            'kpi_week': '',
            'spice_triggered': 0,
            'compliance_total': 0,
            'compliance_compliant': 0,
            'compliance_noncompliant': 0,
            'errors': run_errors,
        }

        # Apply database views before import to ensure schema is current
        print("Applying database views...")
        try:
            apply_database_views(master_url=secrets.get('master_database_url'))
            print("Database views applied successfully")
        except Exception as e:
            print(f"Warning: View application failed (non-fatal): {str(e)[:100]}")

        # Import here after secrets are set
        from src.integrations.import_clockify_data import run_import

        # Run import
        run_import(weeks_back=weeks_back, incremental=incremental)

        print("Import completed successfully")

        # Run Jira import as part of weekly sync
        print("Starting Jira import...")
        from src.integrations.import_jira_data import run_jira_import
        jira_result = run_jira_import(full_sync=True)
        print(f"Jira import completed: {jira_result}")
        jira_stats = jira_result.get('statistics', {})
        run_summary['jira_updated'] = (
            jira_stats.get('ps_project_status', {}).get('imported', 0)
            + jira_stats.get('ps_project_status', {}).get('updated', 0)
        )

        # Compute KPI weekly snapshot (needs fresh Clockify + Jira data)
        print("Computing weekly KPI snapshot...")
        try:
            from src.integrations.kpi_snapshot import run as kpi_run
            snap_result = kpi_run()
            print(f"KPI snapshot written for {snap_result['week_start_date']}")
            run_summary['kpi_written'] = True
            run_summary['kpi_week'] = str(snap_result['week_start_date'])
            # Update COO analysis week parameter to new snapshot week
            update_analysis_week_parameter(str(snap_result['week_start_date']))
        except Exception as snap_exc:
            print(f"KPI snapshot failed (non-fatal): {snap_exc}")
            run_errors.append(f"KPI snapshot: {snap_exc}")

        # Run AI project health analysis (PS + MC) after data is fresh
        print("Starting AI project health analysis...")
        try:
            from src.integrations.analyze_project_health import run_analysis as run_ph_analysis
            ph_summary = run_ph_analysis(weeks_back=1)
            print(f"AI analysis completed: {ph_summary}")
        except Exception as ph_exc:
            print(f"AI analysis failed (non-fatal): {ph_exc}")
            ph_summary = {'error': str(ph_exc)}
            run_errors.append(f"AI analysis: {ph_exc}")

        # Run MC V2 Audit after project health analysis
        print("Starting MC V2 Audit...")
        try:
            from src.integrations.mc_v2_audit import run_mc_v2_audit
            from datetime import date as _date2, timedelta as _timedelta2
            today2 = _date2.today()
            ws = today2 - _timedelta2(days=today2.weekday())  # this Monday
            audit_summary = run_mc_v2_audit(ws)
            refresh_quicksight_datasets(['mc-v2-audit-by-customer', 'mc-v2-audit-by-phase', 'mc-v2-audit-grid'])
            print(f"MC V2 Audit completed: {audit_summary}")
        except Exception as audit_exc:
            print(f"MC V2 Audit failed (non-fatal): {audit_exc}")
            run_errors.append(f"MC V2 Audit: {audit_exc}")

        # Import escalations from ES Jira board
        print("Starting escalations import...")
        try:
            from src.integrations.import_escalations import run_escalations_import
            esc_summary = run_escalations_import()
            refresh_quicksight_datasets(['escalations-detail', 'escalations-by-customer'])
            print(f"Escalations import completed: {esc_summary}")
        except Exception as esc_exc:
            print(f"Escalations import failed (non-fatal): {esc_exc}")
            run_errors.append(f"Escalations import: {esc_exc}")

        # Get import statistics (import SessionLocal here after secrets are set)
        from src.database.config import SessionLocal
        db = SessionLocal()
        try:
            from src.database.models import ImportLog
            from sqlalchemy import func, text as sql_text2

            last_import = db.query(ImportLog).filter(
                ImportLog.import_category == 'time_entries'
            ).order_by(ImportLog.completed_at.desc()).first()

            from sqlalchemy import text as sql_text

            total_users   = db.execute(sql_text("SELECT COUNT(*) FROM clockify_users")).scalar()
            active_users  = db.execute(sql_text("SELECT COUNT(*) FROM clockify_users WHERE status = 'active'")).scalar()
            total_entries = db.execute(sql_text("SELECT COUNT(*) FROM clockify_detailed_time_entries")).scalar()

            stats = {
                'total_users': total_users,
                'active_users': active_users,
                'total_entries': total_entries,
            }

            run_summary['users_updated'] = total_users or 0
            run_summary['projects_updated'] = db.execute(sql_text("SELECT COUNT(*) FROM clockify_projects")).scalar() or 0

            if last_import:
                stats['last_import'] = {
                    'type': last_import.import_type,
                    'imported': last_import.records_imported,
                    'updated': last_import.records_updated,
                    'completed_at': last_import.completed_at.isoformat() if last_import.completed_at else None
                }
                run_summary['time_entries_updated'] = (last_import.records_imported or 0) + (last_import.records_updated or 0)

            # Compliance snapshot — count active eligible staff vs those who submitted time last week
            if mode == 'weekly':
                try:
                    from datetime import date as _date3, timedelta as _timedelta3
                    lw_start = (_date3.today() - _timedelta3(days=_date3.today().weekday() + 7)).isoformat()
                    comp_rows = db.execute(sql_text("""
                        SELECT
                            COUNT(DISTINCT u.clockify_user_id) AS total,
                            COUNT(DISTINCT te.clockify_user_id) AS submitted
                        FROM clockify_users u
                        LEFT JOIN clockify_detailed_time_entries te
                            ON te.clockify_user_id = u.clockify_user_id
                            AND te.week_start = :lw
                        WHERE u.status = 'active'
                          AND u.daily_capacity > 0
                          AND COALESCE(u.time_submission, '') != 'No'
                          AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
                          AND COALESCE(u.practice_area, 'Internal') != 'Exempt'
                          AND NOT COALESCE(u.reporting_excluded, FALSE)
                    """), {'lw': lw_start}).fetchone()
                    if comp_rows:
                        run_summary['compliance_total']        = comp_rows[0] or 0
                        run_summary['compliance_compliant']    = comp_rows[1] or 0
                        run_summary['compliance_noncompliant'] = (comp_rows[0] or 0) - (comp_rows[1] or 0)
                except Exception as comp_exc:
                    print(f"Compliance snapshot query failed (non-fatal): {comp_exc}")

        finally:
            db.close()

        # Refresh all QuickSight SPICE datasets after successful import
        environment = os.environ.get('ENVIRONMENT', 'production')
        all_dataset_ids = get_all_dataset_ids(environment)
        # Allow override from event, otherwise use all datasets
        refresh_dataset_ids = dataset_ids if dataset_ids else all_dataset_ids
        print(f"Refreshing {len(refresh_dataset_ids)} QuickSight SPICE datasets...")
        qs_results = refresh_quicksight_datasets(refresh_dataset_ids)
        run_summary['spice_triggered'] = len(refresh_dataset_ids)

        # ── Send post-run status email ────────────────────────────────────────
        if run_errors:
            run_summary['status'] = 'ERRORS'
        print(f"Sending run status email (status={run_summary['status']})...")
        send_run_status_email(run_summary)

        # Prepare success message
        message = f"""
Weekly Reporting Import Completed Successfully

Environment: {os.environ.get('ENVIRONMENT', 'unknown')}
Mode: {mode}
Timestamp: {datetime.now().isoformat()}

Clockify Statistics:
- Total Users: {stats.get('total_users', 'N/A')}
- Active Users: {stats.get('active_users', 'N/A')}
- Total Time Entries: {stats.get('total_entries', 'N/A')}

Last Clockify Import:
- Type: {stats.get('last_import', {}).get('type', 'N/A')}
- Records Imported: {stats.get('last_import', {}).get('imported', 'N/A')}
- Records Updated: {stats.get('last_import', {}).get('updated', 'N/A')}

Jira Import:
- Projects: {jira_stats.get('projects', {}).get('imported', 0)} imported, {jira_stats.get('projects', {}).get('updated', 0)} updated
- PS Project Status: {jira_stats.get('ps_project_status', {}).get('imported', 0)} imported, {jira_stats.get('ps_project_status', {}).get('updated', 0)} updated

QuickSight Refresh: {'Triggered' if qs_results else 'Not requested'}
        """

        # Send notification if enabled
        if notify and notification_topic:
            send_sns_notification(
                notification_topic,
                "✅ Weekly Reporting Import Success",
                message
            )

        print(message)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Import completed successfully',
                'timestamp': datetime.now().isoformat(),
                'statistics': stats,
                'quicksight_refresh': qs_results
            })
        }

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


# For local testing
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
