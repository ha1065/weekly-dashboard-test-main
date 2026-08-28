"""Import data from Jira into Professional Services project status table."""

import os
import base64
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.database.config import SessionLocal, settings
from src.database.models import JiraProject, PSProjectStatus, PSProjectMapping, ImportLog, ClockifyProject
from src.integrations.jira_client import JiraClient


def parse_date_field(value) -> Optional[datetime]:
    """Parse a date string from Jira custom field."""
    if not value:
        return None
    try:
        if isinstance(value, str):
            # Try date-only format first (YYYY-MM-DD)
            if len(value) == 10:
                return datetime.strptime(value, '%Y-%m-%d').date()
            # Try ISO format
            return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except Exception:
        pass
    return None


def parse_numeric_field(value) -> Optional[Decimal]:
    """Parse a numeric value from Jira custom field."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def get_last_ps_import_date(db: Session) -> Optional[datetime]:
    """Get the last successful PS project status import date."""
    last_log = db.query(ImportLog).filter(
        ImportLog.import_category == 'ps_project_status',
        ImportLog.status == 'success'
    ).order_by(ImportLog.completed_at.desc()).first()

    if last_log and last_log.end_date:
        return last_log.end_date
    return None


def create_import_log(
    db: Session,
    import_type: str,
    category: str,
    start_date: datetime = None,
    end_date: datetime = None
) -> ImportLog:
    """Create an import log entry."""
    log = ImportLog(
        import_type=import_type,
        import_category=category,
        start_date=start_date,
        end_date=end_date,
        started_at=datetime.now()
    )
    db.add(log)
    db.flush()
    return log


def complete_import_log(
    db: Session,
    log: ImportLog,
    imported: int,
    updated: int,
    skipped: int,
    status: str = 'success',
    error: str = None
):
    """Complete an import log entry."""
    log.records_imported = imported
    log.records_updated = updated
    log.records_skipped = skipped
    log.status = status
    log.error_message = error
    log.completed_at = datetime.now()
    db.commit()


def import_jira_projects(db: Session, client: JiraClient) -> dict:
    """Import Jira projects."""
    print("\n  Importing Jira projects...")

    log = create_import_log(db, 'incremental', 'jira_projects')
    imported_count = 0
    updated_count = 0

    try:
        projects = client.get_projects()

        for proj_data in projects:
            project = JiraProject(
                jira_project_id=proj_data['id'],
                project_key=proj_data['key'],
                project_name=proj_data.get('name'),
                lead_name=proj_data.get('lead', {}).get('displayName') if proj_data.get('lead') else None,
                synced_at=datetime.now()
            )

            existing = db.query(JiraProject).filter_by(
                jira_project_id=project.jira_project_id
            ).first()

            if existing:
                existing.project_key = project.project_key
                existing.project_name = project.project_name
                existing.lead_name = project.lead_name
                existing.synced_at = datetime.now()
                updated_count += 1
            else:
                db.add(project)
                imported_count += 1

        db.commit()
        print(f"    Imported {imported_count} new, updated {updated_count} existing")
        complete_import_log(db, log, imported_count, updated_count, 0)

        return {'imported': imported_count, 'updated': updated_count}

    except Exception as e:
        complete_import_log(db, log, 0, 0, 0, 'failed', str(e))
        raise


def _capture_stage_snapshot(db: Session, week_start: date = None) -> None:
    """Upsert this week's PS/MC stage counts into ps_stage_weekly_snapshot."""
    if week_start is None:
        # Monday of the current week
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    db.execute(text("""
        INSERT INTO ps_stage_weekly_snapshot (week_start, stage, category, project_count)
        SELECT
            CAST(:week_start AS date) AS week_start,
            p.status               AS stage,
            p.category,
            COUNT(*)               AS project_count
        FROM ps_project_status p
        WHERE p.status IS NOT NULL
          AND p.category = 'PS'
          AND p.issue_type = 'Emailed request'
          AND p.status_category = 'In Progress'
        GROUP BY p.status, p.category
        ON CONFLICT (week_start, stage, category) DO UPDATE
            SET project_count = EXCLUDED.project_count,
                captured_at   = NOW()
    """), {'week_start': str(week_start)})
    db.commit()
    print(f"    Stage snapshot captured for week {week_start}")


