#!/usr/bin/env python3
"""Apply Sprint 1 foundation migrations (066, 067, 070, 071)."""
import boto3, json
from pathlib import Path

PROFILE = 'AWSAdministratorAccess-961341524729'
REGION  = 'us-east-1'
LAMBDA  = 'production-clockify-import'
BASE    = Path(__file__).parent.parent

session = boto3.Session(profile_name=PROFILE, region_name=REGION)
lc = session.client('lambda')


def run_sql(sql: str, label: str) -> bool:
    sql = sql.strip()
    if not sql or all(l.strip().startswith('--') or not l.strip() for l in sql.splitlines()):
        return True
    resp = lc.invoke(FunctionName=LAMBDA, Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    result = json.loads(resp['Payload'].read())
    if result.get('errorMessage'):
        print(f'  ❌ [{label}] {result["errorMessage"][:300]}')
        return False
    print(f'  ✅ [{label}] status={result.get("statusCode","ok")}')
    return True


def apply_migration(path: Path) -> bool:
    print(f'\n== Applying {path.name} ==')
    stmts, cur, in_dq = [], [], False
    for line in path.read_text().splitlines():
        if '$$' in line:
            in_dq = not in_dq
        cur.append(line)
        if not in_dq and line.strip().endswith(';') and not line.strip().startswith('--'):
            stmt = '\n'.join(cur).strip()
            non_comment = '\n'.join(l for l in stmt.splitlines() if not l.strip().startswith('--')).strip()
            if non_comment:
                stmts.append(non_comment)
            cur = []
    ok = True
    for i, stmt in enumerate(stmts, 1):
        if not run_sql(stmt, f'{path.name}:{i}'):
            ok = False
            break
    return ok


migrations = [
    '066_practice_area_column.sql',
    '067_ps_profitability_rates.sql',
    '070_artifact_verification.sql',
    '071_ps_project_status_dedup_unique.sql',
]

# Row count before dedup
print('\n== ps_project_status row count BEFORE dedup ==')
run_sql('SELECT COUNT(*) AS row_count FROM ps_project_status;', 'count_before')

errors = 0
for m in migrations:
    if not apply_migration(BASE / 'src/database/migrations' / m):
        errors += 1

# Row count after dedup
print('\n== ps_project_status row count AFTER dedup ==')
run_sql('SELECT COUNT(*) AS row_count FROM ps_project_status;', 'count_after')

# Backfill review output for human gate S01-02
print('\n== practice_area backfill review (HUMAN REVIEW REQUIRED) ==')
run_sql(
    'SELECT name, practice_alignment, practice_area, status '
    'FROM clockify_users ORDER BY practice_area NULLS LAST, name;',
    'backfill_review'
)

print(f'\n{"✅ All migrations applied." if errors == 0 else f"❌ {errors} migration(s) failed."}')
