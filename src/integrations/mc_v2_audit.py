"""MC V2 Audit: Managed Services methodology progress report.

For each active MC customer (from ps_project_status WHERE issue_type='Managed Services'),
fetches ALL Jira issues from their project (all statuses), organises them by epic/phase,
and uses Amazon Bedrock to generate a professional progress report.

Output is stored in:
  - mc_v2_audit_by_customer  (one row per customer per week_start)
  - mc_v2_audit_by_phase     (one row per customer+phase per week_start)

Unlike analyze_project_health (which is a weekly Jira-vs-Clockify diff),
this is a cumulative status-as-of snapshot — no date filter on Jira issues.
"""

import base64
import json
import os
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

# Baseline project key — TMSV defines the canonical set of deliverables for each phase.
_BASELINE_PROJECT_KEY = 'TMSV'

# Minimum similarity ratio (0–1) to consider a customer story as matching a baseline story.
_MATCH_THRESHOLD = 0.50


import boto3
import requests


# ---------------------------------------------------------------------------
# Jira helpers
# ---------------------------------------------------------------------------

def _jira_auth() -> Tuple[Dict, str]:
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


def _get_mc_customers() -> List[Dict]:
    """Return active MC customers with their Jira project keys."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return []

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT ON (pss.client_name, jira_project_key)
                    pss.client_name,
                    REGEXP_REPLACE(pss.jira_board_link,
                        '.*/projects/([A-Z][A-Z0-9_]+).*', '\\1'
                    ) AS jira_project_key,
                    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
                        cp.pod_assignment, '{', ''), '}', ''), '"', ''), '\', '')
                    ) AS pod,
                    pss.jira_board_link
                FROM ps_project_status pss
                LEFT JOIN clockify_projects cp
                       ON (
                           LOWER(cp.client_name) = LOWER(pss.client_name)
                           OR LOWER(cp.client_name) LIKE LOWER(pss.client_name) || ' %'
                           OR LOWER(pss.client_name) LIKE LOWER(cp.client_name) || ' %'
                           OR EXISTS (
                               SELECT 1 FROM ps_project_mapping pm
                               WHERE LOWER(pm.ps_client_name) = LOWER(pss.client_name)
                                 AND (
                                     (pm.clockify_client_name IS NOT NULL AND LOWER(pm.clockify_client_name) = LOWER(cp.client_name))
                                     OR
                                     (pm.clockify_project_name IS NOT NULL AND LOWER(pm.clockify_project_name) = LOWER(cp.name))
                                 )
                                 AND pm.is_active = true
                           )
                       )
                      AND cp.pod_assignment IS NOT NULL
                WHERE pss.category = 'MC'
                  AND pss.status_category != 'Done'
                  AND pss.jira_board_link IS NOT NULL
                  AND pss.jira_board_link NOT LIKE '%/projects/CST/%'
                ORDER BY pss.client_name, jira_project_key
            """)).fetchall()
    finally:
        engine.dispose()

    customers = []
    for r in rows:
        client_name, jira_key, pod, board_link = r[0], r[1], r[2], r[3]
        if jira_key:
            is_external = bool(board_link and 'cloudelligent.atlassian.net' not in board_link)
            customers.append({
                'customer_name': client_name,
                'jira_project_key': jira_key,
                'pod': pod or 'Unassigned',
                'is_external': is_external,
            })

    return customers


def _fetch_all_jira_issues(project_key: str) -> List[Dict]:
    """Fetch ALL issues (any status) from the customer's Jira project."""
    headers, base_url = _jira_auth()
    if not base_url:
        print(f"JIRA_BASE_URL not configured — skipping {project_key}")
        return []

    jql = f'project = "{project_key}" ORDER BY created ASC'
    fields = [
        'summary', 'status', 'issuetype', 'parent',
        'priority', 'customfield_10016',  # story points
    ]

    all_issues: List[Dict] = []
    next_page_token = None

    while True:
        payload: Dict = {'jql': jql, 'maxResults': 100, 'fields': fields}
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
            print(f"[{project_key}] Jira API error: {exc}")
            break

        all_issues.extend(data.get('issues', []))

        if data.get('isLast', True):
            break
        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            break

    return all_issues


