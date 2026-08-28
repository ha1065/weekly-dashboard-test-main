"""
Deployment smoke tests for the weekly reporting application.

Run before every deployment to catch regressions:
    pytest tests/test_deployment.py -v --tb=short

No database connection or external API access required.
"""

import json
from datetime import datetime, date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Section 1: Module Imports
# Catches: missing dependencies, syntax errors, circular imports
# ---------------------------------------------------------------------------


def test_import_database_config():
    import src.database.config


def test_import_models():
    import src.database.models


def test_import_apply_views():
    import src.database.apply_views


def test_import_clockify_client():
    import src.integrations.clockify_client


def test_import_jira_client():
    import src.integrations.jira_client


def test_import_import_clockify_data():
    import src.integrations.import_clockify_data


def test_import_import_jira_data():
    import src.integrations.import_jira_data


def test_import_forecast_parser():
    import src.integrations.forecast_parser


def test_import_lambda_handler():
    import src.lambda_handler


# ---------------------------------------------------------------------------
# Section 2: SQLAlchemy Models
# Catches: column type errors, broken constraints, missing tablenames
# ---------------------------------------------------------------------------


def test_all_tables_created(sqlite_engine):
    from sqlalchemy import inspect

    tables = inspect(sqlite_engine).get_table_names()
    expected = [
        "clockify_users",
        "clockify_projects",
        "clockify_detailed_time_entries",
        "user_skills",
        "ps_resource_forecasts",
        "ps_resource_forecast_history",
        "import_logs",
        "jira_projects",
        "ps_project_status",
        "ps_project_mapping",
    ]
    for table in expected:
        assert table in tables, f"Table '{table}' was not created"


def test_insert_clockify_user(db_session):
    from src.database.models import ClockifyUser

    user = ClockifyUser(clockify_user_id="test-id-123", name="Test User")
    db_session.add(user)
    db_session.flush()
    assert user.user_id is not None


def test_insert_ps_resource_forecast(db_session):
    from src.database.models import PSResourceForecast

    forecast = PSResourceForecast(
        week_start_date=date(2026, 1, 6),
        week_end_date=date(2026, 1, 12),
        user_name="Alice Smith",
        client_name="ACME Corp",
        forecasted_hours=40.0,
    )
    db_session.add(forecast)
    db_session.flush()
    assert forecast.forecast_id is not None


def test_insert_import_log(db_session):
    from src.database.models import ImportLog

    log = ImportLog(import_type="manual", import_category="forecasts")
    db_session.add(log)
    db_session.flush()
    assert log.log_id is not None


# ---------------------------------------------------------------------------
# Section 3: SQL View Definitions
# Catches: deleted/renamed views, truncated file, broken parentheses
# ---------------------------------------------------------------------------

SQL_FILE = Path(__file__).parent.parent / "src" / "database" / "create_views.sql"

EXPECTED_VIEWS = [
    "vw_weekly_time_summary",
    "vw_resource_utilization",
    "vw_project_time_tracking",
    "vw_client_time_summary",
    "vw_skill_area_summary",
    "vw_daily_activity_trend",
    "vw_active_resources",
    "vw_import_activity",
    "vw_practice_alignment_performance_12w",
    "vw_monthly_summary",
    "vw_missing_time_submissions",
    "vw_pod_performance_analysis",
    "vw_contractor_weekly_trend",
    "vw_contractor_time_summary",
    "vw_forecast_vs_actual",
    "vw_forecast_pivot",
    "vw_forecast_summary_by_client",
    "vw_forecast_summary",
    "vw_forecast_over_40_hours",
    "vw_ps_project_status",
    "vw_forecast_version_comparison",
    "vw_data_freshness",
]


def test_sql_views_file_exists():
    assert SQL_FILE.exists(), f"create_views.sql not found at {SQL_FILE}"


def test_sql_views_not_empty():
    content = SQL_FILE.read_text()
    assert len(content) > 100, "create_views.sql appears truncated"


def test_all_expected_views_present():
    content = SQL_FILE.read_text()
    for view_name in EXPECTED_VIEWS:
        assert view_name in content, f"View '{view_name}' not found in create_views.sql"


def test_balanced_parentheses():
    content = SQL_FILE.read_text()
    import re
    # Strip single-line comments and string literals to avoid false positives
    cleaned = re.sub(r"--[^\n]*", "", content)
    cleaned = re.sub(r"'[^']*'", "", cleaned)
    opens = cleaned.count("(")
    closes = cleaned.count(")")
    assert opens == closes, f"Mismatched parentheses: {opens} opens vs {closes} closes"


# ---------------------------------------------------------------------------
# Section 4: Forecast Parser
# Catches: date parsing regressions, off-by-one week boundaries
# ---------------------------------------------------------------------------

