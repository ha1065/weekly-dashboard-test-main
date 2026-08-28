#!/usr/bin/env python3
"""Apply create_views.sql to the live database, one statement at a time."""
import boto3, json, re
from pathlib import Path

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def split_sql_statements(sql: str) -> list[str]:
    """Split SQL into individual statements, respecting $$ dollar-quote blocks."""
    statements = []
    current = []
    in_dollar_quote = False

    for line in sql.splitlines():
        stripped = line.strip()
        if '$$' in stripped:
            in_dollar_quote = not in_dollar_quote
        current.append(line)
        if not in_dollar_quote and stripped.endswith(';') and not stripped.startswith('--'):
            stmt = '\n'.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []

    if current:
        stmt = '\n'.join(current).strip()
        if stmt:
            statements.append(stmt)

    return statements

def run(sql: str) -> tuple[bool, str]:
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    result = json.loads(r['Payload'].read())
    if result.get('errorMessage'):
        return False, result['errorMessage'][:200]
    return True, str(result.get('statusCode', 'ok'))

sql_file = Path(__file__).parent.parent / 'src' / 'database' / 'create_views.sql'
statements = split_sql_statements(sql_file.read_text())
print(f'Found {len(statements)} statements in create_views.sql\n')

def strip_leading_comments(sql: str) -> str:
    """Remove leading comment/blank lines so Lambda's run_query sees real SQL first."""
    lines = sql.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith('--'):
            return '\n'.join(lines[i:])
    return sql

succeeded = 0
for i, stmt in enumerate(statements, 1):
    preview = stmt.replace('\n', ' ')[:60]
    ok, msg = run(strip_leading_comments(stmt))
    if ok:
        print(f'[{i}/{len(statements)}] OK    {preview}')
        succeeded += 1
    else:
        print(f'[{i}/{len(statements)}] ERROR {preview}')
        print(f'  {msg}')
        print(f'\nStopped at statement {i}. {succeeded} succeeded, 1 failed.')
        raise SystemExit(1)

print(f'\n✅ {succeeded}/{len(statements)} statements executed successfully.')