def _capture_mc_ticket_snapshot(db: Session, week_start: date = None) -> None:
    """Snapshot MC customer ticket activity for the current week.
    Uses mc_customer_tickets (real customer board data) when available,
    falls back to ps_project_status CST rows for customers with no board import.
    """
    if week_start is None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    db.execute(text("""
        INSERT INTO mc_ticket_activity_snapshot
            (week_start, customer_name, jira_project_key, total_issues,
             open_issues, in_progress_issues, done_issues,
             updated_this_week, health_overall, synced_at)
        -- Source 1: real customer board tickets
        SELECT
            CAST(:week_start AS date),
            t.customer_name,
            t.jira_project_key,
            COUNT(*)                                                                    AS total_issues,
            COUNT(*) FILTER (WHERE t.status_category NOT IN ('In Progress','Done'))    AS open_issues,
            COUNT(*) FILTER (WHERE t.status_category = 'In Progress')                  AS in_progress_issues,
            COUNT(*) FILTER (WHERE t.status_category = 'Done')                         AS done_issues,
            COUNT(*) FILTER (WHERE t.updated_date >= CAST(:week_start AS timestamp) AND t.updated_date <= CAST(:week_end AS timestamp)) AS updated_this_week,
            (SELECT MODE() WITHIN GROUP (ORDER BY p.health_overall)
             FROM ps_project_status p
             WHERE p.category = 'MC' AND LOWER(p.client_name) = LOWER(t.customer_name))
                                                                                        AS health_overall,
            NOW()
        FROM mc_customer_tickets t
        GROUP BY t.customer_name, t.jira_project_key

        UNION ALL

        -- Source 2: CST-only customers (no board import yet)
        SELECT
            CAST(:week_start AS date),
            p.client_name,
            MAX(p.jira_project_key),
            COUNT(*),
            COUNT(*) FILTER (WHERE p.status_category NOT IN ('In Progress','Done')),
            COUNT(*) FILTER (WHERE p.status_category = 'In Progress'),
            COUNT(*) FILTER (WHERE p.status_category = 'Done'),
            COUNT(*) FILTER (WHERE p.updated_date >= CAST(:week_start AS timestamp) AND p.updated_date <= CAST(:week_end AS timestamp)),
            MODE() WITHIN GROUP (ORDER BY p.health_overall),
            NOW()
        FROM ps_project_status p
        WHERE p.category = 'MC'
          AND NOT COALESCE(p.is_excluded, FALSE)
          AND p.client_name IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM mc_customer_tickets t
              WHERE LOWER(t.customer_name) = LOWER(p.client_name)
          )
        GROUP BY p.client_name

        ON CONFLICT (week_start, customer_name)
        DO UPDATE SET
            total_issues       = EXCLUDED.total_issues,
            open_issues        = EXCLUDED.open_issues,
            in_progress_issues = EXCLUDED.in_progress_issues,
            done_issues        = EXCLUDED.done_issues,
            updated_this_week  = EXCLUDED.updated_this_week,
            health_overall     = EXCLUDED.health_overall,
            synced_at          = NOW()
    """), {'week_start': str(week_start), 'week_end': str(week_end)})
    db.commit()
    print(f"    MC ticket snapshot written for week {week_start}")


