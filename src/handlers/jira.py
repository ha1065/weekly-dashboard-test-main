"""Jira handler module.

Modes handled:
  - jira_import   – run full/partial Jira → DB sync
  - jira_fields   – discover available Jira fields (diagnostic)
"""

import json
import os
from typing import Any


def jira_import(event: dict, context: Any, secrets: dict) -> dict:
    """Run Jira PS/MC project import.

    event keys:
      project_keys       list[str] | None
      full_sync          bool (default False)
      week_start         ISO date str | None
      refresh_quicksight bool (default False)
      dataset_ids        list[str] | None
      snapshot_kpis      bool (default False)
    """
    # Heavy imports inside function — secrets must already be in os.environ
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
        from src.handlers.quicksight import get_all_dataset_ids, refresh_quicksight_datasets
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


def jira_fields(event: dict, context: Any, secrets: dict) -> dict:
    """Discover available Jira fields — useful for field ID mapping diagnostics."""
    # Heavy imports inside function
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