# The 4 canonical MC V2 methodology phases (from A2Z template project).
# Every customer's issues are always mapped into exactly these 4 phases.
_MC_PHASES = [
    (1, "Comprehensive Onboarding",               ["onboard", "comprehensive"]),
    (2, "Stabilize & Secure",                     ["stabilize", "secure"]),
    (3, "Operate & Optimize",                     ["operate", "optim"]),
    (4, "Continuous Optimization & Modernization", ["continuous", "modern"]),
]


def _match_phase(epic_name: str) -> int:
    """Return the canonical phase order (1-4) that best matches an epic name, or 0 if none."""
    name_lower = epic_name.lower()
    for order, _phase_name, keywords in _MC_PHASES:
        if any(kw in name_lower for kw in keywords):
            return order
    return 0


def _organize_by_phase(issues: List[Dict]) -> List[Dict]:
    """Map all Jira issues into exactly the 4 canonical MC methodology phases.

    Each epic in the customer project is matched to one of the 4 A2Z phases by
    keyword matching on the epic name. Issues whose epic doesn't match any
    canonical phase are collected in an 'Other' bucket and appended if non-empty.

    Returns:
        List of exactly 4 (or 5 if 'Other') phase dicts:
        {
            'phase_name': str,
            'phase_order': int,
            'items': [issue, ...]
        }
    """
    # Separate epics from child issues
    epics: Dict[str, str] = {}          # epic_key → summary
    children: Dict[str, List[Dict]] = {}  # epic_key → [issue, ...]
    unassigned: List[Dict] = []

    for issue in issues:
        itype = (issue.get('fields', {}).get('issuetype') or {}).get('name', '')
        if itype == 'Epic':
            epics[issue['key']] = issue.get('fields', {}).get('summary', issue['key'])
        else:
            parent = issue.get('fields', {}).get('parent') or {}
            parent_key = parent.get('key')
            if parent_key:
                children.setdefault(parent_key, []).append(issue)
            else:
                unassigned.append(issue)

    # Map each epic to a canonical phase bucket (1-4); unmapped → bucket 0
    phase_items: Dict[int, List[Dict]] = {order: [] for order, _, _ in _MC_PHASES}
    other_items: List[Dict] = list(unassigned)

    for epic_key, epic_name in epics.items():
        phase_order = _match_phase(epic_name)
        epic_children = children.get(epic_key, [])
        if phase_order in phase_items:
            phase_items[phase_order].extend(epic_children)
        else:
            other_items.extend(epic_children)

    # Build the fixed 4-phase list
    phases = []
    for order, phase_name, _ in _MC_PHASES:
        phases.append({
            'phase_name': phase_name,
            'phase_order': order,
            'items': phase_items[order],
        })

    if other_items:
        phases.append({
            'phase_name': 'Other',
            'phase_order': 5,
            'items': other_items,
        })

    return phases


def _normalize_summary(s: str) -> str:
    """Strip time estimates and noise from a Jira summary for fuzzy matching."""
    s = re.sub(r'\(est\.?\s*[\d\-]+\s*hrs?\)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\(if not in place\)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\(sa responsibilities\)', '', s, flags=re.IGNORECASE)
    return ' '.join(s.lower().split())


def _baseline_phase_order(epic_summary: str) -> int:
    """Extract phase order from a TMSV epic name like 'Phase 3: Operate & Optimize'."""
    m = re.match(r'Phase\s+(\d+)', epic_summary, re.IGNORECASE)
    return int(m.group(1)) if m else _match_phase(epic_summary)


def _fetch_baseline_phases() -> Dict[int, Dict]:
    """Fetch the TMSV template project and return phases with their baseline stories.

    TMSV epics are named 'Phase N: …' so we extract the phase number directly
    rather than relying on keyword matching (which can misfire on words like
    'Optimization' matching the Phase-3 'optim' keyword).

    Returns:
        {phase_order: {'phase_name': str, 'stories': [{'key': str, 'summary': str, 'norm': str}]}}
    """
    baseline_issues = _fetch_all_jira_issues(_BASELINE_PROJECT_KEY)
    if not baseline_issues:
        print("[MC V2 Audit] WARNING: Could not fetch baseline (TMSV) issues")
        return {}

    epics: Dict[str, int] = {}   # epic_key → phase_order
    children: Dict[str, List] = {}

    for issue in baseline_issues:
        itype = (issue.get('fields', {}).get('issuetype') or {}).get('name', '')
        if itype == 'Epic':
            summary = issue.get('fields', {}).get('summary', '')
            order = _baseline_phase_order(summary)
            if order:
                epics[issue['key']] = order
        else:
            parent_key = ((issue.get('fields', {}).get('parent') or {}).get('key') or '')
            if parent_key:
                children.setdefault(parent_key, []).append(issue)

    result: Dict[int, Dict] = {}
    phase_names = {o: name for o, name, _ in _MC_PHASES}
    for epic_key, order in epics.items():
        if order not in result:
            result[order] = {'phase_name': phase_names.get(order, f'Phase {order}'), 'stories': []}
        for issue in children.get(epic_key, []):
            summary = (issue.get('fields', {}).get('summary') or '')
            result[order]['stories'].append({
                'key': issue['key'],
                'summary': summary,
                'norm': _normalize_summary(summary),
            })

    print(f"[MC V2 Audit] Baseline loaded: "
          + ", ".join(f"Phase {o}: {len(v['stories'])} stories" for o, v in sorted(result.items())))
    return result