def import_ps_project_status(
    db: Session,
    client: JiraClient,
    project_keys: List[str] = None,
    full_sync: bool = False,
    week_start_override: date = None
) -> dict:
    """Import PS Project Status from Jira Service Desk.

    Args:
        db: Database session
        client: Jira API client
        project_keys: Optional list of project keys to filter
        full_sync: If True, sync all issues; else only recent updates
    """
    end_date = datetime.now()

    if full_sync:
        print("\n  Importing PS Project Status (full sync)...")
        import_type = 'full'

        if not project_keys:
            projects = db.query(JiraProject).all()
            project_keys = [p.project_key for p in projects]

        if not project_keys:
            print("    No projects found to sync")
            return {'imported': 0, 'updated': 0}

        issues = client.get_all_project_issues(project_keys)
        start_date = None
    else:
        last_import = get_last_ps_import_date(db)

        if last_import:
            start_date = last_import
            print(f"\n  Importing PS Project Status (since {start_date.strftime('%Y-%m-%d %H:%M')})...")
        else:
            start_date = end_date - timedelta(days=30)
            print(f"\n  Importing PS Project Status (initial - last 30 days)...")

        import_type = 'incremental'
        issues = client.get_issues_updated_since(start_date, project_keys)

    log = create_import_log(db, import_type, 'ps_project_status', start_date, end_date)
    imported_count = 0
    updated_count = 0

    # Compute week_start once for the entire import run
    if week_start_override:
        week_start = week_start_override
    else:
        _today = date.today()
        _current_monday = _today - timedelta(days=_today.weekday())
        week_start = _current_monday - timedelta(weeks=1)

    try:
        print(f"    Processing {len(issues)} issues (week_start={week_start})...")

        for issue_data in issues:
            fields = issue_data.get('fields', {})

            # Parse standard dates
            created_date = None
            updated_date = None
            due_date = None

            if fields.get('created'):
                try:
                    created_date = datetime.fromisoformat(
                        fields['created'].replace('Z', '+00:00')
                    )
                except Exception:
                    pass

            if fields.get('updated'):
                try:
                    updated_date = datetime.fromisoformat(
                        fields['updated'].replace('Z', '+00:00')
                    )
                except Exception:
                    pass

            if fields.get('duedate'):
                try:
                    due_date = datetime.strptime(fields['duedate'], '%Y-%m-%d').date()
                except Exception:
                    pass

            # Extract resolution_date from Jira system field (set automatically on Done/Resolved)
            resolution_date = None
            if fields.get('resolutiondate'):
                try:
                    resolution_date = datetime.fromisoformat(
                        fields['resolutiondate'].replace('Z', '+00:00').replace('+0000', '+00:00')
                    )
                except (ValueError, AttributeError):
                    resolution_date = None

            # week_start is the Monday of the PRIOR week (computed once for the whole import run)

            # Extract custom fields
            custom_fields = client.extract_custom_fields(issue_data)

            # Parse client name and project name from summary
            summary = fields.get('summary', '')
            jira_project_key_val = fields.get('project', {}).get('key', '')

            # Get issue type early — needed for PROJ sub-task filtering and category classification
            issue_type_name = fields.get('issuetype', {}).get('name') if fields.get('issuetype') else None

            # Skip PROJ board issues — PS Delivery tab is CST-only
            if jira_project_key_val == 'PROJ':
                continue

            client_name, project_name = JiraClient.parse_client_project_from_summary(summary)

            # Classify as PS or MC based on issue_type against configurable MC types
            category = 'MC' if issue_type_name in settings.mc_issue_types else 'PS'

            # Create the PSProjectStatus record
            ps_status = PSProjectStatus(
                jira_issue_id=issue_data['id'],
                issue_key=issue_data['key'],
                jira_project_key=fields.get('project', {}).get('key'),

                # Parsed from summary
                client_name=client_name,
                project_name=project_name,
                summary=summary,

                # Standard fields
                status=fields.get('status', {}).get('name'),
                status_category=fields.get('status', {}).get('statusCategory', {}).get('name'),
                priority=fields.get('priority', {}).get('name') if fields.get('priority') else None,
                issue_type=issue_type_name,
                category=category,
                assignee_name=fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
                created_date=created_date,
                updated_date=updated_date,
                due_date=due_date,

                # Project classification
                project_type=custom_fields.get('project_type'),

                # Team members
                project_manager=custom_fields.get('project_manager'),
                solution_architect=custom_fields.get('solution_architect'),
                engineer=custom_fields.get('engineer'),
                account_executive=custom_fields.get('account_executive'),
                csm=custom_fields.get('csm'),

                # Health status fields
                current_health=custom_fields.get('current_health'),
                health_overall=custom_fields.get('health_overall'),
                health_budget=custom_fields.get('health_budget'),
                health_scope=custom_fields.get('health_scope'),
                health_schedule=custom_fields.get('health_schedule'),
                schedule_score=custom_fields.get('schedule_score'),
                escalation=custom_fields.get('escalation'),
                impact=custom_fields.get('impact'),
                risks_blockers=custom_fields.get('risks_blockers'),

                # Budget
                budget_hours=parse_numeric_field(custom_fields.get('budget_hours')),

                # Date fields - Planning
                planned_start=parse_date_field(custom_fields.get('planned_start')),
                planned_end=parse_date_field(custom_fields.get('planned_end')),
                planned_kickoff=parse_date_field(custom_fields.get('planned_kickoff')),
                sow_signing_date=parse_date_field(custom_fields.get('sow_signing_date')),
                expected_completion=parse_date_field(custom_fields.get('expected_completion')),
                revised_completion=parse_date_field(custom_fields.get('revised_completion')),
                resource_assignment_date=parse_date_field(custom_fields.get('resource_assignment_date')),

                # Date fields - Actual completion by phase
                actual_kickoff=parse_date_field(custom_fields.get('actual_kickoff')),
                actual_completion=parse_date_field(custom_fields.get('actual_completion')),
                internal_prep_completion=parse_date_field(custom_fields.get('internal_prep_completion')),
                discover_align_completion=parse_date_field(custom_fields.get('discover_align_completion')),
                design_review_completion=parse_date_field(custom_fields.get('design_review_completion')),
                build_implement_completion=parse_date_field(custom_fields.get('build_implement_completion')),
                launch_enable_completion=parse_date_field(custom_fields.get('launch_enable_completion')),

                # Narrative fields
                project_summary=custom_fields.get('project_summary'),
                what_we_did=custom_fields.get('what_we_did'),
                what_we_will_do_next=custom_fields.get('what_we_will_do_next'),
                mitigation_plan=custom_fields.get('mitigation_plan'),
                slippages=custom_fields.get('slippages'),

                # Links
                sow_link=custom_fields.get('sow_link'),
                jira_board_link=custom_fields.get('jira_board_link'),

                # System date
                resolution_date=resolution_date,

                # Metadata
                week_start=week_start,
                synced_at=datetime.now()
            )

            # Upsert via INSERT ... ON CONFLICT DO UPDATE (FR-CCR-005)
            # Preserves client_name/project_name — these are excluded from the UPDATE
            # to protect manual normalizations applied via migrations.
            db.execute(text("""
                INSERT INTO ps_project_status (
                    jira_issue_id, issue_key, jira_project_key,
                    client_name, project_name, summary,
                    status, status_category, priority, issue_type, category,
                    assignee_name, created_date, updated_date, due_date,
                    project_type, project_manager, solution_architect, engineer,
                    account_executive, csm,
                    current_health, health_overall, health_budget, health_scope,
                    health_schedule, schedule_score, escalation, impact, risks_blockers,
                    budget_hours,
                    planned_start, planned_end, planned_kickoff, sow_signing_date,
                    expected_completion, revised_completion, resource_assignment_date,
                    actual_kickoff, actual_completion, internal_prep_completion,
                    discover_align_completion, design_review_completion,
                    build_implement_completion, launch_enable_completion,
                    project_summary, what_we_did, what_we_will_do_next,
                    mitigation_plan, slippages, sow_link, jira_board_link,
                    resolution_date,
                    week_start, synced_at
                ) VALUES (
                    :jira_issue_id, :issue_key, :jira_project_key,
                    :client_name, :project_name, :summary,
                    :status, :status_category, :priority, :issue_type, :category,
                    :assignee_name, :created_date, :updated_date, :due_date,
                    :project_type, :project_manager, :solution_architect, :engineer,
                    :account_executive, :csm,
                    :current_health, :health_overall, :health_budget, :health_scope,
                    :health_schedule, :schedule_score, :escalation, :impact, :risks_blockers,
                    :budget_hours,
                    :planned_start, :planned_end, :planned_kickoff, :sow_signing_date,
                    :expected_completion, :revised_completion, :resource_assignment_date,
                    :actual_kickoff, :actual_completion, :internal_prep_completion,
                    :discover_align_completion, :design_review_completion,
                    :build_implement_completion, :launch_enable_completion,
                    :project_summary, :what_we_did, :what_we_will_do_next,
                    :mitigation_plan, :slippages, :sow_link, :jira_board_link,
                    :resolution_date,
                    :week_start, NOW()
                )
                ON CONFLICT (jira_issue_id) DO UPDATE SET
                    issue_key                  = EXCLUDED.issue_key,
                    jira_project_key           = EXCLUDED.jira_project_key,
                    summary                    = EXCLUDED.summary,
                    status                     = EXCLUDED.status,
                    status_category            = EXCLUDED.status_category,
                    priority                   = EXCLUDED.priority,
                    issue_type                 = EXCLUDED.issue_type,
                    category                   = EXCLUDED.category,
                    assignee_name              = EXCLUDED.assignee_name,
                    updated_date               = EXCLUDED.updated_date,
                    due_date                   = EXCLUDED.due_date,
                    project_type               = EXCLUDED.project_type,
                    project_manager            = EXCLUDED.project_manager,
                    solution_architect         = EXCLUDED.solution_architect,
                    engineer                   = EXCLUDED.engineer,
                    account_executive          = EXCLUDED.account_executive,
                    csm                        = EXCLUDED.csm,
                    current_health             = EXCLUDED.current_health,
                    health_overall             = EXCLUDED.health_overall,
                    health_budget              = EXCLUDED.health_budget,
                    health_scope               = EXCLUDED.health_scope,
                    health_schedule            = EXCLUDED.health_schedule,
                    schedule_score             = EXCLUDED.schedule_score,
                    escalation                 = EXCLUDED.escalation,
                    impact                     = EXCLUDED.impact,
                    risks_blockers             = EXCLUDED.risks_blockers,
                    budget_hours               = EXCLUDED.budget_hours,
                    planned_start              = EXCLUDED.planned_start,
                    planned_end                = EXCLUDED.planned_end,
                    planned_kickoff            = EXCLUDED.planned_kickoff,
                    sow_signing_date           = EXCLUDED.sow_signing_date,
                    expected_completion        = EXCLUDED.expected_completion,
                    revised_completion         = EXCLUDED.revised_completion,
                    resource_assignment_date   = EXCLUDED.resource_assignment_date,
                    actual_kickoff             = EXCLUDED.actual_kickoff,
                    actual_completion          = EXCLUDED.actual_completion,
                    internal_prep_completion   = EXCLUDED.internal_prep_completion,
                    discover_align_completion  = EXCLUDED.discover_align_completion,
                    design_review_completion   = EXCLUDED.design_review_completion,
                    build_implement_completion = EXCLUDED.build_implement_completion,
                    launch_enable_completion   = EXCLUDED.launch_enable_completion,
                    project_summary            = EXCLUDED.project_summary,
                    what_we_did                = EXCLUDED.what_we_did,
                    what_we_will_do_next       = EXCLUDED.what_we_will_do_next,
                    mitigation_plan            = EXCLUDED.mitigation_plan,
                    slippages                  = EXCLUDED.slippages,
                    sow_link                   = EXCLUDED.sow_link,
                    jira_board_link            = EXCLUDED.jira_board_link,
                    resolution_date            = EXCLUDED.resolution_date,
                    week_start                 = EXCLUDED.week_start,
                    synced_at                  = NOW()
            """), {
                'jira_issue_id':             ps_status.jira_issue_id,
                'issue_key':                 ps_status.issue_key,
                'jira_project_key':          ps_status.jira_project_key,
                'client_name':               ps_status.client_name,
                'project_name':              ps_status.project_name,
                'summary':                   ps_status.summary,
                'status':                    ps_status.status,
                'status_category':           ps_status.status_category,
                'priority':                  ps_status.priority,
                'issue_type':                ps_status.issue_type,
                'category':                  ps_status.category,
                'assignee_name':             ps_status.assignee_name,
                'created_date':              ps_status.created_date,
                'updated_date':              ps_status.updated_date,
                'due_date':                  ps_status.due_date,
                'project_type':              ps_status.project_type,
                'project_manager':           ps_status.project_manager,
                'solution_architect':        ps_status.solution_architect,
                'engineer':                  ps_status.engineer,
                'account_executive':         ps_status.account_executive,
                'csm':                       ps_status.csm,
                'current_health':            ps_status.current_health,
                'health_overall':            ps_status.health_overall,
                'health_budget':             ps_status.health_budget,
                'health_scope':              ps_status.health_scope,
                'health_schedule':           ps_status.health_schedule,
                'schedule_score':            ps_status.schedule_score,
                'escalation':                ps_status.escalation,
                'impact':                    ps_status.impact,
                'risks_blockers':            ps_status.risks_blockers,
                'budget_hours':              ps_status.budget_hours,
                'planned_start':             ps_status.planned_start,
                'planned_end':               ps_status.planned_end,
                'planned_kickoff':           ps_status.planned_kickoff,
                'sow_signing_date':          ps_status.sow_signing_date,
                'expected_completion':       ps_status.expected_completion,
                'revised_completion':        ps_status.revised_completion,
                'resource_assignment_date':  ps_status.resource_assignment_date,
                'actual_kickoff':            ps_status.actual_kickoff,
                'actual_completion':         ps_status.actual_completion,
                'internal_prep_completion':  ps_status.internal_prep_completion,
                'discover_align_completion': ps_status.discover_align_completion,
                'design_review_completion':  ps_status.design_review_completion,
                'build_implement_completion':ps_status.build_implement_completion,
                'launch_enable_completion':  ps_status.launch_enable_completion,
                'project_summary':           ps_status.project_summary,
                'what_we_did':               ps_status.what_we_did,
                'what_we_will_do_next':      ps_status.what_we_will_do_next,
                'mitigation_plan':           ps_status.mitigation_plan,
                'slippages':                 ps_status.slippages,
                'sow_link':                  ps_status.sow_link,
                'jira_board_link':           ps_status.jira_board_link,
                'resolution_date':           ps_status.resolution_date,
                'week_start':                ps_status.week_start,
            })
            imported_count += 1

        db.commit()
        print(f"    Upserted {imported_count} issues")
        complete_import_log(db, log, imported_count, 0, 0)

        # On full sync: remove rows for issues that no longer exist in Jira
        deleted_count = 0
        if full_sync and issues:
            fetched_ids = {str(i['id']) for i in issues}
            stale = db.query(PSProjectStatus).filter(
                PSProjectStatus.jira_project_key.in_(project_keys),
                ~PSProjectStatus.jira_issue_id.in_(fetched_ids)
            ).all()
            if stale:
                stale_keys = [s.issue_key for s in stale]
                print(f"    Removing {len(stale)} deleted Jira issues: {stale_keys}")
                for row in stale:
                    db.delete(row)
                db.commit()
                deleted_count = len(stale)

        # Capture weekly stage snapshot for trend tracking
        _capture_stage_snapshot(db)

        # Capture MC customer ticket activity snapshot
        _capture_mc_ticket_snapshot(db)

        return {'imported': imported_count, 'updated': updated_count, 'deleted': deleted_count}

    except Exception as e:
        complete_import_log(db, log, 0, 0, 0, 'failed', str(e))
        raise


