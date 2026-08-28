#!/usr/bin/env python3
"""Apply database views with pre-flight schema fixes.
Run this on the EC2 instance that has network access to RDS.

Usage: python3 scripts/apply_views_with_preflight.py
"""
from sqlalchemy import create_engine, text
from pathlib import Path
import sys

# Connection string - uses psycopg2 or pg8000 depending on what's available
DB_URL = 'postgresql://postgres:nippo1-juhSas-vysxas@production-weekly-reporting.csrucya00no8.us-east-1.rds.amazonaws.com:5432/weekly_reporting'

try:
    import psycopg2
    db_url = DB_URL.replace('postgresql://', 'postgresql+psycopg2://')
except ImportError:
    try:
        import pg8000
        db_url = DB_URL.replace('postgresql://', 'postgresql+pg8000://')
    except ImportError:
        print("ERROR: Neither psycopg2 nor pg8000 installed. Install one: pip install psycopg2-binary")
        sys.exit(1)

engine = create_engine(db_url)

preflight_stmts = [
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS epic_key VARCHAR(50)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS epic_summary VARCHAR(500)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS previous_status VARCHAR(100)",
    "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMP",
    """CREATE TABLE IF NOT EXISTS mc_ticket_activity_snapshot (
        id              SERIAL PRIMARY KEY,
        week_start      DATE NOT NULL,
        customer_name   VARCHAR(255) NOT NULL,
        jira_project_key VARCHAR(50),
        total_issues    INTEGER DEFAULT 0,
        open_issues     INTEGER DEFAULT 0,
        in_progress_issues INTEGER DEFAULT 0,
        done_issues     INTEGER DEFAULT 0,
        updated_this_week INTEGER DEFAULT 0,
        health_overall  VARCHAR(50),
        synced_at       TIMESTAMP DEFAULT NOW(),
        UNIQUE (week_start, customer_name)
    )""",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS resolution_date TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS status_category VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS category VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS issue_type VARCHAR(100)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS priority VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS assignee_name VARCHAR(255)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS project_type VARCHAR(100)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS project_manager VARCHAR(255)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS solution_architect VARCHAR(255)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS engineer VARCHAR(255)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS account_executive VARCHAR(255)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS csm VARCHAR(255)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS current_health VARCHAR(100)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS health_overall VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS health_budget VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS health_scope VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS health_schedule VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS schedule_score VARCHAR(50)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS escalation TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS impact TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS risks_blockers TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS budget_hours DECIMAL(10,2)",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS planned_start DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS planned_end DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS planned_kickoff DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS sow_signing_date DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS expected_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS revised_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS resource_assignment_date DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS actual_kickoff DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS actual_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS internal_prep_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS discover_align_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS design_review_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS build_implement_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS launch_enable_completion DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS project_summary TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS what_we_did TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS what_we_will_do_next TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS mitigation_plan TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS slippages TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS sow_link TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS jira_board_link TEXT",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS week_start DATE",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS synced_at TIMESTAMP",
    "ALTER TABLE ps_project_status ADD COLUMN IF NOT EXISTS is_excluded BOOLEAN DEFAULT FALSE",
    "ALTER TABLE clockify_users ADD COLUMN IF NOT EXISTS time_submission VARCHAR(50)",
    "ALTER TABLE clockify_users ADD COLUMN IF NOT EXISTS reporting_excluded BOOLEAN DEFAULT FALSE",
    "ALTER TABLE clockify_users ADD COLUMN IF NOT EXISTS reporting_manager VARCHAR(255)",
    "ALTER TABLE clockify_detailed_time_entries ADD COLUMN IF NOT EXISTS week_start DATE",
    "ALTER TABLE clockify_detailed_time_entries ADD COLUMN IF NOT EXISTS task_name VARCHAR(500)",
    """CREATE TABLE IF NOT EXISTS lob_practice_mapping (
        id SERIAL PRIMARY KEY,
        practice_alignment VARCHAR(255) NOT NULL UNIQUE,
        line_of_business VARCHAR(255) NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS mc_v2_audit_by_customer (
        id SERIAL PRIMARY KEY,
        week_start DATE NOT NULL,
        customer_name VARCHAR(255) NOT NULL,
        jira_project_key VARCHAR(50),
        pod VARCHAR(100),
        overall_completion_pct NUMERIC(5,2),
        executive_summary TEXT,
        synced_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS mc_v2_audit_by_phase (
        id SERIAL PRIMARY KEY,
        week_start DATE NOT NULL,
        customer_name VARCHAR(255) NOT NULL,
        phase_name VARCHAR(255),
        phase_order INTEGER,
        completion_pct NUMERIC(5,2),
        synced_at TIMESTAMP DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS ps_stage_weekly_snapshot (
        id SERIAL PRIMARY KEY,
        week_start DATE NOT NULL,
        category VARCHAR(50),
        stage VARCHAR(255),
        project_count INTEGER DEFAULT 0,
        sort_order INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS ps_project_mapping (
        id SERIAL PRIMARY KEY,
        ps_client_name VARCHAR(255),
        ps_project_name VARCHAR(255),
        clockify_client_name VARCHAR(255),
        clockify_project_name VARCHAR(255),
        category VARCHAR(50),
        nb_subcategory VARCHAR(50),
        is_active BOOLEAN DEFAULT TRUE
    )""",
    """CREATE TABLE IF NOT EXISTS ai_analysis_prompts (
        id SERIAL PRIMARY KEY,
        category VARCHAR(100),
        sequence_order INTEGER,
        prompt_text TEXT,
        is_active BOOLEAN DEFAULT TRUE
    )""",
    """CREATE TABLE IF NOT EXISTS forecast_dropped_users (
        id SERIAL PRIMARY KEY,
        user_name VARCHAR(255),
        import_log_id INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    )""",
]