def _best_match(customer_norm: str, baseline_stories: List[Dict]) -> Optional[Dict]:
    """Return the baseline story with the highest similarity to customer_norm, or None."""
    best_ratio, best = 0.0, None
    for story in baseline_stories:
        ratio = SequenceMatcher(None, customer_norm, story['norm']).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, story
    return best if best_ratio >= _MATCH_THRESHOLD else None


def _status_category(issue: Dict) -> str:
    """Return 'done', 'inprogress', or 'todo' for an issue."""
    cat = (
        (issue.get('fields', {}).get('status') or {})
        .get('statusCategory', {})
        .get('key', 'new')
    )
    if cat == 'done':
        return 'done'
    if cat == 'indeterminate':
        return 'inprogress'
    return 'todo'


def _compute_phase_stats_vs_baseline(
    customer_issues: List[Dict],
    baseline_stories: List[Dict],
) -> Dict:
    """Score a customer phase against the baseline template.

    For each baseline story, find the best-matching customer story and use its
    status to classify it as done / inprogress / todo.  Baseline stories with no
    customer match at all are counted as todo.

    Returns stats dict plus 'matched' list (for prompt rendering).
    """
    matched: List[Dict] = []   # [{baseline, customer_issue, status_cat}]
    matched_baseline_keys: set = set()

    for customer_issue in customer_issues:
        f = customer_issue.get('fields', {})
        summary = f.get('summary') or ''
        norm = _normalize_summary(summary)
        match = _best_match(norm, baseline_stories)
        if match and match['key'] not in matched_baseline_keys:
            matched_baseline_keys.add(match['key'])
            matched.append({
                'baseline': match,
                'customer_issue': customer_issue,
                'status_cat': _status_category(customer_issue),
            })

    # Unmatched baseline stories → todo
    unmatched_baseline = [s for s in baseline_stories if s['key'] not in matched_baseline_keys]

    done = sum(1 for m in matched if m['status_cat'] == 'done')
    inprog = sum(1 for m in matched if m['status_cat'] == 'inprogress')
    todo = inprog + len(unmatched_baseline)  # in-progress still counts as not done for todo col
    total = len(baseline_stories)
    pct = round((done / total * 100), 1) if total > 0 else 0.0

    # Extra customer stories not matching any baseline (bonus work)
    all_matched_customer_keys = {m['customer_issue']['key'] for m in matched}
    extra_customer = [i for i in customer_issues if i['key'] not in all_matched_customer_keys]

    return {
        'total_items': total,
        'done_items': done,
        'in_progress_items': inprog,
        'todo_items': len(unmatched_baseline),
        'completion_pct': pct,
        'matched': matched,
        'unmatched_baseline': unmatched_baseline,
        'extra_customer': extra_customer,
    }