def auto_populate_mappings(db: Session) -> dict:
    """Auto-populate ps_project_mapping by matching Jira client names to Clockify clients.

    Matching strategy (in order):
    1. Case-insensitive exact match
    2. Clockify client name is contained in Jira client name (e.g., "Lawn Doctor" in "Lawn Doctor Migration")
    3. Jira client name is contained in Clockify client name (e.g., "B Squared" in "B Squared Partners")

    Only creates mappings for projects that don't already have one.
    """
    from sqlalchemy import distinct

    print("\n  Auto-populating project mappings...")

    # Get all distinct Clockify client names
    clockify_clients = [
        r[0] for r in db.query(distinct(ClockifyProject.client_name))
        .filter(ClockifyProject.client_name.isnot(None), ClockifyProject.client_name != '')
        .all()
    ]

    if not clockify_clients:
        print("    No Clockify clients found, skipping auto-mapping")
        return {'created': 0, 'skipped': 0}

    # Build lowercase lookup: lowercase -> original name
    ck_lookup = {c.lower(): c for c in clockify_clients}

    # Get all Jira projects (distinct client_name + project_name pairs)
    jira_projects = db.query(
        PSProjectStatus.client_name,
        PSProjectStatus.project_name
    ).filter(
        PSProjectStatus.client_name.isnot(None)
    ).distinct().all()

    # Build lookup of clockify clients already covered by an active mapping.
    # We only create client-level (ps_project_name=NULL) entries to avoid
    # fan-out: per-project rows with the same clockify_client_name cause every
    # time entry for that client to be duplicated N times in views/reports.
    existing = db.query(PSProjectMapping).filter(
        PSProjectMapping.is_active == True
    ).all()
    # Skip auto-creation if ANY active mapping already covers this clockify client
    mapped_ck_clients = {m.clockify_client_name.lower() for m in existing}
    # Also track (ps_client, '') to avoid inserting a client-level row twice
    existing_ps_keys = {m.ps_client_name.lower() for m in existing}

    created = 0
    skipped = 0

    # Deduplicate jira_projects to one entry per distinct ps_client_name
    seen_jira_clients = set()
    for jira_client, _jira_project in jira_projects:
        jira_lower = jira_client.lower()
        if jira_lower in seen_jira_clients or jira_lower in existing_ps_keys:
            skipped += 1
            continue
        seen_jira_clients.add(jira_lower)

        matched_ck_client = None

        # Strategy 1: Exact case-insensitive match
        if jira_lower in ck_lookup:
            matched_ck_client = ck_lookup[jira_lower]
        else:
            # Strategy 2: Clockify name contained in Jira name (longest match first)
            candidates = [(ck_low, ck_orig) for ck_low, ck_orig in ck_lookup.items()
                          if ck_low in jira_lower and len(ck_low) >= 3]
            if candidates:
                matched_ck_client = max(candidates, key=lambda x: len(x[0]))[1]
            else:
                # Strategy 3: Jira name contained in Clockify name
                candidates = [(ck_low, ck_orig) for ck_low, ck_orig in ck_lookup.items()
                              if jira_lower in ck_low and len(jira_lower) >= 3]
                if candidates:
                    matched_ck_client = min(candidates, key=lambda x: len(x[0]))[1]

        if matched_ck_client:
            # Skip if this clockify client is already covered by an existing mapping
            if matched_ck_client.lower() in mapped_ck_clients:
                skipped += 1
                continue
            # Insert client-level mapping (ps_project_name=NULL); ON CONFLICT DO NOTHING
            # so concurrent Lambda invocations or pre-existing rows never cause failures.
            # idx_ps_mapping_unique is an expression index so we must use the full expression.
            db.execute(text("""
                INSERT INTO ps_project_mapping
                    (ps_client_name, ps_project_name, clockify_client_name, clockify_project_name, is_active)
                VALUES (:ps_client, NULL, :ck_client, NULL, true)
                ON CONFLICT (ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name, COALESCE(clockify_project_name, ''))
                DO NOTHING
            """), {"ps_client": jira_client, "ck_client": matched_ck_client})
            mapped_ck_clients.add(matched_ck_client.lower())
            existing_ps_keys.add(jira_lower)
            created += 1
            print(f"    Mapped: {jira_client} -> {matched_ck_client}")

    db.commit()
    print(f"    Auto-mapping complete: {created} created, {skipped} already mapped")

    log = create_import_log(db, 'auto', 'ps_project_mapping')
    complete_import_log(db, log, created, 0, skipped)

    return {'created': created, 'skipped': skipped}


