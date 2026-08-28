#!/usr/bin/env python3
"""Fix remaining missing columns, then re-apply views.
Run on EC2 after the first apply_views_with_preflight.py run.

Usage: python3 scripts/fix_remaining_columns.py
"""
from sqlalchemy import create_engine, text
from pathlib import Path
import sys

DB_URL = 'postgresql://postgres:nippo1-juhSas-vysxas@production-weekly-reporting.csrucya00no8.us-east-1.rds.amazonaws.com:5432/weekly_reporting'

try:
    import psycopg2
    db_url = DB_URL.replace('postgresql://', 'postgresql+psycopg2://')
except ImportError:
    try:
        import pg8000
        db_url = DB_URL.replace('postgresql://', 'postgresql+pg8000://')
    except ImportError:
        print("ERROR: Neither psycopg2 nor pg8000 installed.")
        sys.exit(1)

engine = create_engine(db_url)

fixes = [
    # Escalations table - add all missing columns
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS issue_key VARCHAR(50)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS status VARCHAR(100)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS status_category VARCHAR(50)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS priority VARCHAR(50)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS assignee_name VARCHAR(255)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS reporter_name VARCHAR(255)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS created_date TIMESTAMP",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS updated_date TIMESTAMP",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS resolution_date TIMESTAMP",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS days_open INTEGER",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS days_to_resolve INTEGER",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS summary VARCHAR(500)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS synced_at TIMESTAMP",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS jira_issue_id VARCHAR(50)",
    # ps_stage_weekly_snapshot - add sort_order
    "ALTER TABLE ps_stage_weekly_snapshot ADD COLUMN IF NOT EXISTS sort_order INTEGER",
]

print("=" * 60)
print("Step 1: Adding missing columns...")
print("=" * 60)
with engine.begin() as conn:
    for i, stmt in enumerate(fixes, 1):
        try:
            conn.execute(text(stmt))
            col = stmt.split('ADD COLUMN IF NOT EXISTS ')[1] if 'ADD COLUMN' in stmt else stmt
            print(f"  [{i}/{len(fixes)}] OK - {col}")
        except Exception as e:
            print(f"  [{i}/{len(fixes)}] Warning: {e}")

print("\n" + "=" * 60)
print("Step 2: Re-applying create_views.sql (statement by statement)...")
print("=" * 60)

import re

views_file = Path(__file__).parent.parent / 'src' / 'database' / 'create_views.sql'
if not views_file.exists():
    views_file = Path('src/database/create_views.sql')

with open(views_file) as f:
    sql = f.read()

def split_sql_statements(sql_text):
    """Split SQL into statements, respecting $$ dollar-quoted blocks."""
    statements = []
    current = []
    in_dollar_quote = False

    for line in sql_text.split('\n'):
        if '$$' in line:
            count = line.count('$$')
            if count % 2 == 1:
                in_dollar_quote = not in_dollar_quote

        current.append(line)

        if not in_dollar_quote and line.strip().endswith(';'):
            stmt = '\n'.join(current).strip()
            if stmt and not all(l.strip().startswith('--') or l.strip() == '' for l in current):
                statements.append(stmt)
            current = []

    if current:
        stmt = '\n'.join(current).strip()
        if stmt and not all(l.strip().startswith('--') or l.strip() == '' for l in current):
            statements.append(stmt)

    return statements

statements = split_sql_statements(sql)
print(f"  Found {len(statements)} SQL statements to execute")

failed = 0
succeeded = 0
for i, stmt in enumerate(statements, 1):
    try:
        with engine.begin() as conn:
            conn.execute(text(stmt))
        succeeded += 1
        if i % 10 == 0:
            print(f"  ... {i}/{len(statements)} done")
    except Exception as e:
        failed += 1
        err = str(e)
        stmt_preview = stmt[:120].replace('\n', ' ')
        print(f"  ⚠️  [{i}] {err[:150]}")
        print(f"       SQL: {stmt_preview}...")

print(f"\n{'=' * 60}")
print(f"Results: {succeeded} succeeded, {failed} failed out of {len(statements)} statements")
if failed == 0:
    print("✅ All views applied successfully!")
    print("\nNext step: trigger QuickSight SPICE refresh from the Streamlit app.")
else:
    print(f"⚠️  {failed} statements failed. Review errors above.")