print("=" * 60)
print("Pre-flight: ensuring prerequisite tables/columns exist...")
print("=" * 60)
with engine.begin() as conn:
    for i, stmt in enumerate(preflight_stmts, 1):
        try:
            conn.execute(text(stmt))
            print(f"  [{i}/{len(preflight_stmts)}] OK")
        except Exception as e:
            print(f"  [{i}/{len(preflight_stmts)}] Warning: {e}")

print("\n" + "=" * 60)
print("Applying create_views.sql...")
print("=" * 60)

views_file = Path(__file__).parent.parent / 'src' / 'database' / 'create_views.sql'
if not views_file.exists():
    views_file = Path('src/database/create_views.sql')

with open(views_file) as f:
    sql = f.read()

# Split on semicolons, handling $$ blocks (DO blocks, function bodies)
import re

def split_sql_statements(sql_text):
    """Split SQL into statements, respecting $$ dollar-quoted blocks."""
    statements = []
    current = []
    in_dollar_quote = False

    for line in sql_text.split('\n'):
        stripped = line.strip()

        # Track dollar-quoting
        if '$$' in line:
            count = line.count('$$')
            if count % 2 == 1:
                in_dollar_quote = not in_dollar_quote

        current.append(line)

        if not in_dollar_quote and stripped.endswith(';'):
            stmt = '\n'.join(current).strip()
            if stmt and not all(l.strip().startswith('--') or l.strip() == '' for l in current):
                statements.append(stmt)
            current = []

    # Anything remaining
    if current:
        stmt = '\n'.join(current).strip()
        if stmt and not all(l.strip().startswith('--') or l.strip() == '' for l in current):
            statements.append(stmt)

    return statements

statements = split_sql_statements(sql)
print(f"  Found {len(statements)} SQL statements to execute")

failed = 0
succeeded = 0
try:
    with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                conn.execute(text(stmt))
                succeeded += 1
            except Exception as e:
                failed += 1
                err = str(e)
                # Show first 200 chars of statement for context
                stmt_preview = stmt[:150].replace('\n', ' ')
                print(f"\n  ❌ Statement {i} failed: {err[:200]}")
                print(f"     SQL: {stmt_preview}...")
                # Don't stop — continue with remaining statements
                # But we need a new transaction since this one is aborted
                raise  # re-raise to rollback, we'll retry without transaction
except Exception:
    # Retry each statement independently (no single transaction)
    print("\n  Retrying with individual transactions per statement...")
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
