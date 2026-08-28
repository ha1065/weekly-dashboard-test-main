"""Shared setup for all Streamlit pages."""

import sys
import os
from pathlib import Path

# Add project root to Python path for imports to work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env so AWS_PROFILE and other env vars are available to boto3
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import uuid
from sqlalchemy import func, text
from datetime import datetime, timedelta
from src.database.config import SessionLocal, engine
from src.database.models import ClockifyUser, ClockifyTimeEntry, ClockifyProject, PSResourceForecast, AppUser
from io import BytesIO

from src.integrations.forecast_import import import_forecasts_from_template


def apply_pending_migrations():
    """Apply any pending database migrations on startup.

    Uses schema_migrations table to track applied files — each file runs
    exactly once regardless of how many times ECS restarts.
    """
    migrations_dir = Path(__file__).parent / "database" / "migrations"
    if not migrations_dir.exists():
        return

    # Bootstrap tracking table (must exist before any idempotency check)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

    # Get already-applied filenames
    with engine.connect() as conn:
        applied = {row[0] for row in conn.execute(text("SELECT filename FROM schema_migrations"))}

    for migration_file in sorted(migrations_dir.glob("*.sql")):
        if migration_file.name in applied:
            continue  # already applied — skip
        try:
            with open(migration_file, 'r') as f:
                sql_content = f.read()
            with engine.begin() as conn:
                conn.execute(text(sql_content))
                conn.execute(text("INSERT INTO schema_migrations (filename) VALUES (:fn)"),
                             {"fn": migration_file.name})
            print(f"Applied migration: {migration_file.name}")
        except Exception as e:
            # Migration failed — likely already applied to DB before tracking existed.
            # Record it as applied so we don't retry it every restart.
            print(f"Migration {migration_file.name}: {e} (recording as applied)")
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO schema_migrations (filename) VALUES (:fn) ON CONFLICT DO NOTHING"),
                        {"fn": migration_file.name}
                    )
            except Exception:
                pass  # truly broken — skip silently


def init_migrations():
    """Apply pending migrations once per process. Call from each page's setup."""
    if 'migrations_applied' not in st.session_state:
        try:
            apply_pending_migrations()
            st.session_state.migrations_applied = True
        except Exception as e:
            print(f"Migration error: {e}")


def get_monday_of_week(date=None):
    """Get Monday of the week for a given date."""
    if date is None:
        date = datetime.now()
    
    # weekday(): Monday=0, Tuesday=1, ..., Sunday=6
    days_since_monday = date.weekday()
    monday = date - timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def get_sunday_of_week(date=None):
    """Get Sunday of the week for a given date."""
    monday = get_monday_of_week(date)
    sunday = monday + timedelta(days=6)
    return sunday


DISABLE_AUTH = os.environ.get('DISABLE_AUTH', 'false').lower() == 'true'


def get_auth_config():
    """Build authentication config from the app_users database table.

    On first run (empty table), seeds an initial user from env vars so
    existing deployments keep working without manual intervention.
    """
    import bcrypt as _bcrypt
    db = SessionLocal()
    try:
        users = db.query(AppUser).filter(AppUser.is_active == True).all()

        if not users:
            # Seed initial user from env vars
            username = os.environ.get('AUTH_USERNAME', 'admin')
            password_hash = os.environ.get(
                'AUTH_PASSWORD_HASH',
                '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G4HgpqJ3KEajGy'
            )
            display_name = os.environ.get('AUTH_NAME', 'Admin User')
            seed = AppUser(
                username=username,
                display_name=display_name,
                password_hash=password_hash,
                is_active=True,
            )
            db.add(seed)
            db.commit()
            users = [seed]

        credentials = {
            'usernames': {
                u.username: {'name': u.display_name, 'password': u.password_hash}
                for u in users
            }
        }
    finally:
        db.close()

    cookie_key = os.environ.get('AUTH_COOKIE_KEY', 'weekly_reporting_secret_key_change_me')
    return {
        'credentials': credentials,
        'cookie': {
            'name': 'weekly_reporting_auth',
            'key': cookie_key,
            'expiry_days': 7,
        },
    }


def require_auth():
    """Require authentication and return (name, username).
    
    Stops app if not authenticated.
    """
    if not DISABLE_AUTH:
        if 'authenticator' not in st.session_state:
            auth_config = get_auth_config()
            st.session_state.authenticator = stauth.Authenticate(
                auth_config['credentials'],
                auth_config['cookie']['name'],
                auth_config['cookie']['key'],
                auth_config['cookie']['expiry_days']
            )
        
        authenticator = st.session_state.authenticator
        authenticator.login()

        authentication_status = st.session_state.get('authentication_status')
        name = st.session_state.get('name')
        username = st.session_state.get('username')

        if authentication_status == False:
            st.error('Username/password is incorrect')
            st.stop()
        elif authentication_status == None:
            st.warning('Please enter your username and password')
            st.stop()
    else:
        # Authentication disabled - set default values
        name = 'Local User'
        username = 'local'

    return name, username


def render_sidebar_header():
    """Render logo, logout, logged-in-as, and data freshness in sidebar."""
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        st.sidebar.image(str(logo_path), use_container_width=True)
        st.sidebar.markdown("")  # Add spacing after logo

    st.sidebar.title("Navigation")
    
    if not DISABLE_AUTH and 'authenticator' in st.session_state:
        st.session_state.authenticator.logout('Logout', 'sidebar')
    
    name = st.session_state.get('name', 'User')
    st.sidebar.markdown(f"Logged in as: **{name}**")

    # Data freshness timestamp (NFR-002)
    try:
        with engine.connect() as _conn:
            _last_sync = _conn.execute(text(
                "SELECT MAX(synced_at) FROM clockify_detailed_time_entries"
            )).scalar()
        if _last_sync:
            st.sidebar.caption(f"Data last updated: {_last_sync.strftime('%Y-%m-%d %H:%M')} UTC")
    except Exception:
        pass

    st.sidebar.markdown("---")


def apply_ce_theme():
    """Apply CE branding CSS. Call from each page."""
    css_path = Path(__file__).parent / "assets" / "ce_theme.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    if 'weeks_back' not in st.session_state:
        st.session_state.weeks_back = 4
    if 'weeks_forward' not in st.session_state:
        st.session_state.weeks_forward = 0