from src.integrations.forecast_parser import (
    parse_week_start_date,
    parse_week_date_range,
    get_monday_of_week,
)


class TestParseWeekStartDate:
    def test_iso_format(self):
        assert parse_week_start_date("2026-01-05") == datetime(2026, 1, 5)

    def test_us_date_format(self):
        assert parse_week_start_date("1/5/2026") == datetime(2026, 1, 5)

    def test_datetime_passthrough(self):
        dt = datetime(2026, 2, 3)
        assert parse_week_start_date(dt) is dt

    def test_none_returns_none(self):
        assert parse_week_start_date(None) is None

    def test_nan_returns_none(self):
        assert parse_week_start_date(float("nan")) is None

    def test_verbose_date_format(self):
        result = parse_week_start_date("Jan 5, 2026")
        assert result == datetime(2026, 1, 5)


class TestParseWeekDateRange:
    def test_same_month(self):
        start, end = parse_week_date_range("16th-20th Dec", year=2025)
        assert start == datetime(2025, 12, 16)
        assert end == datetime(2025, 12, 20)

    def test_month_rollover(self):
        start, end = parse_week_date_range("29th Dec-2nd Jan", year=2025)
        assert start == datetime(2025, 12, 29)
        assert end == datetime(2026, 1, 2)

    def test_empty_string(self):
        assert parse_week_date_range("") == (None, None)

    def test_none_input(self):
        assert parse_week_date_range(None) == (None, None)


class TestGetMondayOfWeek:
    def test_wednesday(self):
        wednesday = datetime(2026, 1, 7)  # Wednesday
        assert get_monday_of_week(wednesday) == datetime(2026, 1, 5)

    def test_monday_returns_itself(self):
        monday = datetime(2026, 1, 5)
        assert get_monday_of_week(monday) == datetime(2026, 1, 5)

    def test_sunday(self):
        sunday = datetime(2026, 1, 11)
        assert get_monday_of_week(sunday) == datetime(2026, 1, 5)

    def test_time_zeroed(self):
        result = get_monday_of_week(datetime(2026, 1, 7, 14, 30, 45))
        assert result.hour == 0 and result.minute == 0 and result.second == 0


# ---------------------------------------------------------------------------
# Section 5: Lambda Handler Routing
# Catches: broken routing, removed modes, typos in mode strings
# ---------------------------------------------------------------------------

import src.lambda_handler as handler


class MockContext:
    function_name = "test-function"
    memory_limit_in_mb = 512


@pytest.fixture
def mock_lambda_env():
    mock_secrets = {
        "db_password": "test",
        "clockify_api_key": "test-key",
        "clockify_workspace_id": "test-ws",
        "jira_base_url": "",
        "jira_api_email": "",
        "jira_api_token": "",
        "jira_project_keys": "",
        "jira_phase_field_id": "",
    }
    with patch.object(handler, "get_secrets", return_value=mock_secrets):
        with patch.object(handler, "set_environment_from_secrets"):
            yield


def test_lambda_apply_views_mode(mock_lambda_env):
    with patch.object(
        handler, "apply_database_views", return_value={"status": "success"}
    ):
        result = handler.lambda_handler({"mode": "apply_views"}, MockContext())
    assert result["statusCode"] == 200


def test_lambda_diagnose_mode(mock_lambda_env):
    with patch.object(handler, "diagnose_import_logs", return_value={}):
        result = handler.lambda_handler({"mode": "diagnose"}, MockContext())
    assert result["statusCode"] == 200


def test_lambda_debug_secrets_mode(mock_lambda_env):
    result = handler.lambda_handler({"mode": "debug_secrets"}, MockContext())
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["secrets_retrieved"] is True


def test_lambda_unknown_mode_doesnt_crash(mock_lambda_env):
    """An unrecognized mode should fall through to the import path, not crash."""
    with patch.object(handler, "apply_database_views", return_value={"status": "ok"}):
        with patch("src.integrations.import_clockify_data.run_import"):
            with patch(
                "src.integrations.import_jira_data.run_jira_import",
                return_value={"statistics": {}},
            ):
                with patch("src.database.config.SessionLocal") as mock_session:
                    mock_db = MagicMock()
                    mock_session.return_value = mock_db
                    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
                        None
                    )
                    mock_db.execute.return_value.scalar.return_value = 0
                    result = handler.lambda_handler({}, MockContext())
    assert result["statusCode"] == 200


# ---------------------------------------------------------------------------
# Section 6: Forecast Import Function
# Catches: upsert regressions, import log bugs, return signature changes
# ---------------------------------------------------------------------------


