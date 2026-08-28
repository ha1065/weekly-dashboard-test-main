"""Import escalation data from the Jira ES project board."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.database.config import SessionLocal
from src.integrations.jira_client import JiraClient

_ES_PROJECT = 'ES'
_EPIC_LINK_FIELD = 'customfield_10014'

_FIELDS = [
    'summary', 'description', 'status', 'priority', 'issuetype',
    'assignee', 'reporter', 'created', 'updated',
    'resolutiondate', _EPIC_LINK_FIELD,
]


def _extract_description(raw) -> str | None:
    """Return plain text from a Jira description (string or ADF object)."""
    if not raw:
        return None
    if isinstance(raw, str):
        return raw[:2000]
    # Atlassian Document Format — walk the content tree
    def _walk(node) -> str:
        if not isinstance(node, dict):
            return ''
        if node.get('type') == 'text':
            return node.get('text', '')
        parts = [_walk(c) for c in node.get('content', [])]
        sep = '\n' if node.get('type') in ('paragraph', 'heading', 'bulletList', 'listItem') else ''
        return sep.join(parts)
    return _walk(raw)[:2000] or None


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def _days_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if not start:
        return None
    to = end or datetime.utcnow()
    return max(0, (to - start).days)


def _fetch_all_epics(client: JiraClient) -> Dict[str, str]:
    """Return {epic_key: customer_name} for all ES epics."""
    epics: Dict[str, str] = {}
    next_token = None
    while True:
        result = client.search_issues(
            jql=f'project = {_ES_PROJECT} AND issuetype = Epic ORDER BY created ASC',
            max_results=100,
            fields=['summary'],
            next_page_token=next_token,
        )
        for issue in result.get('issues', []):
            epics[issue['key']] = issue['fields'].get('summary', '').strip()
        if result.get('isLast', True):
            break
        next_token = result.get('nextPageToken')
        if not next_token:
            break
    return epics


def _fetch_all_tickets(client: JiraClient) -> List[Dict]:
    """Return all non-epic issues from the ES project."""
    issues = []
    next_token = None
    while True:
        result = client.search_issues(
            jql=f'project = {_ES_PROJECT} AND issuetype = Story ORDER BY created ASC',
            max_results=100,
            fields=_FIELDS,
            next_page_token=next_token,
        )
        issues.extend(result.get('issues', []))
        if result.get('isLast', True):
            break
        next_token = result.get('nextPageToken')
        if not next_token:
            break
    return issues


def run_escalations_import() -> Dict:
    """Fetch all ES escalation tickets and upsert into the escalations table."""
    print("\nStarting escalations import (ES project)...")
    client = JiraClient()

    print("  Fetching epic index (customer names)...")
    epics = _fetch_all_epics(client)
    print(f"  Found {len(epics)} epics")

    print("  Fetching escalation tickets...")
    tickets = _fetch_all_tickets(client)
    print(f"  Found {len(tickets)} tickets")

    db: Session = SessionLocal()
    upserted = 0
    try:
        for issue in tickets:
            f = issue['fields']

            epic_key = f.get(_EPIC_LINK_FIELD)
            customer_name = epics.get(epic_key) if epic_key else None

            status_obj = f.get('status', {})
            status = status_obj.get('name')
            status_category = (status_obj.get('statusCategory') or {}).get('name')

            priority = (f.get('priority') or {}).get('name')
            assignee = (f.get('assignee') or {}).get('displayName')
            reporter = (f.get('reporter') or {}).get('displayName')
            description = _extract_description(f.get('description'))

            created = _parse_dt(f.get('created'))
            updated = _parse_dt(f.get('updated'))
            resolved = _parse_dt(f.get('resolutiondate'))

            is_done = status_category == 'Done'
            days_open = None if is_done else _days_between(created, None)
            days_to_resolve = _days_between(created, resolved) if is_done else None

            db.execute(text("""
                INSERT INTO escalations (
                    jira_issue_id, issue_key,
                    customer_name, epic_key, epic_summary,
                    summary, description, status, status_category, priority,
                    assignee_name, reporter_name,
                    created_date, updated_date, resolution_date,
                    days_open, days_to_resolve,
                    previous_status, status_changed_at, synced_at
                ) VALUES (
                    :issue_id, :issue_key,
                    :customer_name, :epic_key, :epic_summary,
                    :summary, :description, :status, :status_category, :priority,
                    :assignee, :reporter,
                    :created, :updated, :resolved,
                    :days_open, :days_to_resolve,
                    NULL, NULL, NOW()
                )
                ON CONFLICT (jira_issue_id) DO UPDATE SET
                    customer_name      = EXCLUDED.customer_name,
                    epic_key           = EXCLUDED.epic_key,
                    epic_summary       = EXCLUDED.epic_summary,
                    summary            = EXCLUDED.summary,
                    description        = EXCLUDED.description,
                    previous_status    = CASE
                                           WHEN escalations.status IS DISTINCT FROM EXCLUDED.status
                                           THEN escalations.status
                                           ELSE escalations.previous_status
                                         END,
                    status_changed_at  = CASE
                                           WHEN escalations.status IS DISTINCT FROM EXCLUDED.status
                                           THEN NOW()
                                           ELSE escalations.status_changed_at
                                         END,
                    status             = EXCLUDED.status,
                    status_category    = EXCLUDED.status_category,
                    priority           = EXCLUDED.priority,
                    assignee_name      = EXCLUDED.assignee_name,
                    reporter_name      = EXCLUDED.reporter_name,
                    updated_date       = EXCLUDED.updated_date,
                    resolution_date    = EXCLUDED.resolution_date,
                    days_open          = EXCLUDED.days_open,
                    days_to_resolve    = EXCLUDED.days_to_resolve,
                    synced_at          = NOW()
            """), {
                'issue_id': issue['id'],
                'issue_key': issue['key'],
                'customer_name': customer_name,
                'epic_key': epic_key,
                'epic_summary': epics.get(epic_key) if epic_key else None,
                'summary': f.get('summary', '')[:500],
                'description': description,
                'status': status,
                'status_category': status_category,
                'priority': priority,
                'assignee': assignee,
                'reporter': reporter,
                'created': created,
                'updated': updated,
                'resolved': resolved,
                'days_open': days_open,
                'days_to_resolve': days_to_resolve,
            })
            upserted += 1

        db.commit()
        print(f"  Upserted {upserted} escalation records")
        return {'upserted': upserted, 'epics': len(epics)}

    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()
