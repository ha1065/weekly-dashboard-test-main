"""AI-driven project health analysis: Jira estimates vs Clockify actuals.

Uses Amazon Bedrock (Converse API) to estimate per-person effort from Jira
issues worked on last week, then compares against actual Clockify hours
already imported into the database.

Produces two result sets per category (PS / MC):
  - ai_analysis_by_user    — Name, Role, Jira Estimate, Clockify Actual, Delta, Verdict
  - ai_analysis_by_project — Project rollup of the same fields
"""

import base64
import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import boto3
import requests


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _get_week_range(weeks_back: int = 1) -> Tuple[date, date]:
    """Return (monday, sunday) for the target week."""
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    monday = this_monday - timedelta(weeks=weeks_back)
    return monday, monday + timedelta(days=6)


# ---------------------------------------------------------------------------
# Jira helpers
# ---------------------------------------------------------------------------

def _jira_auth() -> Tuple[Dict, str]:
    """Return (headers, base_url) for Jira REST API calls."""
    email = os.environ.get('JIRA_API_EMAIL', '')
    token = os.environ.get('JIRA_API_TOKEN', '')
    base_url = os.environ.get('JIRA_BASE_URL', '').rstrip('/')
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {
        'Authorization': f'Basic {creds}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    return headers, base_url


def _extract_project_key(board_link: str) -> Optional[str]:
    """Extract a Jira project key from a board URL."""
    if not board_link:
        return None
    m = re.search(r'/projects/([A-Z][A-Z0-9_]+)/', board_link)
    return m.group(1) if m else None


def _get_project_names(category: str) -> List[str]:
    """Return display names (client_name – project_name) for active projects in this category."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return []

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            if category == 'MC':
                rows = conn.execute(text("""
                    SELECT client_name, project_name FROM ps_project_status
                    WHERE category = 'MC'
                      AND NOT (status_category = 'Done' AND actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                    ORDER BY client_name, project_name
                """)).fetchall()
            else:
                rows = conn.execute(text("""
                    SELECT client_name, project_name FROM ps_project_status
                    WHERE category = 'PS'
                      AND NOT (status_category = 'Done' AND actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                      AND status != 'ON HOLD'
                    ORDER BY client_name, project_name
                """)).fetchall()
    finally:
        engine.dispose()

    return [
        f"{r[0]} – {r[1]}" if r[1] else r[0]
        for r in rows
    ]


def _get_project_keys(category: str) -> List[str]:
    """Return Jira project keys for the given category from ps_project_status.

    For MC: extracts keys from jira_board_link (each customer has their own
    project board). The jira_project_key column stores 'CST' for all MC rows
    (the CST board key) so it cannot be used for MC.

    For PS: uses jira_project_key directly, falling back to jira_board_link.
    """
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return []

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            if category == 'MC':
                # Always extract from board link — jira_project_key is 'CST' for all MC rows
                rows = conn.execute(text("""
                    SELECT DISTINCT jira_board_link
                    FROM ps_project_status
                    WHERE category = 'MC'
                      AND jira_board_link IS NOT NULL
                      AND jira_board_link NOT LIKE '%/projects/CST/%'
                      AND status_category != 'Done'
                      AND 'cloudelligent.atlassian.net' = ANY(
                          STRING_TO_ARRAY(jira_board_link, '/')
                      )
                """)).fetchall()
                keys: set = set()
                for (board_link,) in rows:
                    extracted = _extract_project_key(board_link)
                    if extracted and extracted != 'CST':
                        keys.add(extracted)
                return list(keys)
            else:  # PS
                rows = conn.execute(text("""
                    SELECT DISTINCT jira_project_key, jira_board_link
                    FROM ps_project_status
                    WHERE category = 'PS'
                      AND (jira_project_key IS NOT NULL OR jira_board_link IS NOT NULL)
                      AND status_category != 'Done'
                """)).fetchall()
                keys = set()
                for jira_key, board_link in rows:
                    if jira_key and jira_key != 'CST':
                        keys.add(jira_key)
                    elif board_link:
                        extracted = _extract_project_key(board_link)
                        if extracted and extracted != 'CST':
                            keys.add(extracted)
                return list(keys)
    finally:
        engine.dispose()


def _extract_week_activity(issue: Dict, start: date, end: date) -> Dict:
    """Extract changelog events and comments that occurred during the analysis week.

    Returns a dict with:
      - updated_this_week: bool — was the issue touched during the week?
      - last_updated: str — ISO date of last update
      - status_changes: list of "Old → New" strings that happened this week
      - comment_count: number of comments added this week
      - update_count: total field changes logged this week
    """
    from datetime import timezone

    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt   = datetime(end.year,   end.month,   end.day, 23, 59, 59, tzinfo=timezone.utc)

    # Last updated timestamp
    updated_str = issue.get('fields', {}).get('updated', '')
    last_updated = updated_str[:10] if updated_str else 'unknown'

    status_changes = []
    update_count = 0

    for history in issue.get('changelog', {}).get('histories', []):
        created_str = history.get('created', '')
        try:
            # Jira timestamps: "2026-03-10T14:23:00.000+0000"
            ts = datetime.fromisoformat(created_str.replace('Z', '+00:00').replace('+0000', '+00:00'))
            if not (start_dt <= ts <= end_dt):
                continue
        except Exception:
            continue

        update_count += 1
        for item in history.get('items', []):
            if item.get('field') == 'status':
                from_str = item.get('fromString', '?')
                to_str   = item.get('toString', '?')
                status_changes.append(f"{from_str} → {to_str}")

    # Count comments added this week
    comment_count = 0
    for comment in issue.get('fields', {}).get('comment', {}).get('comments', []):
        created_str = comment.get('created', '')
        try:
            ts = datetime.fromisoformat(created_str.replace('Z', '+00:00').replace('+0000', '+00:00'))
            if start_dt <= ts <= end_dt:
                comment_count += 1
        except Exception:
            pass

    updated_this_week = update_count > 0 or comment_count > 0

    return {
        'updated_this_week': updated_this_week,
        'last_updated': last_updated,
        'status_changes': status_changes,
        'comment_count': comment_count,
        'update_count': update_count,
    }


def _fetch_jira_issues(project_keys: List[str], start: date, end: date) -> List[Dict]:
    """Fetch active (non-done) Jira issues with assignees, changelog, and comments.

    Fetches all open in-progress tickets plus any updated this week (to catch
    tickets just completed). The changelog (expand=changelog) and comment field
    allow us to see exactly what activity happened during the analysis week,
    giving the AI a precise signal for effort estimation.
    """
    if not project_keys:
        return []

    headers, base_url = _jira_auth()
    if not base_url:
        print("JIRA_BASE_URL not configured — skipping Jira fetch")
        return []

    start_str = start.strftime('%Y-%m-%d')
    keys_str = ', '.join(f'"{k}"' for k in project_keys)
    jql = (
        f'project in ({keys_str}) '
        f'AND (statusCategory != Done OR updated >= "{start_str}") '
        f'AND assignee is not EMPTY '
        f'ORDER BY updated DESC'
    )

    fields = [
        'summary', 'status', 'issuetype', 'assignee', 'priority',
        'customfield_10016',   # story points
        'timeoriginalestimate', 'timespent',
        'project', 'parent', 'updated', 'comment',
    ]

    all_issues: List[Dict] = []
    next_page_token = None

    while True:
        payload: Dict = {
            'jql': jql,
            'maxResults': 100,
            'fields': fields,
            'expand': ['changelog'],
        }
        if next_page_token:
            payload['nextPageToken'] = next_page_token

        try:
            resp = requests.post(
                f"{base_url}/rest/api/3/search/jql",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"Jira API error: {exc}")
            break

        all_issues.extend(data.get('issues', []))

        if data.get('isLast', True):
            break
        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            break

    return all_issues


def _get_email_to_cw_user_map() -> Dict[str, str]:
    """Return {email_lower: te_user_name} mapping via clockify_users.email + time entries."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return {}

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            # Join clockify_users (email) with time entries (user_name as it appears in data)
            rows = conn.execute(text("""
                SELECT DISTINCT cu.email, te.user_name
                FROM clockify_users cu
                JOIN clockify_detailed_time_entries te
                  ON cu.clockify_user_id = te.clockify_user_id
                WHERE cu.email IS NOT NULL AND te.user_name IS NOT NULL
            """)).fetchall()
    finally:
        engine.dispose()

    return {r[0].lower(): r[1] for r in rows if r[0]}


def _match_jira_to_clockify_users(
    issues: List[Dict], cw_users: List[Dict]
) -> Dict[str, List[Dict]]:
    """Group Jira issues by matched Clockify user_name.

    Matching priority:
    1. Email match (Jira assignee.emailAddress vs clockify_users.email)
    2. Token-overlap on display names as fallback

    Returns {clockify_user_name: [issue, ...]}. Issues with no Clockify match
    are filed under the key '__unmatched__'.
    """
    import re

    email_map = _get_email_to_cw_user_map()

    def tokenize(s: str) -> set:
        return {t.lower() for t in re.split(r'[\s\-–/@._]+', s) if len(t) > 2}

    cw_names = [u['user_name'] for u in cw_users]

    def find_cw_match_by_tokens(jira_display: str) -> Optional[str]:
        j_tokens = tokenize(jira_display)
        if not j_tokens:
            return None
        best, best_score = None, 0
        for cw_name in cw_names:
            overlap = len(j_tokens & tokenize(cw_name))
            if overlap > 0 and overlap > best_score:
                best, best_score = cw_name, overlap
        return best

    grouped: Dict[str, List[Dict]] = {}
    for issue in issues:
        assignee_obj = issue.get('fields', {}).get('assignee') or {}
        email = (assignee_obj.get('emailAddress') or '').lower()
        display = assignee_obj.get('displayName', '')

        # Try email match first (most reliable)
        cw_name = email_map.get(email) if email else None
        # Only keep if this Clockify user is in our category user list
        if cw_name and cw_name not in cw_names:
            cw_name = None
        # Fallback: token-overlap on display name
        if not cw_name and display:
            cw_name = find_cw_match_by_tokens(display)

        key = cw_name if cw_name else '__unmatched__'
        grouped.setdefault(key, []).append(issue)

    return grouped


def _format_jira_by_user(
    issues: List[Dict], cw_users: List[Dict],
    week_start: date = None, week_end: date = None,
) -> Tuple[str, Dict[str, float]]:
    """Format Jira issues grouped by Clockify user, showing week activity.

    Each issue shows:
      - whether it was touched during the analysis week (changelog/comments)
      - status transitions that occurred this week
      - last updated date
      - estimated hours (weighted down 50% if not touched this week)

    Returns (formatted_text, {clockify_user_name: estimated_hours}).
    """
    grouped = _match_jira_to_clockify_users(issues, cw_users)
    jira_estimate_hours: Dict[str, float] = {}

    lines = []
    for cw_name, user_issues in sorted(grouped.items()):
        if cw_name == '__unmatched__':
            continue
        total_est = 0.0
        issue_lines = []
        for issue in user_issues:
            f = issue.get('fields', {})
            key = issue.get('key', '')
            summary = f.get('summary', '')
            itype = (f.get('issuetype') or {}).get('name', 'Issue')
            status = (f.get('status') or {}).get('name', '?')
            sp = f.get('customfield_10016') or 0
            orig_secs = f.get('timeoriginalestimate') or 0

            # Base estimate from Jira fields
            if orig_secs:
                base_est = orig_secs / 3600
            elif sp:
                base_est = float(sp) * 4
            else:
                base_est = 2.0

            # Extract week activity from changelog + comments
            activity = _extract_week_activity(issue, week_start, week_end) if week_start else {
                'updated_this_week': True, 'last_updated': 'unknown',
                'status_changes': [], 'comment_count': 0, 'update_count': 0,
            }

            # Weight estimate: tickets not touched this week contribute half
            touched = activity['updated_this_week']
            est = base_est if touched else base_est * 0.5
            total_est += est

            # Build activity summary string
            activity_parts = []
            if touched:
                activity_parts.append('✓ active this week')
                if activity['status_changes']:
                    activity_parts.append('status: ' + ', '.join(activity['status_changes']))
                if activity['comment_count']:
                    activity_parts.append(f"{activity['comment_count']} comment(s)")
                if activity['update_count'] > len(activity['status_changes']):
                    extra = activity['update_count'] - len(activity['status_changes'])
                    activity_parts.append(f"{extra} field update(s)")
            else:
                activity_parts.append(f'⚠ last updated {activity["last_updated"]} (not this week)')

            sp_str = f"{sp} SP" if sp else "no SP"
            est_str = f"{est:.1f}h est" + ('' if touched else ' (halved — inactive)')
            activity_str = ' | '.join(activity_parts)
            issue_lines.append(
                f"    [{key}] {itype} ({status}): {summary} | {sp_str} | {est_str} | {activity_str}"
            )

        active_count = sum(
            1 for i in user_issues
            if (_extract_week_activity(i, week_start, week_end) if week_start else {}).get('updated_this_week', True)
        )
        jira_estimate_hours[cw_name] = round(total_est, 1)
        lines.append(
            f"- {cw_name}: {len(user_issues)} issues ({active_count} active this week), ~{total_est:.1f}h estimated"
        )
        lines.extend(issue_lines)

    if not lines:
        return "No matched Jira activity found.", {}

    return '\n'.join(lines), jira_estimate_hours


# ---------------------------------------------------------------------------
# Clockify helpers (reads from DB — already imported)
# ---------------------------------------------------------------------------

def _fetch_clockify_entries(start: date, end: date, category: str) -> List[Dict]:
    """Fetch Clockify entries for the week, filtered to projects in the given category."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return []

    # Filter Clockify entries to only the projects belonging to this category,
    # using the same two-tier mapping as vw_ps_profitability_2026.
    if category == 'MC':
        issue_type_filter = "p.category = 'MC'"
        opposite_filter   = "p2.category = 'PS'"
    else:
        issue_type_filter = "p.category = 'PS'"
        opposite_filter   = "p2.category = 'MC'"

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(f"""
                SELECT
                    te.user_name,
                    COALESCE(cu.cloudelligent_title, 'Unknown') AS role,
                    COALESCE(te.client_name, '') AS client_name,
                    COALESCE(te.project_name, '') AS project_name,
                    SUM(te.duration_hours) AS hours
                FROM clockify_detailed_time_entries te
                LEFT JOIN clockify_users cu
                       ON te.clockify_user_id = cu.clockify_user_id
                WHERE te.entry_date >= :s AND te.entry_date <= :e
                  AND LOWER(COALESCE(te.project_name, '')) NOT LIKE '%meeting%'
                  AND (
                    -- Tier 1: explicit ps_project_mapping to a category project
                    EXISTS (
                        SELECT 1 FROM ps_project_mapping m
                        JOIN ps_project_status p
                          ON LOWER(p.client_name) = LOWER(m.ps_client_name)
                         AND (m.ps_project_name IS NULL OR LOWER(p.project_name) = LOWER(m.ps_project_name))
                         AND {issue_type_filter}
                         AND NOT (p.status_category = 'Done' AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                         AND p.status != 'ON HOLD'
                        WHERE m.is_active = TRUE
                          AND (m.category IS NULL OR m.category = '{category}')
                          AND LOWER(te.client_name) = LOWER(m.clockify_client_name)
                          AND (m.clockify_project_name IS NULL
                               OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
                    )
                    OR
                    -- Tier 2: direct client name match, excluding entries that are
                    -- mapped to the opposite category via the PS/MC mapping tabs
                    (
                        EXISTS (
                            SELECT 1 FROM ps_project_status p
                            WHERE {issue_type_filter}
                              AND NOT (p.status_category = 'Done' AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                              AND p.status != 'ON HOLD'
                              AND LOWER(te.client_name) = LOWER(p.client_name)
                        )
                        AND NOT EXISTS (
                            SELECT 1 FROM ps_project_mapping m
                            JOIN ps_project_status p2
                              ON LOWER(p2.client_name) = LOWER(m.ps_client_name)
                             AND (m.ps_project_name IS NULL OR LOWER(p2.project_name) = LOWER(m.ps_project_name))
                             AND ({opposite_filter})
                            WHERE m.is_active = TRUE
                              AND LOWER(te.client_name) = LOWER(m.clockify_client_name)
                              AND (m.clockify_project_name IS NULL
                                   OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
                        )
                    )
                  )
                GROUP BY te.user_name, cu.cloudelligent_title, te.client_name, te.project_name
                ORDER BY te.user_name, hours DESC
            """), {'s': start, 'e': end}).fetchall()
    finally:
        engine.dispose()

    return [
        {
            'user_name': r[0],
            'role': r[1],
            'client_name': r[2],
            'project_name': r[3],
            'hours': float(r[4]) if r[4] else 0.0,
        }
        for r in rows
    ]


def _fetch_category_user_hours(start: date, end: date, category: str) -> List[Dict]:
    """Return per-user total hours on category projects for the week (for post-processing)."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return []

    if category == 'MC':
        issue_type_filter = "p.category = 'MC'"
        opposite_filter   = "p2.category = 'PS'"
        practice_filter = ""  # MC: all users who logged to MC projects
    else:
        issue_type_filter = "p.category = 'PS'"
        opposite_filter   = "p2.category = 'MC'"
        # PS: exclude users who are exclusively Managed Cloud Services-aligned
        practice_filter = "AND (cu.practice_alignment IS NULL OR cu.practice_alignment != 'Managed Cloud Services')"

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(f"""
                SELECT
                    te.user_name,
                    COALESCE(cu.cloudelligent_title, 'Unknown') AS role,
                    SUM(te.duration_hours) AS total_hours,
                    -- Primary project = category-mapped client/project with most hours
                    (
                        SELECT CASE
                            WHEN te2.project_name IS NOT NULL AND te2.project_name != te2.client_name
                            THEN COALESCE(te2.client_name, '') || ' – ' || te2.project_name
                            ELSE COALESCE(te2.client_name, te2.project_name, '')
                        END
                        FROM clockify_detailed_time_entries te2
                        WHERE te2.user_name = te.user_name
                          AND te2.entry_date >= :s AND te2.entry_date <= :e
                          AND LOWER(COALESCE(te2.project_name, '')) NOT LIKE '%meeting%'
                          AND EXISTS (
                              SELECT 1 FROM ps_project_mapping m2
                              WHERE m2.is_active = TRUE
                                AND (m2.category IS NULL OR m2.category = '{category}')
                                AND LOWER(te2.client_name) = LOWER(m2.clockify_client_name)
                          )
                        GROUP BY te2.client_name, te2.project_name
                        ORDER BY SUM(te2.duration_hours) DESC
                        LIMIT 1
                    ) AS primary_project
                FROM clockify_detailed_time_entries te
                LEFT JOIN clockify_users cu
                       ON te.clockify_user_id = cu.clockify_user_id
                WHERE te.entry_date >= :s AND te.entry_date <= :e
                  AND LOWER(COALESCE(te.project_name, '')) NOT LIKE '%meeting%'
                  AND (
                    EXISTS (
                        SELECT 1 FROM ps_project_mapping m
                        JOIN ps_project_status p
                          ON LOWER(p.client_name) = LOWER(m.ps_client_name)
                         AND (m.ps_project_name IS NULL OR LOWER(p.project_name) = LOWER(m.ps_project_name))
                         AND {issue_type_filter}
                         AND NOT (p.status_category = 'Done' AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                         AND p.status != 'ON HOLD'
                        WHERE m.is_active = TRUE
                          AND (m.category IS NULL OR m.category = '{category}')
                          AND LOWER(te.client_name) = LOWER(m.clockify_client_name)
                          AND (m.clockify_project_name IS NULL
                               OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
                    )
                    OR
                    (
                        EXISTS (
                            SELECT 1 FROM ps_project_status p
                            WHERE {issue_type_filter}
                              AND NOT (p.status_category = 'Done' AND p.actual_completion < DATE_TRUNC('year', CURRENT_DATE))
                              AND p.status != 'ON HOLD'
                              AND LOWER(te.client_name) = LOWER(p.client_name)
                        )
                        AND NOT EXISTS (
                            SELECT 1 FROM ps_project_mapping m
                            JOIN ps_project_status p2
                              ON LOWER(p2.client_name) = LOWER(m.ps_client_name)
                             AND (m.ps_project_name IS NULL OR LOWER(p2.project_name) = LOWER(m.ps_project_name))
                             AND ({opposite_filter})
                            WHERE m.is_active = TRUE
                              AND LOWER(te.client_name) = LOWER(m.clockify_client_name)
                              AND (m.clockify_project_name IS NULL
                                   OR LOWER(te.project_name) = LOWER(m.clockify_project_name))
                        )
                    )
                  )
                  {practice_filter}
                GROUP BY te.user_name, cu.cloudelligent_title
                ORDER BY total_hours DESC
            """), {'s': start, 'e': end}).fetchall()
    finally:
        engine.dispose()

    return [
        {
            'user_name': r[0],
            'role': r[1],
            'total_hours': float(r[2]) if r[2] else 0.0,
            'primary_project': r[3],
        }
        for r in rows
    ]


def _format_clockify(entries: List[Dict]) -> str:
    """Render Clockify entries grouped by user as plain text."""
    if not entries:
        return "No Clockify time entries found for this period."

    by_user: Dict[str, Dict] = {}
    for e in entries:
        name = e['user_name']
        if name not in by_user:
            by_user[name] = {'role': e['role'], 'total': 0.0, 'projects': {}}
        by_user[name]['total'] += e['hours']
        pk = f"{e['client_name']} / {e['project_name']}" if e['project_name'] else e['client_name']
        by_user[name]['projects'][pk] = by_user[name]['projects'].get(pk, 0.0) + e['hours']

    lines = []
    for user, data in sorted(by_user.items()):
        lines.append(f"- {user} ({data['role']}): {data['total']:.1f}h total")
        for proj, hrs in sorted(data['projects'].items(), key=lambda x: -x[1]):
            lines.append(f"    {proj}: {hrs:.1f}h")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def _load_prompts(category: str) -> List[str]:
    """Load ordered, active prompts for a category from the database."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return []

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT prompt_text
                FROM ai_analysis_prompts
                WHERE category = :cat AND is_active = TRUE
                ORDER BY sequence_order
            """), {'cat': category}).fetchall()
    finally:
        engine.dispose()

    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Bedrock invocation
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a technical delivery analyst with deep experience in cloud engineering, \
professional services delivery, and managed operations.

Your task: analyse Jira work items alongside Clockify time entries to produce an \
honest, technically grounded assessment of whether logged hours reflect the actual \
complexity of the work performed.

## Using Jira update activity to judge effort

Each Jira issue includes:
  - Whether it was "✓ active this week" (changelog or comments during the analysis week)
  - Status transitions that occurred (e.g. "In Progress → In Review")
  - Number of comments and field updates made this week
  - Last updated date for inactive tickets

Use this activity data as the PRIMARY signal for effort:
- Tickets marked "✓ active this week" with status changes indicate real, substantive work
- Multiple status transitions or comments in one week suggest higher effort than the estimate
- Tickets marked "⚠ last updated [old date] (not this week)" were likely NOT worked on;
  treat their contribution to effort as minimal unless Clockify hours clearly contradict this
- Estimates for inactive tickets have already been halved in the pre-processing; use your
  judgement to further adjust based on context

Estimation guidelines:
- Infrastructure changes (VPC, ECS, RDS setup): 4–16 hours depending on complexity
- Code reviews, documentation: 1–3 hours each
- Incidents and P1/P2 tickets: unpredictable, consider severity
- Routine operational tasks (monitoring checks, minor config changes): 0.5–2 hours
- Meetings and coordination: not in Jira but consume real time (factor in 10–20%)
- Status transition In Progress → In Review/Done in one week suggests near-complete ticket
- Consider seniority and role when estimating

Return ONLY valid JSON — no markdown, no prose outside the JSON structure.\
"""

_JSON_SCHEMA = """\
Return exactly this JSON (no surrounding text):
{
  "analysis_week": "YYYY-MM-DD",
  "category": "PS",
  "by_user": [
    {
      "user_name": "Jane Smith",
      "role": "Cloud Engineer",
      "project_name": "Client A - Migration",
      "jira_issues": ["PROJ-123", "PROJ-456"],
      "jira_estimate_hours": 24.0,
      "clockify_actual_hours": 28.5,
      "delta": 4.5,
      "verdict": "On Track",
      "notes": "One concise sentence."
    }
  ],
  "by_project": [
    {
      "project_name": "Client A - Migration",
      "team_size": 3,
      "total_jira_estimate_hours": 72.0,
      "total_clockify_hours": 85.0,
      "total_delta": 13.0,
      "verdict": "Over-logged",
      "notes": "One concise sentence."
    }
  ]
}

Verdict values (use exactly):
  "On Track"           — delta within ±20% of Jira estimate
  "Over-logged"        — Clockify exceeds Jira estimate by > 20%
  "Under-logged"       — Clockify below Jira estimate by > 20%
  "No Jira Activity"   — no Jira issues found for this person/project
  "No Clockify Activity" — no Clockify entries found for this person/project\
"""


def _call_bedrock(user_message: str) -> str:
    """Invoke the Bedrock Converse API and return the raw text response."""
    model_id = os.environ.get(
        'BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )
    region = os.environ.get('AWS_REGION', 'us-east-1')

    bedrock = boto3.client('bedrock-runtime', region_name=region)
    response = bedrock.converse(
        modelId=model_id,
        system=[{'text': _SYSTEM_PROMPT}],
        messages=[{'role': 'user', 'content': [{'text': user_message}]}],
        inferenceConfig={'maxTokens': 8192, 'temperature': 0.1},
    )
    return response['output']['message']['content'][0]['text']


def _parse_json(raw: str) -> Dict:
    """Extract and parse the JSON object from a Bedrock response.

    Handles truncated responses by attempting to close any unclosed
    JSON structures before parsing.
    """
    raw = raw.strip()
    # Strip markdown fences if present
    m = re.search(r'```(?:json)?\s*([\s\S]+?)```', raw)
    if m:
        raw = m.group(1).strip()
    # Find the first '{' in case there is any leading prose
    start = raw.find('{')
    if start > 0:
        raw = raw[start:]

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Truncation recovery: find the last complete project entry and close the JSON
    try:
        last_complete = raw.rfind('},')
        if last_complete == -1:
            last_complete = raw.rfind('}')
        if last_complete > 0:
            truncated = raw[:last_complete + 1].rstrip(',')
            opens = truncated.count('[') - truncated.count(']')
            closes = truncated.count('{') - truncated.count('}')
            truncated += ']' * opens + '}' * closes
            return json.loads(truncated)
    except Exception:
        pass

    # Last resort: return empty structure
    print(f'[analyze_project_health] JSON parse failed, returning empty result. Raw length: {len(raw)}')
    return {'projects': []}


# ---------------------------------------------------------------------------
# Database upsert
# ---------------------------------------------------------------------------

def _upsert(results: Dict, week_start: date, category: str):
    """Delete then re-insert analysis rows for this week+category."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    engine = create_engine(db_url)
    analyzed_at = datetime.now()

    try:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM ai_analysis_by_user WHERE week_start=:ws AND category=:cat"
            ), {'ws': week_start, 'cat': category})
            conn.execute(text(
                "DELETE FROM ai_analysis_by_project WHERE week_start=:ws AND category=:cat"
            ), {'ws': week_start, 'cat': category})

            for row in results.get('by_user', []):
                issues_str = ', '.join(row.get('jira_issues', [])) if row.get('jira_issues') else None
                conn.execute(text("""
                    INSERT INTO ai_analysis_by_user
                        (week_start, category, project_name, user_name, role,
                         jira_issues, jira_estimate_hours, clockify_actual_hours,
                         delta, verdict, notes, analyzed_at)
                    VALUES
                        (:ws, :cat, :proj, :user, :role,
                         :issues, :je, :ca, :delta, :verdict, :notes, :at)
                """), {
                    'ws': week_start, 'cat': category,
                    'proj': row.get('project_name'),
                    'user': row.get('user_name', ''),
                    'role': row.get('role', ''),
                    'issues': issues_str,
                    'je': row.get('jira_estimate_hours'),
                    'ca': row.get('clockify_actual_hours'),
                    'delta': row.get('delta'),
                    'verdict': row.get('verdict', ''),
                    'notes': row.get('notes', ''),
                    'at': analyzed_at,
                })

            for row in results.get('by_project', []):
                conn.execute(text("""
                    INSERT INTO ai_analysis_by_project
                        (week_start, category, project_name, team_size,
                         total_jira_estimate_hours, total_clockify_hours,
                         total_delta, verdict, notes, analyzed_at)
                    VALUES
                        (:ws, :cat, :proj, :ts, :je, :ca, :delta, :verdict, :notes, :at)
                """), {
                    'ws': week_start, 'cat': category,
                    'proj': row.get('project_name', ''),
                    'ts': row.get('team_size'),
                    'je': row.get('total_jira_estimate_hours'),
                    'ca': row.get('total_clockify_hours'),
                    'delta': row.get('total_delta'),
                    'verdict': row.get('verdict', ''),
                    'notes': row.get('notes', ''),
                    'at': analyzed_at,
                })
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Per-category runner
# ---------------------------------------------------------------------------

def _run_category(category: str, monday: date, sunday: date) -> Dict:
    """Run the full pipeline for one category; return the parsed result dict."""
    print(f"[{category}] Loading prompts from DB...")
    prompts = _load_prompts(category)
    if not prompts:
        print(f"[{category}] No active prompts — skipping")
        return {}

    print(f"[{category}] Fetching project names and Jira project keys...")
    project_names = _get_project_names(category)
    print(f"[{category}] {len(project_names)} known projects")
    project_keys = _get_project_keys(category)
    print(f"[{category}] Project keys: {project_keys}")

    print(f"[{category}] Fetching Jira issues {monday} → {sunday}...")
    jira_issues = _fetch_jira_issues(project_keys, monday, sunday)
    print(f"[{category}] {len(jira_issues)} Jira issues")

    print(f"[{category}] Fetching Clockify entries from DB...")
    clockify_entries = _fetch_clockify_entries(monday, sunday, category)
    print(f"[{category}] {len(clockify_entries)} Clockify entry rows")

    print(f"[{category}] Fetching per-user category hours for post-processing...")
    category_user_hours = _fetch_category_user_hours(monday, sunday, category)
    print(f"[{category}] {len(category_user_hours)} users with {category} hours")

    week_label = f"{monday.strftime('%b %d')} – {sunday.strftime('%b %d, %Y')}"
    instructions = '\n\n'.join(f"{i + 1}. {p}" for i, p in enumerate(prompts))

    known_projects_str = '\n'.join(f"- {p}" for p in project_names)

    # Pre-match Jira issues to Clockify users in Python so the AI gets clean
    # per-user Jira data rather than a raw list it has to name-match itself.
    jira_by_user_str, jira_estimate_map = _format_jira_by_user(jira_issues, category_user_hours, monday, sunday)

    user_message = f"""## Analysis Instructions

{instructions}

## Context
- Week: {week_label}
- Category: {category} ({"Professional Services" if category == "PS" else "Managed Cloud"})

## Known {category} Projects (include ALL of these in by_project, even if no activity)

{known_projects_str}

## Current Jira Assignments (all open tickets, grouped by team member)

{jira_by_user_str}

## Clockify Time Entries Last Week ({category} projects only)

{_format_clockify(clockify_entries)}

{_JSON_SCHEMA}"""

    print(f"[{category}] Calling Bedrock ({os.environ.get('BEDROCK_MODEL_ID', 'default model')})...")
    raw = _call_bedrock(user_message)
    print(f"[{category}] Response: {len(raw)} chars")

    result = _parse_json(raw)

    # Post-process: normalize AI project names to canonical names, then fill
    # gaps for any canonical project the AI omitted entirely.
    #
    # The AI uses abbreviated names from Jira/Clockify (e.g. "EMR Bear") while
    # our canonical list has "Client – Project" format ("EMR Bear – Migration…").
    # We match by checking whether all significant tokens (>3 chars) in the AI
    # name appear in the canonical name (case-insensitive).

    def _tokenize(s: str) -> set:
        import re
        return {t.lower() for t in re.split(r'[\s\-–/]+', s) if len(t) > 3}

    def _find_canonical(ai_name: str, canonicals: List[str]) -> Optional[str]:
        ai_tokens = _tokenize(ai_name)
        if not ai_tokens:
            return None
        best, best_score = None, 0
        for c in canonicals:
            c_tokens = _tokenize(c)
            overlap = len(ai_tokens & c_tokens)
            # Require ALL AI tokens to match, and at least one meaningful token
            if overlap == len(ai_tokens) and overlap > best_score:
                best, best_score = c, overlap
        return best

    canonical_set = set(project_names)
    matched_canonicals: set = set()
    kept_rows = []

    for row in result.get('by_project', []):
        ai_name = row.get('project_name', '').strip()
        if ai_name in canonical_set:
            matched_canonicals.add(ai_name)
            kept_rows.append(row)
        else:
            canon = _find_canonical(ai_name, project_names)
            if canon:
                row['project_name'] = canon
                matched_canonicals.add(canon)
                kept_rows.append(row)
            # No canonical match → discard (e.g. ON HOLD project still in Jira/Clockify)

    result['by_project'] = kept_rows

    # Fill in canonical projects the AI omitted entirely
    filled = 0
    for name in project_names:
        if name not in matched_canonicals:
            result.setdefault('by_project', []).append({
                'project_name': name,
                'team_size': 0,
                'total_jira_estimate_hours': 0.0,
                'total_clockify_hours': 0.0,
                'total_delta': 0.0,
                'verdict': 'No Activity',
                'notes': 'No Jira or Clockify activity this week.',
            })
            filled += 1

    ai_count = len(result.get('by_project', [])) - filled
    print(f"[{category}] by_project after fill: {len(result.get('by_project', []))} rows ({ai_count} from AI, {filled} filled)")

    # Post-process by_user: Jira assignee display names (used by AI) rarely
    # match Clockify user_names exactly. Use token-overlap matching to map AI
    # rows to canonical Clockify names, then fill any Clockify user the AI missed.
    cw_user_map = {u['user_name']: u for u in category_user_hours}
    cw_user_names = list(cw_user_map.keys())

    def _find_user_match(ai_name: str) -> Optional[str]:
        ai_tokens = _tokenize(ai_name)
        if not ai_tokens:
            return None
        best, best_score = None, 0
        for cw_name in cw_user_names:
            cw_tokens = _tokenize(cw_name)
            overlap = len(ai_tokens & cw_tokens)
            if overlap > 0 and overlap > best_score:
                best, best_score = cw_name, overlap
        return best

    matched_cw_users: set = set()
    normalized_by_user = []
    for row in result.get('by_user', []):
        ai_name = row.get('user_name', '').strip()
        cw_match = _find_user_match(ai_name)
        if cw_match:
            u = cw_user_map[cw_match]
            row['user_name'] = cw_match
            row['role'] = u['role']
            row['clockify_actual_hours'] = u['total_hours']
            row['delta_hours'] = row.get('jira_estimate_hours', 0.0) - u['total_hours']
            if not row.get('project_name'):
                row['project_name'] = u.get('primary_project')
            matched_cw_users.add(cw_match)
        normalized_by_user.append(row)

    result['by_user'] = normalized_by_user

    user_filled = 0
    for u in category_user_hours:
        if u['user_name'] not in matched_cw_users:
            jira_est = jira_estimate_map.get(u['user_name'], 0.0)
            has_jira = jira_est > 0
            result['by_user'].append({
                'user_name': u['user_name'],
                'role': u['role'],
                'project_name': u.get('primary_project'),
                'jira_estimate_hours': jira_est,
                'clockify_actual_hours': u['total_hours'],
                'delta_hours': jira_est - u['total_hours'],
                'verdict': 'Needs Review' if has_jira else 'No Jira Activity',
                'notes': (
                    f"Matched {jira_est:.1f}h of Jira estimated work; logged {u['total_hours']:.1f}h in Clockify."
                    if has_jira else
                    f"Logged {u['total_hours']:.1f}h to {category} projects but no Jira issues found this week."
                ),
            })
            user_filled += 1
    print(f"[{category}] by_user after fill: {len(result.get('by_user', []))} rows ({len(normalized_by_user) - user_filled} from AI, {user_filled} filled)")

    result['category'] = category
    result['analysis_week'] = str(monday)
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_analysis(weeks_back: int = 1, week_start: date = None) -> Dict:
    """Run the AI project health analysis for both PS and MC.

    Args:
        week_start: Explicit Monday date to analyse (preferred). If omitted,
                    falls back to weeks_back offset from today.
        weeks_back: 1 = last week (default), 2 = two weeks ago, etc.

    Returns:
        Summary dict with per-category counts / errors.
    """
    if week_start is not None:
        monday = week_start
        sunday = monday + timedelta(days=6)
    else:
        monday, sunday = _get_week_range(weeks_back)
    print(f"AI project health analysis: {monday} → {sunday}")

    summary: Dict = {'week_start': str(monday), 'ps': {}, 'mc': {}}

    for category in ('PS', 'MC'):
        try:
            result = _run_category(category, monday, sunday)
            if not result:
                summary[category.lower()] = {'skipped': 'no prompts configured'}
                continue

            _upsert(result, monday, category)
            summary[category.lower()] = {
                'by_user_rows': len(result.get('by_user', [])),
                'by_project_rows': len(result.get('by_project', [])),
            }
            print(
                f"[{category}] Done — "
                f"{summary[category.lower()]['by_user_rows']} user rows, "
                f"{summary[category.lower()]['by_project_rows']} project rows"
            )
        except Exception as exc:
            print(f"[{category}] FAILED: {exc}")
            summary[category.lower()] = {'error': str(exc)}

    return summary