def _format_phase_for_prompt(phase: Dict, stats: Dict) -> str:
    """Render a phase section for Bedrock showing baseline vs. customer reality."""
    order = phase['phase_order']
    name = phase['phase_name']
    pct = stats['completion_pct']
    lines = [f"### Phase {order}: {name}  ({pct}% complete — {stats['done_items']}/{stats['total_items']} baseline items Done)"]

    # Matched items
    for m in stats.get('matched', []):
        bl = m['baseline']
        ci = m['customer_issue']
        cf = ci.get('fields', {})
        cstatus = (cf.get('status') or {}).get('name', '?')
        cat = m['status_cat']
        marker = '✓' if cat == 'done' else '⟳' if cat == 'inprogress' else '○'
        lines.append(f"  {marker} BASELINE: {bl['summary']}")
        lines.append(f"      Customer [{ci['key']}] ({cstatus}): {cf.get('summary','')[:80]}")

    # Baseline stories with no customer match
    for bl in stats.get('unmatched_baseline', []):
        lines.append(f"  ✗ MISSING (no customer match): {bl['summary']}")

    # Extra customer work beyond the baseline
    for ci in stats.get('extra_customer', []):
        cf = ci.get('fields', {})
        cstatus = (cf.get('status') or {}).get('name', '?')
        cat = _status_category(ci)
        marker = '✓' if cat == 'done' else '⟳' if cat == 'inprogress' else '○'
        lines.append(f"  {marker} EXTRA (not in baseline) [{ci['key']}] ({cstatus}): {cf.get('summary','')[:80]}")

    if not stats.get('matched') and not stats.get('unmatched_baseline'):
        lines.append("  (no issues found)")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Prompt / Bedrock
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a professional managed services delivery analyst at Cloudelligent. \
Your task is to review a customer's Jira project data and produce a concise, \
professional status report organised by the four Cloudelligent MC V2 methodology phases.

The four phases are always (use exactly these names):
  Phase 1: Comprehensive Onboarding
  Phase 2: Stabilize & Secure
  Phase 3: Operate & Optimize
  Phase 4: Continuous Optimization & Modernization

For each phase write a single narrative (2-4 sentences) that covers:
- What has been completed (Done items) in plain business language.
- What is currently in progress and what remains to be done.
If a phase has no issues, write "No work items recorded for this phase."
Be factual and specific — reference actual Jira task descriptions.

Write the executive summary (3-5 sentences) as if presenting to a customer stakeholder.

