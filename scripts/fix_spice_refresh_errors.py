#!/usr/bin/env python3
"""Fix 4 failing SPICE datasets and trigger refreshes.

Failures (2026-06-08):
  1. category-hours-summary-prod      → relation vw_category_hours_summary does not exist
  2. project-hours-current-week-prod  → relation vw_project_hours_current_week does not exist
  3. kpi-weekly-snapshots-prod        → column nb_nonproductive_hours does not exist
  4. ps-stage-trend                   → column sort_order does not exist
"""

import boto3
import json
import time
import re
from pathlib import Path

PROFILE = 'AWSAdministratorAccess-961341524729'
REGION  = 'us-east-1'
ACCOUNT = '961341524729'
LAMBDA  = 'production-clockify-import'
BASE    = Path(__file__).parent.parent

session = boto3.Session(profile_name=PROFILE, region_name=REGION)
lc = session.client('lambda')
qs = session.client('quicksight')


def run_sql(sql: str, label: str) -> bool:
    """Run a single SQL statement via Lambda."""
    sql = sql.strip()
    if not sql or sql.startswith('--'):
        return True
    resp = lc.invoke(
        FunctionName=LAMBDA,
        Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode()
    )
    result = json.loads(resp['Payload'].read())
    if result.get('errorMessage'):
        print(f'  ❌ [{label}] {result["errorMessage"][:200]}')
        return False
    print(f'  ✅ [{label}] status={result.get("statusCode", "ok")}')
    return True


def split_statements(sql: str) -> list[str]:
    """Split SQL into individual statements, respecting $$ dollar-quote blocks."""
    stmts, current, in_dq = [], [], False
    for line in sql.splitlines():
        if '$$' in line:
            in_dq = not in_dq
        current.append(line)
        stripped = line.strip()
        if not in_dq and stripped.endswith(';') and not stripped.startswith('--'):
            stmt = '\n'.join(current).strip()
            if stmt:
                stmts.append(stmt)
            current = []
    if current:
        stmt = '\n'.join(current).strip()
        if stmt:
            stmts.append(stmt)
    return stmts


def apply_migration(path: Path) -> bool:
    stmts = split_statements(path.read_text())
    print(f'  Applying {path.name} ({len(stmts)} statements)...')
    for i, stmt in enumerate(stmts, 1):
        # Skip pure comment blocks
        non_comment = '\n'.join(
            l for l in stmt.splitlines() if not l.strip().startswith('--')
        ).strip()
        if not non_comment:
            continue
        ok = run_sql(non_comment, f'{path.name}:{i}')
        if not ok:
            return False
    return True


def trigger_refresh(ds_id: str) -> str:
    iid = f'fix-{int(time.time())}-{ds_id[:16]}'
    try:
        qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId=ds_id, IngestionId=iid)
        print(f'  ✅ Started: {ds_id}')
        return iid
    except Exception as e:
        print(f'  ❌ {ds_id}: {e}')
        return ''


def wait_ingestion(ds_id: str, iid: str, timeout: int = 300) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(10)
        resp = qs.describe_ingestion(AwsAccountId=ACCOUNT, DataSetId=ds_id, IngestionId=iid)
        status = resp['Ingestion']['IngestionStatus']
        if status in ('COMPLETED', 'FAILED', 'CANCELLED'):
            err = resp['Ingestion'].get('ErrorInfo', {}).get('Message', '')
            return f'{status}  {err}'.strip()
    return 'TIMEOUT'


errors = 0

# ── Fix 1 & 2: Restore views from migration 050
print('\n== Fix 1 & 2: Restore vw_project_hours_* and vw_category_hours_summary ==')
if not apply_migration(BASE / 'src/database/migrations/050_project_hours_views.sql'):
    errors += 1

# ── Fix 3a: Add missing columns (migration 061)
print('\n== Fix 3a: Add nb_nonproductive_hours + missing_time_count ==')
if not run_sql(
    'ALTER TABLE kpi_weekly_snapshots '
    'ADD COLUMN IF NOT EXISTS nb_nonproductive_hours NUMERIC(10,2), '
    'ADD COLUMN IF NOT EXISTS missing_time_count INTEGER;',
    'migration_061'
):
    errors += 1

# ── Fix 3b: Rebuild vw_kpi_ytd (migration 065)
print('\n== Fix 3b: Rebuild vw_kpi_ytd with _prev columns ==')
if not apply_migration(BASE / 'src/database/migrations/065_rebuild_vw_kpi_ytd_with_prev_cols.sql'):
    errors += 1

# ── Fix 4: Add sort_order to ps_stage_weekly_snapshot
print('\n== Fix 4: Add sort_order to ps_stage_weekly_snapshot ==')
if not run_sql(
    'ALTER TABLE ps_stage_weekly_snapshot ADD COLUMN IF NOT EXISTS sort_order INTEGER;',
    'add_col'
):
    errors += 1
else:
    run_sql(
        """UPDATE ps_stage_weekly_snapshot SET sort_order = CASE stage
            WHEN 'Backlog'      THEN 1
            WHEN 'To Do'        THEN 2
            WHEN 'In Progress'  THEN 3
            WHEN 'In Review'    THEN 4
            WHEN 'Done'         THEN 5
            ELSE 99
        END WHERE sort_order IS NULL;""",
        'backfill'
    )

# ── Trigger SPICE refreshes
print('\n== Triggering SPICE refreshes ==')
datasets = [
    'category-hours-summary-prod',
    'project-hours-current-week-prod',
    'kpi-weekly-snapshots-prod',
    'ps-stage-trend',
]
ingestions = {ds: trigger_refresh(ds) for ds in datasets}

print('\n== Waiting for ingestions ==')
for ds_id, iid in ingestions.items():
    if iid:
        result = wait_ingestion(ds_id, iid)
        icon = '✅' if result.startswith('COMPLETED') else '❌'
        print(f'  {icon} {ds_id}: {result}')

print(f'\n{"✅ All fixes applied." if errors == 0 else f"⚠️  {errors} fix(es) failed — check output above."}')
