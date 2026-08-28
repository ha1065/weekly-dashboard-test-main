"""
Resource Capacity Forecasting — Weighted Historical Allocation with Constraints

Algorithm:
1. Get last 4 weeks of actuals per person/project from Clockify
2. Calculate each person's avg weekly hours per project (allocation pattern)
3. For each active PS project, forecast 12 weeks forward:
   - Base forecast = person's avg weekly hours on that project
   - Apply decay as project approaches estimated completion
   - Cap cumulative forecast at remaining SOW hours
   - Cap person's total weekly forecast at their capacity
4. Write actuals (4 weeks) + forecasts (12 weeks) to ps_resource_forecast_v2
"""

from datetime import date, timedelta
from sqlalchemy import text


def run_resource_forecast(conn):
    """Main entry point for resource capacity forecasting."""

    current_monday = _current_week_start()
    lookback_start = current_monday - timedelta(weeks=8)
    forecast_end = current_monday + timedelta(weeks=12)

    # Load seasonal factors — only used if seasonal_correction_enabled=1
    # Stored in capacity_model_config as seasonal_factor_week_N keys
    seasonal_factors = {}
    try:
        seasonal_rows = conn.execute(text("""
            SELECT config_key, seasonal_factor FROM capacity_model_config
            WHERE config_key LIKE 'seasonal_factor_week_%'
        """)).fetchall()
        for row in seasonal_rows:
            week_num = row.config_key.replace('seasonal_factor_week_', '')
            seasonal_factors[week_num] = float(row.seasonal_factor or 1.0)
    except Exception:
        conn.rollback()  # recover from aborted transaction before proceeding

    # Clear existing data and regenerate
    conn.execute(text("DELETE FROM ps_resource_forecast_v2"))

    # Step 1: Get 8 weeks of actuals per person/project (S02-02: 8-week lookback, S02-04: practice_area filter)
    actuals = conn.execute(text("""
        SELECT
            te.clockify_user_id,
            u.name AS user_name,
            COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
                u.pod_assignment, '{',''),'}',''),'"',''),'\\','')),''), 'Not Assigned') AS pod_assignment,
            COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
                u.practice_alignment, '{',''),'}',''),'"',''),'\\','')),''), 'Not Assigned') AS practice_alignment,
            u.cloudelligent_title,
            u.skill_area,
            u.level,
            te.client_name,
            te.project_name,
            cp.project_type,
            te.week_start,
            SUM(te.duration_hours) AS hours,
            u.daily_capacity * 5 AS weekly_capacity
        FROM clockify_detailed_time_entries te
        JOIN clockify_users u ON te.clockify_user_id = u.clockify_user_id
        LEFT JOIN clockify_projects cp ON te.clockify_project_id = cp.clockify_project_id
        WHERE te.week_start >= :lookback_start
          AND te.week_start < :current_monday
          AND te.duration_hours > 0
          AND u.status = 'active'
          AND u.daily_capacity > 0
          AND COALESCE(u.time_submission, '') != 'No'
          AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
          AND cp.project_type = 'Professional Services'
          AND u.practice_area IN ('PS', 'Both')
        GROUP BY te.clockify_user_id, u.name, u.pod_assignment, u.practice_alignment,
                 u.cloudelligent_title, u.skill_area, u.level, te.client_name, te.project_name,
                 cp.project_type, te.week_start, u.daily_capacity
    """), {'lookback_start': lookback_start, 'current_monday': current_monday}).fetchall()

    # Step 2: Get active PS projects with SOW and completion dates
    projects = conn.execute(text("""
        SELECT
            v.client_name,
            v.project_name,
            v.type AS project_type,
            v.budget_hours,
            COALESCE(v.actual_hours, 0) AS actual_hours_ytd,
            v.budget_hours - COALESCE(v.actual_hours, 0) AS remaining_sow,
            GREATEST(
                COALESCE(v.revised_completion, '1900-01-01'::DATE),
                COALESCE(v.expected_completion, '1900-01-01'::DATE),
                COALESCE((CURRENT_DATE + (v.days_to_completion || ' days')::INTERVAL)::DATE, '1900-01-01'::DATE)
            ) AS est_completion
        FROM vw_ps_project_status v
        LEFT JOIN (
            SELECT DISTINCT ON (client_name, project_name) client_name, project_name, is_excluded
            FROM ps_project_status
            ORDER BY client_name, project_name, synced_at DESC
        ) pps ON pps.client_name = v.client_name AND pps.project_name = v.project_name
        WHERE v.budget_hours > 0
          AND v.status_category != 'Done'
          AND NOT COALESCE(pps.is_excluded, FALSE)
    """)).fetchall()

    project_map = {}
    for p in projects:
        key = (p.client_name, p.project_name)
        project_map[key] = {
            'type': p.project_type,
            'remaining_sow': float(p.remaining_sow or 0),
            'est_completion': p.est_completion,
            'budget_hours': float(p.budget_hours or 0),
        }

    # Step 2c: Build a set of (client, project) pairs that are Done or excluded.
    # Used in the stub fallback to avoid forecasting completed projects that no
    # longer appear in vw_ps_project_status.
    # We resolve BOTH the raw ps_project_status names AND the Clockify-side names
    # (via ps_project_mapping) so projects with name mismatches are still caught.
    done_projects = set()
    try:
        done_rows = conn.execute(text("""
            WITH done_ps AS (
                SELECT DISTINCT LOWER(TRIM(client_name)) AS ps_client,
                                LOWER(TRIM(project_name)) AS ps_project
                FROM ps_project_status
                WHERE status_category = 'Done'
                   OR COALESCE(is_excluded, FALSE) = TRUE
            )
            -- Clockify-side names from explicit mapping
            SELECT DISTINCT
                LOWER(TRIM(m.clockify_client_name))  AS client,
                LOWER(TRIM(m.clockify_project_name)) AS project
            FROM done_ps dp
            JOIN ps_project_mapping m
              ON LOWER(TRIM(m.ps_client_name)) = dp.ps_client
             AND (m.ps_project_name IS NULL
                  OR LOWER(TRIM(m.ps_project_name)) = dp.ps_project)
            WHERE m.is_active = TRUE
              AND m.clockify_client_name IS NOT NULL

            UNION

            -- Raw ps_project_status names (catches projects with direct Clockify name match)
            SELECT ps_client AS client, ps_project AS project
            FROM done_ps
        """)).fetchall()
        done_projects = {(r[0], r[1]) for r in done_rows if r[0] is not None}
    except Exception:
        conn.rollback()

    # Step 2b: Get Jira ticket velocity per project
    # Maps jira_project_key -> {velocity, remaining_tickets, weeks_remaining}
    jira_velocity = _get_jira_velocity(conn)

    # Load configurable weights from forecast_config table
    config = _load_forecast_config(conn)
    weight_hours = float(config.get('weight_historical_hours', 0.50))
    weight_jira  = float(config.get('weight_jira_velocity',    0.30))
    weight_pm    = float(config.get('weight_pm_forecast',      0.20))
    decay_start  = float(config.get('decay_start_weeks',       2.0))
    seasonal_enabled = int(config.get('seasonal_correction_enabled', 1)) == 1
    # Normalise weights in case they don't sum to 1.0
    total_weight = weight_hours + weight_jira + weight_pm
    if total_weight > 0:
        weight_hours /= total_weight
        weight_jira  /= total_weight
        weight_pm    /= total_weight

    # Load PM forecasts for the blend signal: {(client, project) -> avg weekly hours}
    pm_forecast_map = {}
    pm_rows = conn.execute(text("""
        SELECT project_name, client_name,
               AVG(forecasted_hours) AS avg_weekly_hours
        FROM ps_resource_forecasts
        WHERE week_start_date >= :lookback
          AND week_start_date < :current
        GROUP BY project_name, client_name
    """), {'lookback': current_monday - timedelta(weeks=8), 'current': current_monday}).fetchall()
    for r in pm_rows:
        pm_forecast_map[(r.client_name, r.project_name)] = float(r.avg_weekly_hours or 0)

    # Match Jira projects to our project_map via board link parsing
    board_links = conn.execute(text("""
        SELECT client_name, project_name, jira_board_link
        FROM ps_project_status
        WHERE category = 'PS' AND status_category != 'Done'
          AND NOT COALESCE(is_excluded, FALSE)
          AND jira_board_link IS NOT NULL AND jira_board_link != ''
    """)).fetchall()

    import re
    for row in board_links:
        key = None
        for pk in project_map:
            if pk[0] and row.client_name and row.client_name.lower() in pk[0].lower():
                key = pk
                break

        if not key or key not in project_map:
            continue

        match = re.search(r'/projects/([A-Z0-9]+)', row.jira_board_link)
        if not match:
            match = re.search(r'/browse/([A-Z0-9]+)-', row.jira_board_link)
        if not match:
            continue

        jira_key = match.group(1)
        if jira_key in ('CST', 'PROJ'):
            continue

        jira_data = jira_velocity.get(jira_key)
        est_comp = project_map[key]['est_completion']
        if est_comp and isinstance(est_comp, str):
            est_comp = date.fromisoformat(est_comp[:10])
        hours_weeks = max(0, (est_comp - current_monday).days / 7.0) if est_comp else None

        jira_weeks = None
        if jira_data and jira_data['velocity'] > 0:
            jira_weeks = jira_data['remaining'] / jira_data['velocity']
            project_map[key]['jira_weeks_remaining'] = round(jira_weeks, 1)
            project_map[key]['jira_remaining_tickets'] = jira_data['remaining']
            project_map[key]['jira_velocity_per_week'] = round(jira_data['velocity'], 1)

        # 3-signal weighted blend for est_completion
        if hours_weeks is not None:
            pm_hours = pm_forecast_map.get(key)
            # PM signal: if PM forecasts N hrs/week and remaining SOW is known,
            # weeks = remaining_sow / pm_avg_weekly_hours
            pm_weeks = None
            if pm_hours and pm_hours > 0 and project_map[key]['remaining_sow'] > 0:
                pm_weeks = project_map[key]['remaining_sow'] / pm_hours

            signals = [(weight_hours, hours_weeks)]
            if jira_weeks is not None:
                signals.append((weight_jira, jira_weeks))
            if pm_weeks is not None:
                signals.append((weight_pm, pm_weeks))

            # Re-normalise to available signals
            total_w = sum(w for w, _ in signals)
            blended_weeks = sum((w / total_w) * v for w, v in signals)
            project_map[key]['est_completion'] = current_monday + timedelta(weeks=int(blended_weeks) + 1)

    # Step 3: Insert actuals (S02-02: only last 4 weeks for is_actual=True)
    actual_rows = []
    person_project_hours = {}  # (user_id, client, project) -> [weekly_hours]
    actual_cutoff = current_monday - timedelta(weeks=4)

    for row in actuals:
        key = (row.clockify_user_id, row.client_name, row.project_name)
        person_project_hours.setdefault(key, []).append(float(row.hours))

        # S02-02: Only insert actual rows from last 4 weeks
        if row.week_start >= actual_cutoff:
            actual_rows.append({
                'clockify_user_id': row.clockify_user_id,
                'user_name': row.user_name,
                'pod_assignment': row.pod_assignment,
                'practice_alignment': row.practice_alignment,
                'cloudelligent_title': row.cloudelligent_title,
                'skill_area': row.skill_area,
                'level': row.level,
                'client_name': row.client_name,
                'project_name': row.project_name,
                'project_type': row.project_type,
                'week_start': row.week_start,
                'is_actual': True,
                'hours': float(row.hours),
                'allocation_pct': None,  # calculated below
                'remaining_sow_hours': None,
                'estimated_completion': None,
                'weekly_capacity': float(row.weekly_capacity),
                'capacity_available': None,
                'jira_remaining_tickets': None,
                'jira_velocity_per_week': None,
                'jira_weeks_remaining': None,
            })

    # Step 4: Calculate person averages and generate forecasts
    # Build person metadata from actuals
    person_meta = {}
    for row in actuals:
        if row.clockify_user_id not in person_meta:
            person_meta[row.clockify_user_id] = {
                'user_name': row.user_name,
                'pod_assignment': row.pod_assignment,
                'practice_alignment': row.practice_alignment,
                'cloudelligent_title': row.cloudelligent_title,
                'skill_area': row.skill_area,
                'level': row.level,
                'weekly_capacity': float(row.weekly_capacity),
            }

    # S02-02: Calculate avg hours per person/project using all available weeks
    person_project_avg = {}
    for key, hours_list in person_project_hours.items():
        person_project_avg[key] = sum(hours_list) / len(hours_list)

    # Calculate total avg per person (across all PS projects)
    person_total_avg = {}
    for (uid, client, project), avg in person_project_avg.items():
        person_total_avg[uid] = person_total_avg.get(uid, 0) + avg

    # Generate 12 weeks of forecasts
    forecast_rows = []
    project_cumulative = {}  # (client, project) -> cumulative forecasted hours

    for week_offset in range(12):
        forecast_week = current_monday + timedelta(weeks=week_offset)
        # S02-01: Get seasonal factor for this week (only if enabled)
        week_num = str(forecast_week.isocalendar()[1])
        seasonal_factor = seasonal_factors.get(week_num, 1.0) if seasonal_enabled else 1.0
        
        person_week_total = {}  # uid -> total forecasted this week

        for (uid, client, project), avg_hours in person_project_avg.items():
            # Try exact match first
            proj_key = (client, project)
            if proj_key not in project_map:
                # Try client-only match (handles Clockify vs PS naming differences)
                client_lower = client.lower().strip()
                proj_key = next(
                    (k for k in project_map if k[0].lower().strip() == client_lower),
                    None
                )
                if proj_key is None:
                    # Check if this project is known-done/excluded before using stub.
                    # Completed projects disappear from vw_ps_project_status (Done filter)
                    # but their Clockify hours still appear in the history window — we
                    # must not forecast them.
                    ck = (client.lower().strip(), project.lower().strip())
                    if ck in done_projects:
                        continue  # Project is complete or excluded — skip forecasting
                    # Truly unknown active project — look up completion date from
                    # ps_project_status using fuzzy client name match
                    stub_completion = current_monday + timedelta(weeks=12)
                    try:
                        stub_rows = conn.execute(text("""
                            SELECT GREATEST(
                                COALESCE(revised_completion, '1900-01-01'::DATE),
                                COALESCE(expected_completion, '1900-01-01'::DATE)
                            ) AS best_completion
                            FROM ps_project_status
                            WHERE LOWER(TRIM(client_name)) LIKE :client_pat
                              AND status_category != 'Done'
                              AND NOT COALESCE(is_excluded, FALSE)
                            ORDER BY synced_at DESC LIMIT 1
                        """), {'client_pat': f'%{client.lower().strip()[:8]}%'}).fetchone()
                        if stub_rows and stub_rows[0] and stub_rows[0].year > 1900:
                            stub_completion = stub_rows[0]
                    except Exception:
                        conn.rollback()
                    proj_key = '__stub__'
                    if proj_key not in project_map:
                        project_map[proj_key] = {
                            'type': 'Professional Services',
                            'remaining_sow': 9999,
                            'est_completion': stub_completion,
                            'budget_hours': 9999,
                            'jira_remaining_tickets': None,
                            'jira_velocity_per_week': None,
                            'jira_weeks_remaining': None,
                        }
                    else:
                        # Update stub completion to the latest date seen across stubs
                        existing = project_map[proj_key]['est_completion']
                        if stub_completion > existing:
                            project_map[proj_key]['est_completion'] = stub_completion

            # Use Clockify names for the output rows (consistent with actuals)
            # but use PS view names when matched via client-only lookup
            output_client = client
            output_project = project

            proj = project_map[proj_key]
            meta = person_meta.get(uid)
            if not meta:
                continue

            # Decay factor based on proximity to completion
            est_comp = proj['est_completion']
            if est_comp:
                if isinstance(est_comp, str):
                    est_comp = date.fromisoformat(est_comp[:10])
                weeks_remaining = (est_comp - forecast_week).days / 7.0
                if weeks_remaining <= 0:
                    continue  # Project should be done
                elif weeks_remaining <= 2:
                    decay = weeks_remaining / 2.0
                else:
                    decay = 1.0
            else:
                decay = 1.0

            # Apply decay
            forecasted = avg_hours * decay
            
            # S02-01: Apply seasonal factor after decay and before SOW cap
            forecasted = forecasted * seasonal_factor

            # Check remaining SOW constraint
            cumulative = project_cumulative.get(proj_key, 0)
            remaining = proj['remaining_sow'] - cumulative
            if remaining <= 0:
                continue
            if forecasted > remaining:
                forecasted = remaining

            project_cumulative[proj_key] = cumulative + forecasted

            # Track person's total for capacity check
            person_week_total[uid] = person_week_total.get(uid, 0) + forecasted

            # Allocation %
            total_avg = person_total_avg.get(uid, 1)
            alloc_pct = round((avg_hours / total_avg * 100) if total_avg > 0 else 0, 1)

            forecast_rows.append({
                'clockify_user_id': uid,
                'user_name': meta['user_name'],
                'pod_assignment': meta['pod_assignment'],
                'practice_alignment': meta['practice_alignment'],
                'cloudelligent_title': meta['cloudelligent_title'],
                'skill_area': meta['skill_area'],
                'level': meta['level'],
                'client_name': output_client,
                'project_name': output_project,
                'project_type': proj['type'],
                'week_start': forecast_week,
                'is_actual': False,
                'hours': round(forecasted, 2),
                'allocation_pct': alloc_pct,
                'remaining_sow_hours': round(remaining, 2),
                'estimated_completion': est_comp,
                'weekly_capacity': meta['weekly_capacity'],
                'capacity_available': None,  # calculated after all projects
                'jira_remaining_tickets': proj.get('jira_remaining_tickets'),
                'jira_velocity_per_week': proj.get('jira_velocity_per_week'),
                'jira_weeks_remaining': round(proj.get('jira_weeks_remaining', 0), 1) if proj.get('jira_weeks_remaining') else None,
            })

    # Step 5: Apply capacity constraint and calculate availability
    # Group forecast rows by (uid, week) to compute capacity_available
    from collections import defaultdict
    person_week_hours = defaultdict(float)
    for row in forecast_rows:
        person_week_hours[(row['clockify_user_id'], row['week_start'])] += row['hours']

    for row in forecast_rows:
        key = (row['clockify_user_id'], row['week_start'])
        total_week = person_week_hours[key]
        capacity = row['weekly_capacity']

        # Scale down if over capacity
        if total_week > capacity and total_week > 0:
            scale = capacity / total_week
            row['hours'] = round(row['hours'] * scale, 2)
            person_week_hours[key] = capacity

        row['capacity_available'] = round(capacity - person_week_hours[key], 2)

    # Also set capacity_available on actuals
    actual_person_week = defaultdict(float)
    for row in actual_rows:
        actual_person_week[(row['clockify_user_id'], row['week_start'])] += row['hours']
    for row in actual_rows:
        key = (row['clockify_user_id'], row['week_start'])
        row['capacity_available'] = round(row['weekly_capacity'] - actual_person_week[key], 2)
        total_avg = person_total_avg.get(row['clockify_user_id'], 1)
        pp_avg = person_project_avg.get(
            (row['clockify_user_id'], row['client_name'], row['project_name']), 0)
        row['allocation_pct'] = round((pp_avg / total_avg * 100) if total_avg > 0 else 0, 1)
        proj_key = (row['client_name'], row['project_name'])
        if proj_key in project_map:
            row['remaining_sow_hours'] = round(project_map[proj_key]['remaining_sow'], 2)
            row['estimated_completion'] = project_map[proj_key]['est_completion']

    # Step 6: Add availability rows for ALL PS resources (S02-04: practice_area filter)
    all_ps_resources = conn.execute(text("""
        SELECT
            u.clockify_user_id,
            u.name AS user_name,
            COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
                u.pod_assignment, '{',''),'}',''),'"',''),'\\','')),''), 'Not Assigned') AS pod_assignment,
            COALESCE(NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
                u.practice_alignment, '{',''),'}',''),'"',''),'\\','')),''), 'Not Assigned') AS practice_alignment,
            u.cloudelligent_title,
            u.skill_area,
            u.level,
            u.daily_capacity * 5 AS weekly_capacity
        FROM clockify_users u
        WHERE u.status = 'active'
          AND u.daily_capacity > 0
          AND COALESCE(u.time_submission, '') != 'No'
          AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
          AND u.practice_area IN ('PS', 'Both')
    """)).fetchall()

    # For each PS resource not already in forecast, add rows showing full availability
    forecasted_uids = {row['clockify_user_id'] for row in forecast_rows}
    actual_uids = {row['clockify_user_id'] for row in actual_rows}
    all_known_uids = forecasted_uids | actual_uids

    for resource in all_ps_resources:
        if resource.clockify_user_id not in all_known_uids:
            capacity = float(resource.weekly_capacity)
            for week_offset in range(12):
                forecast_week = current_monday + timedelta(weeks=week_offset)
                forecast_rows.append({
                    'clockify_user_id': resource.clockify_user_id,
                    'user_name': resource.user_name,
                    'pod_assignment': resource.pod_assignment,
                    'practice_alignment': resource.practice_alignment,
                    'cloudelligent_title': resource.cloudelligent_title,
                    'skill_area': resource.skill_area,
                    'level': resource.level,
                    'client_name': 'Unassigned',
                    'project_name': 'Available',
                    'project_type': None,
                    'week_start': forecast_week,
                    'is_actual': False,
                    'hours': 0,
                    'allocation_pct': 0,
                    'remaining_sow_hours': None,
                    'estimated_completion': None,
                    'weekly_capacity': capacity,
                    'capacity_available': capacity,
                    'jira_remaining_tickets': None,
                    'jira_velocity_per_week': None,
                    'jira_weeks_remaining': None,
                })

    # Step 7: Bulk insert
    all_rows = actual_rows + forecast_rows
    if all_rows:
        conn.execute(text("""
            INSERT INTO ps_resource_forecast_v2 (
                clockify_user_id, user_name, pod_assignment, practice_alignment,
                cloudelligent_title, skill_area, level, client_name, project_name, project_type,
                week_start, is_actual, hours, allocation_pct, remaining_sow_hours,
                estimated_completion, weekly_capacity, capacity_available,
                jira_remaining_tickets, jira_velocity_per_week, jira_weeks_remaining, generated_at
            ) VALUES (
                :clockify_user_id, :user_name, :pod_assignment, :practice_alignment,
                :cloudelligent_title, :skill_area, :level, :client_name, :project_name, :project_type,
                :week_start, :is_actual, :hours, :allocation_pct, :remaining_sow_hours,
                :estimated_completion, :weekly_capacity, :capacity_available,
                :jira_remaining_tickets, :jira_velocity_per_week, :jira_weeks_remaining, NOW()
            )
            ON CONFLICT (clockify_user_id, client_name, project_name, week_start)
            DO UPDATE SET
                hours = EXCLUDED.hours,
                allocation_pct = EXCLUDED.allocation_pct,
                remaining_sow_hours = EXCLUDED.remaining_sow_hours,
                estimated_completion = EXCLUDED.estimated_completion,
                capacity_available = EXCLUDED.capacity_available,
                level = EXCLUDED.level,
                jira_remaining_tickets = EXCLUDED.jira_remaining_tickets,
                jira_velocity_per_week = EXCLUDED.jira_velocity_per_week,
                jira_weeks_remaining = EXCLUDED.jira_weeks_remaining,
                generated_at = NOW()
        """), all_rows)

    conn.commit()
    
    # S02-03: Compute PM forecast accuracy
    _compute_pm_accuracy(conn, current_monday)
    
    return {
        'actual_rows': len(actual_rows),
        'forecast_rows': len(forecast_rows),
        'people': len(person_meta),
        'projects': len(project_map),
    }