Return ONLY valid JSON — no markdown fences, no prose outside the JSON.\
"""

_JSON_SCHEMA = """\
Return exactly this JSON (no surrounding text). Always include all 4 phases even if empty:
{
  "customer_name": "Customer Name",
  "analysis_as_of": "YYYY-MM-DD",
  "overall_completion_pct": 45.0,
  "executive_summary": "3-5 sentence professional summary suitable for a customer stakeholder.",
  "phases": [
    {
      "phase_name": "Comprehensive Onboarding",
      "phase_order": 1,
      "total_items": 6,
      "done_items": 5,
      "in_progress_items": 1,
      "todo_items": 0,
      "completion_pct": 83.3,
      "narrative": "Single combined narrative covering completed work and what remains or is in progress."
    },
    {
      "phase_name": "Stabilize & Secure",
      "phase_order": 2,
      "total_items": 0,
      "done_items": 0,
      "in_progress_items": 0,
      "todo_items": 0,
      "completion_pct": 0.0,
      "narrative": "No work items recorded for this phase."
    },
    {
      "phase_name": "Operate & Optimize",
      "phase_order": 3,
      "total_items": 0,
      "done_items": 0,
      "in_progress_items": 0,
      "todo_items": 0,
      "completion_pct": 0.0,
      "narrative": "No work items recorded for this phase."
    },
    {
      "phase_name": "Continuous Optimization & Modernization",
      "phase_order": 4,
      "total_items": 0,
      "done_items": 0,
      "in_progress_items": 0,
      "todo_items": 0,
      "completion_pct": 0.0,
      "narrative": "No work items recorded for this phase."
    }
  ]
}
"""


def _load_prompt() -> str:
    """Load the MC V2 Audit prompt from the database (category='MC_V2')."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return ''

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT prompt_text FROM ai_analysis_prompts
                WHERE category = 'MC_V2' AND is_active = TRUE
                ORDER BY sequence_order
                LIMIT 1
            """)).fetchall()
    finally:
        engine.dispose()

    return rows[0][0] if rows else ''


def _call_bedrock(user_message: str) -> str:
    model_id = os.environ.get(
        'BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    )
    region = os.environ.get('AWS_REGION', 'us-east-1')
    bedrock = boto3.client('bedrock-runtime', region_name=region)
    response = bedrock.converse(
        modelId=model_id,
        system=[{'text': _SYSTEM_PROMPT}],
        messages=[{'role': 'user', 'content': [{'text': user_message}]}],
        inferenceConfig={'maxTokens': 4096, 'temperature': 0.1},
    )
    return response['output']['message']['content'][0]['text']


def _parse_json(raw: str) -> Dict:
    raw = raw.strip()
    m = re.search(r'```(?:json)?\s*([\s\S]+?)```', raw)
    if m:
        raw = m.group(1).strip()
    start = raw.find('{')
    if start > 0:
        raw = raw[start:]
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Database upsert
# ---------------------------------------------------------------------------

def _upsert(customer_name: str, jira_project_key: str, pod: str, result: Dict, week_start: date):
    """Delete then re-insert audit rows for this customer+week_start."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    engine = create_engine(db_url)
    analyzed_at = datetime.now()

    try:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM mc_v2_audit_by_customer "
                "WHERE week_start=:ws AND customer_name=:cn"
            ), {'ws': week_start, 'cn': customer_name})
            conn.execute(text(
                "DELETE FROM mc_v2_audit_by_phase "
                "WHERE week_start=:ws AND customer_name=:cn"
            ), {'ws': week_start, 'cn': customer_name})

            conn.execute(text("""
                INSERT INTO mc_v2_audit_by_customer
                    (week_start, customer_name, jira_project_key, pod,
                     total_phases, completed_phases, overall_completion_pct,
                     executive_summary, analyzed_at)
                VALUES
                    (:ws, :cn, :jk, :pod, :tp, :cp, :pct, :es, :at)
            """), {
                'ws': week_start,
                'cn': customer_name,
                'jk': jira_project_key,
                'pod': pod,
                'tp': len(result.get('phases', [])),
                'cp': sum(1 for p in result.get('phases', [])
                          if (p.get('completion_pct') or 0) >= 100),
                'pct': result.get('overall_completion_pct'),
                'es': result.get('executive_summary', ''),
                'at': analyzed_at,
            })

            for phase in result.get('phases', []):
                pct = phase.get('completion_pct')
                raw_name = phase.get('phase_name', '')
                phase_name_with_pct = (
                    f"{raw_name} (External)" if pct is None else f"{raw_name} ({pct}%)"
                )
                conn.execute(text("""
                    INSERT INTO mc_v2_audit_by_phase
                        (week_start, customer_name, jira_project_key,
                         phase_name, phase_order,
                         total_items, done_items, in_progress_items, todo_items,
                         completion_pct, narrative, analyzed_at)
                    VALUES
                        (:ws, :cn, :jk, :pn, :po,
                         :ti, :di, :ii, :tdi,
                         :pct, :narrative, :at)
                """), {
                    'ws': week_start,
                    'cn': customer_name,
                    'jk': jira_project_key,
                    'pn': phase_name_with_pct,
                    'po': phase.get('phase_order'),
                    'ti': phase.get('total_items', 0),
                    'di': phase.get('done_items', 0),
                    'ii': phase.get('in_progress_items', 0),
                    'tdi': phase.get('todo_items', 0),
                    'pct': pct,
                    'narrative': phase.get('narrative', ''),
                    'at': analyzed_at,
                })
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Per-customer runner
# ---------------------------------------------------------------------------

_EXTERNAL_SUMMARY = (
    "Jira board for this customer is managed on an external instance and cannot be "
    "audited automatically. Progress data must be reviewed manually."
)

_EXTERNAL_RESULT = {
    'overall_completion_pct': None,
    'executive_summary': _EXTERNAL_SUMMARY,
    'phases': [
        {
            'phase_name': phase_name,
            'phase_order': order,
            'total_items': 0,
            'done_items': 0,
            'in_progress_items': 0,
            'todo_items': 0,
            'completion_pct': None,
            'narrative': 'Jira board managed externally — automated audit not available.',
        }
        for order, phase_name, _ in _MC_PHASES
    ],
}