def prepopulate_mappings_from_project_type(db: Session) -> dict:
    """
    Pre-populate ps_project_mapping from clockify_projects using project_type and pod_assignment.

    - project_type = 'Professional Services'
        → category='PS', project-level entry (client_name + project_name)
    - project_type IN ('Managed Cloud', 'Managed Cloud and Managed IT', 'Managed IT', 'FinOps')
        → category='MC', client-level entry (client_name only), pod_assignment from project field

    Skips any entry where the clockify_client_name is already covered by an active mapping
    (for MC) or where the exact (client, project) pair already exists (for PS).
    """
    MC_TYPES = {'Managed Cloud'}
    PS_TYPES = {'Professional Services'}

    # Load active mappings for collision checks
    existing = db.query(PSProjectMapping).filter(PSProjectMapping.is_active == True).all()
    mapped_ck_clients_mc = {m.clockify_client_name.lower() for m in existing if m.category == 'MC'}
    mapped_ps_pairs = {
        (m.clockify_client_name.lower(), (m.clockify_project_name or '').lower())
        for m in existing if m.category == 'PS'
    }

    projects = db.query(ClockifyProject).filter(
        ClockifyProject.archived == False,
        ClockifyProject.project_type.in_(MC_TYPES | PS_TYPES),
        ClockifyProject.client_name.isnot(None),
        ClockifyProject.client_name != '',
    ).all()

    created_ps = created_mc = skipped = 0

    # MC: one entry per distinct client (avoid fan-out)
    seen_mc_clients = set()
    for p in projects:
        if p.project_type not in MC_TYPES:
            continue
        ck_client = p.client_name.strip()
        ck_lower = ck_client.lower()
        if ck_lower in mapped_ck_clients_mc or ck_lower in seen_mc_clients:
            skipped += 1
            continue
        seen_mc_clients.add(ck_lower)
        db.execute(text("""
            INSERT INTO ps_project_mapping
                (ps_client_name, ps_project_name, clockify_client_name, clockify_project_name, category, pod_assignment, is_active)
            VALUES (:ps_client, NULL, :ck_client, NULL, 'MC', :pod, true)
            ON CONFLICT (ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name, COALESCE(clockify_project_name, ''))
            DO NOTHING
        """), {"ps_client": ck_client, "ck_client": ck_client, "pod": p.pod_assignment or None})
        mapped_ck_clients_mc.add(ck_lower)
        created_mc += 1

    # PS: one entry per project
    for p in projects:
        if p.project_type not in PS_TYPES:
            continue
        ck_client = p.client_name.strip()
        ck_project = p.name.strip()
        pair = (ck_client.lower(), ck_project.lower())
        if pair in mapped_ps_pairs:
            skipped += 1
            continue
        db.execute(text("""
            INSERT INTO ps_project_mapping
                (ps_client_name, ps_project_name, clockify_client_name, clockify_project_name, category, pod_assignment, is_active)
            VALUES (:ps_client, :ps_proj, :ck_client, :ck_proj, 'PS', NULL, true)
            ON CONFLICT (ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name, COALESCE(clockify_project_name, ''))
            DO NOTHING
        """), {"ps_client": ck_client, "ps_proj": ck_project, "ck_client": ck_client, "ck_proj": ck_project})
        mapped_ps_pairs.add(pair)
        created_ps += 1

    db.commit()
    print(f"    Pre-populate from project type: {created_ps} PS + {created_mc} MC created, {skipped} skipped")
    return {'created_ps': created_ps, 'created_mc': created_mc, 'skipped': skipped}


