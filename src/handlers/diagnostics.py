"""Diagnostics handler module.

Modes handled:
  - diagnose               – diagnose import_logs table
  - diagnose_users         – diagnose user data (status, pods, custom fields)
  - diagnose_contractors   – contractor weekly trend and summary
  - diagnose_dates         – latest entry dates and POD data
  - diagnose_ps            – PS project status data
  - diagnose_forecasts     – forecast data and history
  - diagnose_free_agents   – free agent availability data
  - diagnose_pod           – pod performance data
  - diagnose_report_mapping – show which Clockify projects appear in PS/MC reports
  - debug_secrets          – show what secrets/env vars are set
  - debug_clockify         – show raw Clockify API user counts per status filter
"""

import json
import os
from typing import Any, Dict


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------

def diagnose(event: dict, context: Any, secrets: dict) -> dict:
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

    return {
        'statusCode': 200,
        'body': json.dumps(results, default=str)
    }


# ---------------------------------------------------------------------------
# diagnose_users
# ---------------------------------------------------------------------------

def diagnose_users(event: dict, context: Any, secrets: dict) -> dict:
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

    return {
        'statusCode': 200,
        'body': json.dumps(results, default=str)
    }


# ---------------------------------------------------------------------------
# diagnose_contractors
# ---------------------------------------------------------------------------

def diagnose_contractors(event: dict, context: Any, secrets: dict) -> dict:
    """Diagnose contractor data."""
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


# ---------------------------------------------------------------------------
# diagnose_dates
# ---------------------------------------------------------------------------

def diagnose_dates(event: dict, context: Any, secrets: dict) -> dict:
    """Check latest entry dates and POD data."""
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


# ---------------------------------------------------------------------------
# diagnose_ps
# ---------------------------------------------------------------------------

def diagnose_ps(event: dict, context: Any, secrets: dict) -> dict:
    """Check PS project status data."""
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


# ---------------------------------------------------------------------------
# diagnose_forecasts
# ---------------------------------------------------------------------------

def diagnose_forecasts(event: dict, context: Any, secrets: dict) -> dict:
    """Check forecast data."""
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


# ---------------------------------------------------------------------------
# diagnose_free_agents
# ---------------------------------------------------------------------------

def diagnose_free_agents(event: dict, context: Any, secrets: dict) -> dict:
    """Check free agent availability data."""
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


# ---------------------------------------------------------------------------
# diagnose_pod
# ---------------------------------------------------------------------------

def diagnose_pod(event: dict, context: Any, secrets: dict) -> dict:
    """Check pod performance data."""
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


# ---------------------------------------------------------------------------
# diagnose_report_mapping
# ---------------------------------------------------------------------------

def diagnose_report_mapping(event: dict, context: Any, secrets: dict) -> dict:
    """Show which Clockify projects are included in PS/MC reports and via which tier."""
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


# ---------------------------------------------------------------------------
# debug_secrets
# ---------------------------------------------------------------------------

def debug_secrets(event: dict, context: Any, secrets: dict) -> dict:
    """Show what secrets/env vars are set (masks sensitive values)."""
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


# ---------------------------------------------------------------------------
# debug_clockify
# ---------------------------------------------------------------------------

def debug_clockify(event: dict, context: Any, secrets: dict) -> dict:
    """Show raw Clockify API user counts per status filter."""
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