def _run_customer(customer: Dict, week_start: date, extra_instructions: str,
                  baseline_phases: Dict[int, Dict]) -> Dict:
    """Run the V2 Audit pipeline for one MC customer."""
    name = customer['customer_name']
    key = customer['jira_project_key']

    if customer.get('is_external'):
        print(f"[MC V2 Audit] {name} — external Jira, storing placeholder")
        result = dict(_EXTERNAL_RESULT)
        result['customer_name'] = name
        return result

    print(f"[MC V2 Audit] {name} ({key}) — fetching Jira issues...")

    issues = _fetch_all_jira_issues(key)
    print(f"[MC V2 Audit] {name} — {len(issues)} total issues")

    if not issues:
        return {'skipped': 'no Jira issues found'}

    customer_phases = _organize_by_phase(issues)

    # Score each canonical phase against the baseline template
    phase_stats: Dict[str, Dict] = {}
    for phase in customer_phases:
        bl = baseline_phases.get(phase['phase_order'], {})
        bl_stories = bl.get('stories', [])
        if bl_stories:
            stats = _compute_phase_stats_vs_baseline(phase['items'], bl_stories)
        else:
            # No baseline for this phase — fall back to self-scoring
            done_c = sum(1 for i in phase['items'] if _status_category(i) == 'done')
            inp_c  = sum(1 for i in phase['items'] if _status_category(i) == 'inprogress')
            todo_c = sum(1 for i in phase['items'] if _status_category(i) == 'todo')
            total = len(phase['items'])
            pct = round(done_c / total * 100, 1) if total else 0.0
            stats = {
                'total_items': total, 'done_items': done_c,
                'in_progress_items': inp_c, 'todo_items': todo_c,
                'completion_pct': pct,
                'matched': [], 'unmatched_baseline': [], 'extra_customer': phase['items'],
            }
        phase_stats[phase['phase_name']] = stats

    # Overall completion is baseline-relative: total baseline items across all phases
    all_baseline = sum(s['total_items'] for s in phase_stats.values())
    all_done = sum(s['done_items'] for s in phase_stats.values())
    overall_pct = round((all_done / all_baseline * 100), 1) if all_baseline > 0 else 0.0

    phase_text = '\n\n'.join(
        _format_phase_for_prompt(p, phase_stats[p['phase_name']])
        for p in customer_phases
        if p['phase_name'] in phase_stats
    )

    user_message = f"""## Customer: {name}
## Jira Project: {key}
## Status As Of: {week_start}
## Overall Completion vs Baseline: {overall_pct}% ({all_done}/{all_baseline} baseline items Done)

{extra_instructions}

## Phase Analysis (Baseline vs Customer Board)
Legend: ✓ = Done  ⟳ = In Progress  ○ = To Do  ✗ = Missing from customer board  EXTRA = not in baseline

{phase_text}

{_JSON_SCHEMA}"""

    print(f"[MC V2 Audit] {name} — calling Bedrock...")
    raw = _call_bedrock(user_message)
    print(f"[MC V2 Audit] {name} — response {len(raw)} chars")

    result = _parse_json(raw)

    # Always trust computed stats over AI counts
    for phase in result.get('phases', []):
        pn = phase.get('phase_name', '')
        if pn in phase_stats:
            s = phase_stats[pn]
            phase['total_items'] = s['total_items']
            phase['done_items'] = s['done_items']
            phase['in_progress_items'] = s['in_progress_items']
            phase['todo_items'] = s['todo_items']
            phase['completion_pct'] = s['completion_pct']

    result['overall_completion_pct'] = overall_pct
    result['customer_name'] = name

    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def seed_artifact_verification_from_jira(conn, base_url: str, headers: Dict):
    """Seed artifact_verification table with all MC V2 Done Jira issues."""
    from sqlalchemy import text

    rows = conn.execute(text("""
        SELECT DISTINCT issue_key AS jira_issue_id
        FROM ps_project_status
        WHERE category = 'MC' AND status_category = 'Done'
          AND issue_key IS NOT NULL
    """)).fetchall()

    inserted = 0
    for row in rows:
        issue_id = row[0]
        try:
            conn.execute(text("""
                INSERT INTO artifact_verification
                  (jira_issue_id, artifact_present, artifact_url, artifact_verified_at, verified_by, error_message)
                VALUES (:issue_id, FALSE, NULL, NULL, NULL, NULL)
                ON CONFLICT (jira_issue_id) DO NOTHING
            """), {'issue_id': issue_id})
            inserted += 1
        except Exception as e:
            print(f"[Artifact Verification] Seed failed for {issue_id}: {e}")

    print(f"[Artifact Verification] Seeded {inserted} MC Done issues")


