"""Admin handler module.

Modes handled:
  - apply_views        – recreate all DB views from create_views.sql
  - run_migration      – apply a named SQL migration file
  - run_query          – execute arbitrary SQL (read/write) as report_user
  - run_query_master   – execute SQL as postgres superuser (for DDL)
  - fix_report_user    – create/reset report_user with correct grants
  - restore_forecasts  – restore ps_resource_forecasts from history snapshot
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Internal helper — also called by pipeline for view refresh
# ---------------------------------------------------------------------------

def apply_database_views(master_url: str = None) -> Dict[str, Any]:
    """Apply database views from SQL file.

    Uses master_url (postgres superuser) when provided so that DROP VIEW on
    views owned by postgres does not fail with 'must be owner of view'.
    Falls back to the report_user DATABASE_URL if master_url is not supplied.
    """
    # Heavy imports inside function
    from sqlalchemy import create_engine, text

    print("Applying database views...")

    # Prefer master URL (postgres superuser) to handle DROP VIEW on postgres-owned views.
    # Fall back to report_user DATABASE_URL if master URL is unavailable.
    if master_url:
        print("Using master database URL (superuser) for view recreation")
        engine = create_engine(master_url)
    else:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL not set - call set_environment_from_secrets first")
        print("Using report_user DATABASE_URL (master_url not available)")
        engine = create_engine(database_url)

    sql_file = Path(__file__).parent.parent / "database" / "create_views.sql"

    with open(sql_file, 'r') as f:
        sql_content = f.read()

    with engine.begin() as connection:
        connection.execute(text(sql_content))

    # Grant permissions separately (DROP VIEW removes grants)
    try:
        with engine.begin() as connection:
            connection.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC"))
            connection.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))
    except Exception as e:
        print(f"Warning: Could not grant permissions: {e}")

    print("Database views applied successfully")
    return {'status': 'success', 'message': 'Views applied successfully'}


# ---------------------------------------------------------------------------
# Public handler functions
# ---------------------------------------------------------------------------

def apply_views(event: dict, context: Any, secrets: dict) -> dict:
    """Recreate all DB views from create_views.sql."""
    result = apply_database_views(master_url=secrets.get('master_database_url'))
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }


def run_migration(event: dict, context: Any, secrets: dict) -> dict:
    """Apply a SQL migration file.

    event keys:
      migration_file  str  filename relative to src/database/migrations/
    """
    # Heavy imports inside function
    from sqlalchemy import create_engine, text

    migration_file = event.get('migration_file', '')
    if not migration_file:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'migration_file parameter required'})
        }

    migrations_dir = Path(__file__).parent.parent / 'database' / 'migrations'
    sql_file = migrations_dir / migration_file

    if not sql_file.exists():
        return {
            'statusCode': 404,
            'body': json.dumps({'error': f'Migration file not found: {migration_file}'})
        }

    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()

        # Prefer master URL (postgres superuser) for DDL operations
        master_url = secrets.get('master_database_url') if secrets else None
        if master_url:
            print(f"run_migration: using master_database_url for {migration_file}")
            mig_engine = create_engine(master_url)
        else:
            print(f"run_migration: master_database_url not available, falling back to report_user")
            from src.database.config import engine as mig_engine

        with mig_engine.begin() as connection:
            connection.execute(text(sql_content))

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'message': f'Migration {migration_file} applied successfully'
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def run_query(event: dict, context: Any, secrets: dict) -> dict:
    """Execute a SQL statement as report_user and return rows.

    event keys:
      sql  str  SQL to execute
    """
    # Heavy imports inside function
    from sqlalchemy import text
    from src.database.config import engine

    sql = event.get('sql', '')
    if not sql:
        return {'statusCode': 400, 'body': json.dumps({'error': 'sql parameter required'})}
    is_write = sql.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'VACUUM', 'REINDEX'))
    ctx = engine.begin() if is_write else engine.connect()
    with ctx as conn:
        result = conn.execute(text(sql))
        cols = list(result.keys()) if result.returns_rows else []
        rows = [list(r) for r in result.fetchall()] if result.returns_rows else []
    return {'statusCode': 200, 'body': json.dumps({'columns': cols, 'rows': rows}, default=str)}


def run_query_master(event: dict, context: Any, secrets: dict) -> dict:
    """Execute SQL with master/owner credentials (for DDL).

    event keys:
      sql  str  SQL to execute
    """
    # Heavy imports inside function
    from sqlalchemy import create_engine, text

    master_url = secrets.get('master_database_url', '')
    if not master_url:
        return {'statusCode': 400, 'body': json.dumps({'error': 'master_database_url not found in secret'})}
    sql = event.get('sql', '')
    if not sql:
        return {'statusCode': 400, 'body': json.dumps({'error': 'sql parameter required'})}
    master_engine = create_engine(master_url)
    try:
        with master_engine.begin() as conn:
            result = conn.execute(text(sql))
            cols = list(result.keys()) if result.returns_rows else []
            rows = [list(r) for r in result.fetchall()] if result.returns_rows else []
        master_engine.dispose()
        return {'statusCode': 200, 'body': json.dumps({'columns': cols, 'rows': rows}, default=str)}
    except Exception as e:
        master_engine.dispose()
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def fix_report_user(event: dict, context: Any, secrets: dict) -> dict:
    """Create/reset report_user using master credentials.

    Uses 'master_database_url' key from Secrets Manager to connect as postgres.
    Creates report_user if it doesn't exist, resets password to match db_password
    in secret, and grants all required privileges on the weekly_reporting database.
    """
    # Heavy imports inside function
    from sqlalchemy import create_engine, text as sa_text

    master_url = secrets.get('master_database_url', '')
    target_password = secrets.get('db_password', '')
    if not master_url:
        return {'statusCode': 400, 'body': json.dumps({'error': 'master_database_url not found in secret'})}
    if not target_password:
        return {'statusCode': 400, 'body': json.dumps({'error': 'db_password not found in secret'})}
    db_name = os.environ.get('DB_NAME', 'weekly_reporting')
    master_engine = create_engine(master_url)
    actions_taken = []
    try:
        with master_engine.begin() as conn:
            # Check if report_user exists
            exists = conn.execute(
                sa_text("SELECT 1 FROM pg_roles WHERE rolname = 'report_user'")
            ).fetchone()
            if not exists:
                conn.execute(sa_text(f"CREATE USER report_user WITH PASSWORD '{target_password}'"))
                actions_taken.append('created report_user')
            else:
                conn.execute(sa_text(f"ALTER USER report_user WITH PASSWORD '{target_password}'"))
                actions_taken.append('reset report_user password')
            # Grant database-level privileges (must be done outside table-level transaction)
            conn.execute(sa_text(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO report_user"))
            actions_taken.append(f'granted all on database {db_name}')
        # Grant schema and table/sequence privileges (separate transaction)
        with master_engine.begin() as conn:
            conn.execute(sa_text("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO report_user"))
            conn.execute(sa_text("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO report_user"))
            conn.execute(sa_text("GRANT USAGE ON SCHEMA public TO report_user"))
            conn.execute(sa_text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO report_user"))
            conn.execute(sa_text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO report_user"))
            actions_taken.append('granted table/sequence/schema privileges')
        # Verify: connect as report_user
        verify_url = os.environ.get('DATABASE_URL', '')
        verify_engine = create_engine(verify_url)
        with verify_engine.connect() as vconn:
            current_user = vconn.execute(sa_text("SELECT current_user")).scalar()
            table_count = vconn.execute(sa_text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
            )).scalar()
        verify_engine.dispose()
        master_engine.dispose()
        actions_taken.append(f'verified login as {current_user}, visible tables: {table_count}')
        return {'statusCode': 200, 'body': json.dumps({'status': 'success', 'actions': actions_taken})}
    except Exception as fix_e:
        master_engine.dispose()
        return {'statusCode': 500, 'body': json.dumps({'error': str(fix_e), 'actions_taken': actions_taken})}


def restore_forecasts(event: dict, context: Any, secrets: dict) -> dict:
    """Restore ps_resource_forecasts from a history snapshot.

    event keys:
      snapshot_id  str | None  (defaults to most recent)
    """
    # Heavy imports inside function
    from sqlalchemy import text
    from src.database.config import engine

    snapshot_id = event.get('snapshot_id')

    with engine.begin() as conn:
        if not snapshot_id:
            # Find the most recent snapshot
            row = conn.execute(text(
                "SELECT snapshot_id, COUNT(*) as cnt, ROUND(SUM(forecasted_hours)::numeric,1) as hrs "
                "FROM ps_resource_forecast_history GROUP BY snapshot_id ORDER BY snapshot_id::int DESC LIMIT 1"
            )).fetchone()
            if not row:
                return {'statusCode': 400, 'body': json.dumps({'error': 'No history snapshots found'})}
            snapshot_id = row[0]

        # Check current live count
        live_count = conn.execute(text("SELECT COUNT(*) FROM ps_resource_forecasts")).scalar()

        # Restore from history
        result = conn.execute(text("""
            INSERT INTO ps_resource_forecasts
                (week_start_date, week_end_date, clockify_user_id, user_name,
                 location, project_name, clockify_project_id, client_name,
                 project_type, pm_name, stage, practice_area,
                 forecasted_hours, actual_hours, comments, created_by,
                 created_at, updated_at)
            SELECT
                week_start_date, week_end_date, clockify_user_id, user_name,
                location, project_name, clockify_project_id, client_name,
                project_type, pm_name, stage, practice_area,
                forecasted_hours, actual_hours, comments, created_by,
                created_at, updated_at
            FROM ps_resource_forecast_history
            WHERE snapshot_id = :sid
            ON CONFLICT (user_name, week_start_date, client_name, project_name) DO UPDATE
            SET forecasted_hours = EXCLUDED.forecasted_hours,
                updated_at = NOW()
        """), {'sid': str(snapshot_id)})

        restored = result.rowcount
        new_count = conn.execute(text("SELECT COUNT(*) FROM ps_resource_forecasts")).scalar()

    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'success',
            'snapshot_id': str(snapshot_id),
            'records_restored': restored,
            'previous_live_count': live_count,
            'new_live_count': new_count
        })
    }