def import_mc_customer_boards(db: Session, client: JiraClient) -> dict:
    """Import tickets from individual MC customer Jira project boards.

    Reads jira_board_link from ps_project_status for active MC customers,
    extracts the project key, and imports all non-Done tickets plus any
    tickets updated in the last 14 days (to catch recent closures).

    Only imports from cloudelligent.atlassian.net boards (skips external instances).
    """
    import re

    print("\n  Importing MC customer board tickets...")

    # Get active MC customers with board links (excluding CST and external instances)
    rows = db.execute(text("""
        SELECT DISTINCT
            client_name,
            jira_board_link,
            REGEXP_REPLACE(jira_board_link, '.*/projects/([A-Z][A-Z0-9_]+).*', '\\1') AS project_key
        FROM ps_project_status
        WHERE category = 'MC'
          AND jira_board_link IS NOT NULL
          AND jira_board_link LIKE '%cloudelligent.atlassian.net%'
          AND jira_board_link NOT LIKE '%/projects/CST/%'
          AND status_category != 'Done'
        ORDER BY client_name
    """)).fetchall()

    if not rows:
        print("    No MC customer boards found")
        return {'imported': 0, 'updated': 0}

    cutoff = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    imported_total = updated_total = 0
    fields_list = ['summary', 'status', 'issuetype', 'priority', 'assignee',
                   'customfield_10016', 'created', 'updated', 'resolutiondate']

    for customer_name, board_link, project_key in rows:
        if not project_key or project_key == 'CST':
            continue

        print(f"    Fetching {project_key} ({customer_name})...")
        jql = (
            f'project = "{project_key}" '
            f'AND (statusCategory != Done OR updated >= "{cutoff}") '
            f'ORDER BY updated DESC'
        )

        all_issues = []
        next_page_token = None
        try:
            while True:
                data = client.search_issues(
                    jql=jql,
                    max_results=100,
                    fields=fields_list,
                    next_page_token=next_page_token
                )
                issues = data.get('issues', [])
                all_issues.extend(issues)
                if len(issues) < 100:
                    break
                next_page_token = data.get('nextPageToken')
                if not next_page_token:
                    break
        except Exception as e:
            print(f"      Failed to fetch {project_key}: {e}")
            continue

        imported = updated = 0
        for issue in all_issues:
            f = issue.get('fields', {})
            assignee = (f.get('assignee') or {}).get('displayName')
            created = None
            updated_dt = None
            resolved = None
            try:
                if f.get('created'):
                    created = datetime.fromisoformat(f['created'].replace('Z', '+00:00').replace('+0000', '+00:00'))
                if f.get('updated'):
                    updated_dt = datetime.fromisoformat(f['updated'].replace('Z', '+00:00').replace('+0000', '+00:00'))
                if f.get('resolutiondate'):
                    resolved = datetime.fromisoformat(f['resolutiondate'].replace('Z', '+00:00').replace('+0000', '+00:00'))
            except Exception:
                pass

            db.execute(text("""
                INSERT INTO mc_customer_tickets
                    (jira_issue_id, issue_key, jira_project_key, customer_name,
                     summary, status, status_category, issue_type, priority,
                     assignee_name, story_points, created_date, updated_date,
                     resolution_date, synced_at)
                VALUES
                    (:issue_id, :issue_key, :project_key, :customer,
                     :summary, :status, :status_cat, :issue_type, :priority,
                     :assignee, :sp, :created, :updated, :resolved, NOW())
                ON CONFLICT (jira_issue_id) DO UPDATE SET
                    status          = EXCLUDED.status,
                    status_category = EXCLUDED.status_category,
                    assignee_name   = EXCLUDED.assignee_name,
                    updated_date    = EXCLUDED.updated_date,
                    resolution_date = EXCLUDED.resolution_date,
                    synced_at       = NOW()
            """), {
                'issue_id':   issue['id'],
                'issue_key':  issue['key'],
                'project_key': project_key,
                'customer':   customer_name,
                'summary':    (f.get('summary') or '')[:500],
                'status':     (f.get('status') or {}).get('name'),
                'status_cat': (f.get('status') or {}).get('statusCategory', {}).get('name'),
                'issue_type': (f.get('issuetype') or {}).get('name'),
                'priority':   (f.get('priority') or {}).get('name'),
                'assignee':   assignee,
                'sp':         f.get('customfield_10016'),
                'created':    created,
                'updated':    updated_dt,
                'resolved':   resolved,
            })
            # Track new vs updated (simplified — just count)
            imported += 1

        db.commit()
        imported_total += imported
        print(f"      {project_key}: {imported} tickets synced")

    print(f"    MC customer boards: {imported_total} total tickets synced across {len(rows)} customers")
    return {'imported': imported_total, 'updated': updated_total}