def verify_confluence_artifacts(conn, base_url: str, headers: Dict):
    """Verify Confluence artifacts for MC issues. Check for remote links and validate page existence."""
    from sqlalchemy import text

    rows = conn.execute(text("""
        SELECT jira_issue_id
        FROM artifact_verification
        WHERE artifact_verified_at IS NULL
           OR artifact_verified_at < NOW() - INTERVAL '7 days'
        ORDER BY artifact_verified_at NULLS FIRST
        LIMIT 10
    """)).fetchall()

    if not rows:
        print("[Artifact Verification] No issues to verify")
        return

    print(f"[Artifact Verification] Verifying {len(rows)} issues")

    for row in rows:
        issue_id = row[0]
        artifact_found = False
        artifact_url = None
        error_msg = None

        try:
            # Check for Confluence remote links
            resp = requests.get(
                f"{base_url}/rest/api/3/issue/{issue_id}/remotelink",
                headers=headers,
                timeout=8,
            )
            resp.raise_for_status()
            links = resp.json()

            # Find Confluence link
            for link in links:
                obj_url = (link.get('object') or {}).get('url', '')
                if '/wiki/' in obj_url:
                    artifact_found = True
                    artifact_url = obj_url
                    break

            # If found, verify the page exists
            if artifact_found and artifact_url:
                head_resp = requests.head(
                    artifact_url,
                    headers=headers,
                    timeout=8,
                )
                if head_resp.status_code != 200:
                    artifact_found = False
                    error_msg = f"Page returned {head_resp.status_code}"

        except requests.exceptions.Timeout:
            error_msg = "Timeout verifying artifact"
        except requests.exceptions.RequestException as e:
            error_msg = f"API error: {str(e)[:100]}"
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)[:100]}"

        # Upsert result
        try:
            conn.execute(text("""
                INSERT INTO artifact_verification
                  (jira_issue_id, artifact_present, artifact_url, artifact_verified_at, verified_by, error_message)
                VALUES (:issue_id, :present, :url, NOW(), 'mc_v2_audit', :error)
                ON CONFLICT (jira_issue_id) DO UPDATE SET
                  artifact_present = EXCLUDED.artifact_present,
                  artifact_url = EXCLUDED.artifact_url,
                  artifact_verified_at = EXCLUDED.artifact_verified_at,
                  error_message = EXCLUDED.error_message
            """), {
                'issue_id': issue_id,
                'present': artifact_found,
                'url': artifact_url,
                'error': error_msg,
            })
        except Exception as e:
            print(f"[Artifact Verification] Upsert failed for {issue_id}: {e}")

    print(f"[Artifact Verification] Verification complete for {len(rows)} issues")


def run_mc_v2_audit(week_start: date) -> Dict:
    """Run the MC V2 Audit for all active MC customers.

    Args:
        week_start: The Monday date this snapshot is taken as-of.

    Returns:
        Summary dict {customer_name: {rows_saved: n} or {error: msg} or {skipped: reason}}
    """
    print(f"MC V2 Audit: snapshot as of {week_start}")

    customers = _get_mc_customers()
    print(f"MC V2 Audit: {len(customers)} active MC customers with Jira keys")

    # Fetch baseline template once — all customers are scored against it
    baseline_phases = _fetch_baseline_phases()

    extra_instructions = _load_prompt()
    if not extra_instructions:
        extra_instructions = (
            "Our Managed Services team follows a structured methodology. "
            "Based on the analysis below, write a professional status report "
            "covering what baseline deliverables have been completed, what is in "
            "progress, and what is still missing for each phase."
        )

    summary: Dict = {}

    for customer in customers:
        name = customer['customer_name']
        key = customer['jira_project_key']
        pod = customer['pod']
        try:
            result = _run_customer(customer, week_start, extra_instructions, baseline_phases)
            if 'skipped' in result:
                summary[name] = result
                continue
            _upsert(name, key, pod, result, week_start)
            summary[name] = {
                'phases_saved': len(result.get('phases', [])),
                'overall_completion_pct': result.get('overall_completion_pct'),
            }
            print(f"[MC V2 Audit] {name} — saved {summary[name]['phases_saved']} phases")
        except Exception as exc:
            print(f"[MC V2 Audit] {name} — FAILED: {exc}")
            summary[name] = {'error': str(exc)}

    # Run artifact verification (S03-04)
    try:
        from sqlalchemy import create_engine
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            engine = create_engine(db_url)
            with engine.begin() as conn:
                headers, base_url = _jira_auth()
                if base_url:
                    seed_artifact_verification_from_jira(conn, base_url, headers)
                    verify_confluence_artifacts(conn, base_url, headers)
    except Exception as e:
        print(f"[Artifact Verification] Failed: {e}")

    return summary