def _current_week_start():
    """Return the Monday of the current week."""
    today = date.today()
    return today - timedelta(days=today.weekday())


def _get_jira_velocity(conn):
    """
    Query Jira for ticket velocity per project.
    Parses the actual project board key from jira_board_link field.
    Returns dict: client_name -> {velocity, remaining, weeks_remaining}
    """
    import os
    import re
    import requests
    from datetime import datetime, timedelta

    base_url = os.environ.get('JIRA_BASE_URL', '')
    email = os.environ.get('JIRA_API_EMAIL', '')
    token = os.environ.get('JIRA_API_TOKEN', '')

    if not all([base_url, email, token]):
        return {}

    # Get board links from ps_project_status to extract real project keys
    board_links = conn.execute(text("""
        SELECT client_name, project_name, jira_board_link
        FROM ps_project_status
        WHERE category = 'PS'
          AND status_category != 'Done'
          AND NOT COALESCE(is_excluded, FALSE)
          AND jira_board_link IS NOT NULL
          AND jira_board_link != ''
    """)).fetchall()

    # Parse project key from board link URL
    # Patterns: /projects/BGW/boards/..., /browse/PROJ-8, /projects/ADAT/list
    project_board_map = {}  # (client_name, project_name) -> jira_project_key
    for row in board_links:
        link = row.jira_board_link
        match = re.search(r'/projects/([A-Z0-9]+)', link)
        if not match:
            match = re.search(r'/browse/([A-Z0-9]+)-', link)
        if match:
            project_board_map[(row.client_name, row.project_name)] = match.group(1)

    if not project_board_map:
        return {}

    # Get unique project keys to query
    unique_keys = set(project_board_map.values())
    # Remove CST (parent board) and PROJ (5x5x5 umbrella)
    unique_keys.discard('CST')
    unique_keys.discard('PROJ')

    # Load lookback config
    config = _load_forecast_config(conn)
    lookback_weeks = int(config.get('lookback_weeks', 4))

    auth = (email, token)
    velocity_by_key = {}
    cutoff_date = (datetime.now() - timedelta(weeks=lookback_weeks)).strftime('%Y-%m-%d')

    for project_key in unique_keys:
        try:
            # Get remaining (open) tickets
            remaining_resp = requests.get(
                f"{base_url}/rest/api/3/search/jql",
                params={
                    'jql': f'project={project_key} AND status!=Done AND issuetype in (Story,Task,Bug)',
                    'maxResults': 0
                },
                auth=auth, timeout=10
            )
            remaining = remaining_resp.json().get('total', 0) if remaining_resp.ok else 0

            # Get tickets resolved in lookback period
            resolved_resp = requests.get(
                f"{base_url}/rest/api/3/search/jql",
                params={
                    'jql': f'project={project_key} AND status=Done AND resolutiondate>="{cutoff_date}" AND issuetype in (Story,Task,Bug)',
                    'maxResults': 0
                },
                auth=auth, timeout=10
            )
            resolved = resolved_resp.json().get('total', 0) if resolved_resp.ok else 0

            velocity = resolved / float(lookback_weeks)

            if remaining > 0 or velocity > 0:
                velocity_by_key[project_key] = {
                    'velocity': velocity,
                    'remaining': remaining,
                    'weeks_remaining': remaining / velocity if velocity > 0 else 99,
                }
        except Exception:
            continue

    # Map back to (client_name, project_name) -> velocity data
    result = {}
    for (client, project), key in project_board_map.items():
        if key in velocity_by_key:
            result[key] = velocity_by_key[key]

    return result


def _load_forecast_config(conn):
    """Load forecast configuration weights from the database."""
    rows = conn.execute(text("SELECT key, value FROM forecast_config")).fetchall()
    return {row.key: float(row.value) for row in rows}


def _compute_pm_accuracy(conn, current_monday):
    """S02-03: PM forecast accuracy is computed by the KPI snapshot process — skipped here."""
    pass