def run_jira_import(
    project_keys: List[str] = None,
    full_sync: bool = False,
    week_start_override: date = None
) -> dict:
    """Run Jira data import for PS Project Status.

    Args:
        project_keys: Optional list of project keys to sync
        full_sync: If True, sync all issues; else only recent updates

    Returns:
        Dict with import statistics
    """
    print("=" * 60)
    print("  Starting PS Project Status Import")
    print("=" * 60)

    # Use configured project keys if not specified
    if not project_keys:
        project_keys = settings.jira_project_keys

    db = SessionLocal()
    client = JiraClient()

    stats = {
        'projects': {'imported': 0, 'updated': 0},
        'ps_project_status': {'imported': 0, 'updated': 0},
        'mc_customer_boards': {'imported': 0, 'updated': 0},
        'ps_project_mapping': {'created': 0, 'skipped': 0}
    }

    try:
        stats['projects'] = import_jira_projects(db, client)
        stats['ps_project_status'] = import_ps_project_status(db, client, project_keys, full_sync, week_start_override)
        stats['mc_customer_boards'] = import_mc_customer_boards(db, client)
        stats['ps_project_mapping'] = auto_populate_mappings(db)

        print("\n" + "=" * 60)
        print("  PS Project Status import completed successfully!")
        print("=" * 60)

        return {'status': 'success', 'statistics': stats}

    except Exception as e:
        print(f"\n  Import failed: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {'status': 'failed', 'error': str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    run_jira_import()