def _seed_clockify_user(db_session, clockify_user_id, name):
    """Seed a Clockify user and commit so it survives the rollback inside import_forecasts_from_template."""
    from src.database.models import ClockifyUser
    user = ClockifyUser(clockify_user_id=clockify_user_id, name=name)
    db_session.add(user)
    db_session.commit()
    return user


def test_forecast_import_inserts_new(db_session):
    from src.integrations.forecast_import import import_forecasts_from_template

    _seed_clockify_user(db_session, "ck-alice", "Alice Smith")
    forecasts = [
        {
            "week_start_date": date(2026, 1, 6),
            "week_end_date": date(2026, 1, 12),
            "user_name": "Alice Smith",
            "client_name": "ACME Corp",
            "project_name": "Cloud Migration",
            "project_type": "Migration",
            "pm_name": "Bob Jones",
            "stage": "Build",
            "comments": None,
            "forecasted_hours": 40.0,
            "actual_hours": 0.0,
        }
    ]
    imported, updated, skipped = import_forecasts_from_template(db_session, forecasts)
    assert imported == 1
    assert updated == 0


def test_forecast_import_replaces_existing(db_session):
    """Re-importing the same week deletes old records and inserts new ones."""
    from src.integrations.forecast_import import import_forecasts_from_template
    from src.database.models import PSResourceForecast, PSResourceForecastHistory

    _seed_clockify_user(db_session, "ck-bob", "Bob Test")
    forecast = {
        "week_start_date": date(2026, 3, 2),
        "week_end_date": date(2026, 3, 8),
        "user_name": "Bob Test",
        "client_name": "TestCo",
        "project_name": "P1",
        "project_type": None,
        "pm_name": None,
        "stage": None,
        "comments": None,
        "forecasted_hours": 40.0,
        "actual_hours": 0.0,
    }
    import_forecasts_from_template(db_session, [forecast])

    # Second import with updated hours should delete+insert, not update
    forecast["forecasted_hours"] = 32.0
    imported, updated, skipped = import_forecasts_from_template(db_session, [forecast])
    assert imported == 1
    assert updated == 0

    # Verify the old forecast was archived to history
    history = db_session.query(PSResourceForecastHistory).all()
    assert len(history) == 1
    assert history[0].forecasted_hours == 40.0
    assert history[0].user_name == "Bob Test"

    # Verify the current forecast has the new hours
    current = db_session.query(PSResourceForecast).filter(
        PSResourceForecast.user_name == "Bob Test"
    ).first()
    assert current.forecasted_hours == 32.0


def test_forecast_import_multiple_projects_same_client(db_session):
    from src.integrations.forecast_import import import_forecasts_from_template

    _seed_clockify_user(db_session, "ck-multi", "Multi Project User")
    forecasts = [
        {
            "week_start_date": date(2026, 5, 4),
            "week_end_date": date(2026, 5, 10),
            "user_name": "Multi Project User",
            "client_name": "SameCo",
            "project_name": "Project A",
            "project_type": None,
            "pm_name": None,
            "stage": None,
            "comments": None,
            "forecasted_hours": 30.0,
            "actual_hours": 0.0,
        },
        {
            "week_start_date": date(2026, 5, 4),
            "week_end_date": date(2026, 5, 10),
            "user_name": "Multi Project User",
            "client_name": "SameCo",
            "project_name": "Project B",
            "project_type": None,
            "pm_name": None,
            "stage": None,
            "comments": None,
            "forecasted_hours": 28.0,
            "actual_hours": 0.0,
        },
    ]
    imported, updated, skipped = import_forecasts_from_template(db_session, forecasts)
    assert imported == 2, "Both projects should be imported separately"
    assert updated == 0


def test_forecast_import_rejects_unknown_user(db_session):
    """Users not in Clockify are skipped and reported in the skipped set."""
    from src.integrations.forecast_import import import_forecasts_from_template

    forecasts = [
        {
            "week_start_date": date(2026, 4, 6),
            "week_end_date": date(2026, 4, 12),
            "user_name": "Unknown Person XYZ",
            "client_name": "Test Client",
            "project_name": "Test Project",
            "project_type": None,
            "pm_name": None,
            "stage": None,
            "comments": None,
            "forecasted_hours": 8.0,
            "actual_hours": 0.0,
        }
    ]
    imported, updated, skipped = import_forecasts_from_template(db_session, forecasts)
    assert imported == 0
    assert "Unknown Person XYZ" in skipped


def test_forecast_import_empty_list(db_session):
    from src.integrations.forecast_import import import_forecasts_from_template

    imported, updated, skipped = import_forecasts_from_template(db_session, [])
    assert imported == 0
    assert updated == 0
