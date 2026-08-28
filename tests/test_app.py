"""
Tests for Streamlit application pages: Project Mapping and Data Management.

Validates data loading queries, mapping CRUD logic, and page rendering.
No running Streamlit server or external database required.

    pytest tests/test_app.py -v --tb=short
"""

from datetime import datetime, date
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Section 1: PSProjectMapping model CRUD
# ---------------------------------------------------------------------------


def test_insert_ps_project_mapping(db_session):
    from src.database.models import PSProjectMapping

    mapping = PSProjectMapping(
        ps_client_name="Acme Corp",
        ps_project_name="Migration Phase 1",
        clockify_client_name="ACME",
        clockify_project_name="Migration",
        is_active=True,
    )
    db_session.add(mapping)
    db_session.flush()
    assert mapping.id is not None


def test_mapping_lookup_by_client_and_project(db_session):
    from src.database.models import PSProjectMapping

    db_session.add(PSProjectMapping(
        ps_client_name="ClientA",
        ps_project_name="ProjectX",
        clockify_client_name="ClientA-CK",
        is_active=True,
    ))
    db_session.add(PSProjectMapping(
        ps_client_name="ClientA",
        ps_project_name="ProjectY",
        clockify_client_name="ClientA-CK",
        clockify_project_name="ProjY",
        is_active=True,
    ))
    db_session.flush()

    # Both mappings should exist for same client
    results = db_session.query(PSProjectMapping).filter(
        PSProjectMapping.ps_client_name == "ClientA",
        PSProjectMapping.is_active == True,
    ).all()
    assert len(results) == 2


def test_mapping_update(db_session):
    from src.database.models import PSProjectMapping

    mapping = PSProjectMapping(
        ps_client_name="UpdateTest",
        clockify_client_name="OldClient",
        is_active=True,
    )
    db_session.add(mapping)
    db_session.flush()

    # Update the clockify client
    mapping.clockify_client_name = "NewClient"
    mapping.clockify_project_name = "NewProject"
    db_session.flush()

    refreshed = db_session.query(PSProjectMapping).get(mapping.id)
    assert refreshed.clockify_client_name == "NewClient"
    assert refreshed.clockify_project_name == "NewProject"


def test_mapping_delete(db_session):
    from src.database.models import PSProjectMapping

    mapping = PSProjectMapping(
        ps_client_name="DeleteTest",
        clockify_client_name="SomeClient",
        is_active=True,
    )
    db_session.add(mapping)
    db_session.flush()
    mid = mapping.id

    db_session.delete(mapping)
    db_session.flush()

    assert db_session.query(PSProjectMapping).get(mid) is None


def test_mapping_nullable_project_names(db_session):
    """Verify that ps_project_name and clockify_project_name can be null (client-level mapping)."""
    from src.database.models import PSProjectMapping

    mapping = PSProjectMapping(
        ps_client_name="ClientLevel",
        ps_project_name=None,
        clockify_client_name="ClientLevel-CK",
        clockify_project_name=None,
        is_active=True,
    )
    db_session.add(mapping)
    db_session.flush()
    assert mapping.id is not None
    assert mapping.ps_project_name is None
    assert mapping.clockify_project_name is None


# ---------------------------------------------------------------------------
# Section 2: PS/MC project filtering logic
# ---------------------------------------------------------------------------


def test_ps_project_status_model(db_session):
    """Verify PSProjectStatus model can be instantiated."""
    from src.database.models import PSProjectStatus

    project = PSProjectStatus(
        jira_issue_id="PS-123",
        issue_key="PS-123",
        jira_project_key="PS",
        client_name="TestClient",
        project_name="TestProject",
        issue_type="Emailed request",
        status_category="In Progress",
    )
    db_session.add(project)
    db_session.flush()
    assert project.id is not None


def test_ps_mc_filtering(db_session):
    """Verify PS and MC projects can be filtered by issue_type."""
    from src.database.models import PSProjectStatus

    # Add PS project
    db_session.add(PSProjectStatus(
        jira_issue_id="PS-100",
        issue_key="PS-100",
        jira_project_key="PS",
        client_name="PSClient",
        project_name="PSProject",
        issue_type="Emailed request",
        status_category="In Progress",
    ))
    # Add MC project
    db_session.add(PSProjectStatus(
        jira_issue_id="MC-200",
        issue_key="MC-200",
        jira_project_key="MC",
        client_name="MCClient",
        project_name="MCProject",
        issue_type="Managed Services",
        status_category="In Progress",
    ))
    db_session.flush()

    # PS query: exclude Managed Services
    ps_results = db_session.execute(text(
        "SELECT client_name, project_name FROM ps_project_status "
        "WHERE client_name IS NOT NULL "
        "AND (issue_type IS NULL OR issue_type != 'Managed Services')"
    )).fetchall()
    ps_clients = [r[0] for r in ps_results]
    assert "PSClient" in ps_clients
    assert "MCClient" not in ps_clients

    # MC query: only Managed Services
    mc_results = db_session.execute(text(
        "SELECT client_name, project_name FROM ps_project_status "
        "WHERE client_name IS NOT NULL "
        "AND issue_type = 'Managed Services'"
    )).fetchall()
    mc_clients = [r[0] for r in mc_results]
    assert "MCClient" in mc_clients
    assert "PSClient" not in mc_clients


# ---------------------------------------------------------------------------
# Section 3: Mapping lookup dictionary logic
# ---------------------------------------------------------------------------


def test_mapping_lookup_keys(db_session):
    """Verify the mapping lookup dictionary is keyed correctly."""
    from src.database.models import PSProjectMapping

    db_session.add(PSProjectMapping(
        ps_client_name="Alpha Corp",
        ps_project_name="Big Migration",
        clockify_client_name="Alpha",
        is_active=True,
    ))
    db_session.add(PSProjectMapping(
        ps_client_name="Alpha Corp",
        ps_project_name=None,
        clockify_client_name="Alpha-General",
        is_active=True,
    ))
    db_session.flush()

    mappings = db_session.query(PSProjectMapping).filter(
        PSProjectMapping.is_active == True,
    ).all()

    # Build lookup same way the app does
    mapping_lookup = {}
    for m in mappings:
        key = (m.ps_client_name.lower(), (m.ps_project_name or "").lower())
        mapping_lookup[key] = m

    assert ("alpha corp", "big migration") in mapping_lookup
    assert ("alpha corp", "") in mapping_lookup
    assert mapping_lookup[("alpha corp", "big migration")].clockify_client_name == "Alpha"
    assert mapping_lookup[("alpha corp", "")].clockify_client_name == "Alpha-General"


def test_mapped_count_calculation(db_session):
    """Verify mapped/unmapped counting logic."""
    from src.database.models import PSProjectMapping, PSProjectStatus

    # Add projects
    db_session.add(PSProjectStatus(
        jira_issue_id="P1", issue_key="P1", jira_project_key="PJ",
        client_name="Client1", project_name="Proj1",
        issue_type="Emailed request", status_category="In Progress",
    ))
    db_session.add(PSProjectStatus(
        jira_issue_id="P2", issue_key="P2", jira_project_key="PJ",
        client_name="Client2", project_name="Proj2",
        issue_type="Emailed request", status_category="In Progress",
    ))
    # Map only the first
    db_session.add(PSProjectMapping(
        ps_client_name="Client1", ps_project_name="Proj1",
        clockify_client_name="CK-Client1", is_active=True,
    ))
    db_session.flush()

    mappings = db_session.query(PSProjectMapping).filter(
        PSProjectMapping.is_active == True,
    ).all()
    mapping_lookup = {
        (m.ps_client_name.lower(), (m.ps_project_name or "").lower()): m
        for m in mappings
    }

    projects = [("Client1", "Proj1"), ("Client2", "Proj2")]
    mapped = sum(1 for c, p in projects if (c.lower(), (p or "").lower()) in mapping_lookup)
    assert mapped == 1
    assert len(projects) - mapped == 1


# ---------------------------------------------------------------------------
# Section 3b: Auto-populate mapping logic
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="ON CONFLICT with COALESCE requires PostgreSQL; SQLite does not support functional conflict targets",
)
def test_auto_populate_exact_match(db_session):
    """Verify auto-populate creates mappings for exact case-insensitive client matches."""
    from src.database.models import PSProjectMapping, PSProjectStatus, ClockifyProject

    # Clockify client
    db_session.add(ClockifyProject(
        clockify_project_id="ck1", name="Main Project",
        client_name="Acme Corp",
    ))
    # Jira project with same client name (different case)
    db_session.add(PSProjectStatus(
        jira_issue_id="J1", issue_key="J1", jira_project_key="PJ",
        client_name="acme corp", project_name="Migration",
        issue_type="Emailed request", status_category="In Progress",
    ))
    db_session.flush()

    from src.integrations.import_jira_data import auto_populate_mappings
    result = auto_populate_mappings(db_session)

    assert result['created'] == 1
    mapping = db_session.query(PSProjectMapping).first()
    assert mapping.ps_client_name == "acme corp"
    assert mapping.clockify_client_name == "Acme Corp"
    assert mapping.is_active is True


@pytest.mark.skipif(
    True,
    reason="ON CONFLICT with COALESCE requires PostgreSQL; SQLite does not support functional conflict targets",
)
def test_auto_populate_partial_match(db_session):
    """Verify auto-populate matches when Clockify name is contained in Jira name."""
    from src.database.models import PSProjectMapping, PSProjectStatus, ClockifyProject

    db_session.add(ClockifyProject(
        clockify_project_id="ck2", name="Proj", client_name="Lawn Doctor",
    ))
    db_session.add(PSProjectStatus(
        jira_issue_id="J2", issue_key="J2", jira_project_key="PJ",
        client_name="Lawn Doctor Migration", project_name="Assess",
        issue_type="Emailed request", status_category="In Progress",
    ))
    db_session.flush()

    from src.integrations.import_jira_data import auto_populate_mappings
    result = auto_populate_mappings(db_session)

    assert result['created'] == 1
    mapping = db_session.query(PSProjectMapping).first()
    assert mapping.ps_client_name == "Lawn Doctor Migration"
    assert mapping.clockify_client_name == "Lawn Doctor"


def test_auto_populate_skips_existing(db_session):
    """Verify auto-populate does not duplicate existing mappings."""
    from src.database.models import PSProjectMapping, PSProjectStatus, ClockifyProject

    db_session.add(ClockifyProject(
        clockify_project_id="ck3", name="Proj", client_name="TestCo",
    ))
    db_session.add(PSProjectStatus(
        jira_issue_id="J3", issue_key="J3", jira_project_key="PJ",
        client_name="TestCo", project_name="AppDev",
        issue_type="Emailed request", status_category="In Progress",
    ))
    # Pre-existing mapping
    db_session.add(PSProjectMapping(
        ps_client_name="TestCo", ps_project_name="AppDev",
        clockify_client_name="TestCo", is_active=True,
    ))
    db_session.flush()

    from src.integrations.import_jira_data import auto_populate_mappings
    result = auto_populate_mappings(db_session)

    assert result['created'] == 0
    assert result['skipped'] == 1
    assert db_session.query(PSProjectMapping).count() == 1


# ---------------------------------------------------------------------------
# Section 4: Data Sources table logic
# ---------------------------------------------------------------------------


def test_data_sources_table_structure():
    """Verify DATA_SOURCES definition has required fields."""
    DATA_SOURCES = [
        ("clockify_users", "Clockify team members and attributes", "users"),
        ("clockify_projects", "Clockify project definitions", "projects"),
        ("clockify_detailed_time_entries", "Individual time entries from Clockify", "time_entries"),
        ("user_skills", "User skill and certification records", None),
        ("ps_resource_forecasts", "Weekly resource forecast allocations", "forecasts"),
        ("ps_project_status", "Jira project status (PS and MC)", "ps_project_status"),
        ("ps_project_mapping", "Jira-to-Clockify project mapping", None),
        ("jira_projects", "Jira project metadata", "jira_projects"),
        ("import_logs", "Data import audit trail", None),
    ]

    assert len(DATA_SOURCES) == 9
    for entry in DATA_SOURCES:
        assert len(entry) == 3
        table_name, description, _ = entry
        assert isinstance(table_name, str) and len(table_name) > 0
        assert isinstance(description, str) and len(description) > 0


def test_freshness_lookup(db_session):
    """Verify import_logs freshness query returns correct timestamps."""
    from src.database.models import ImportLog

    db_session.add(ImportLog(
        import_type="adhoc",
        import_category="time_entries",
        status="success",
        started_at=datetime(2026, 2, 18, 10, 0),
        completed_at=datetime(2026, 2, 18, 10, 5),
    ))
    db_session.add(ImportLog(
        import_type="adhoc",
        import_category="time_entries",
        status="success",
        started_at=datetime(2026, 2, 19, 12, 0),
        completed_at=datetime(2026, 2, 19, 12, 3),
    ))
    db_session.add(ImportLog(
        import_type="adhoc",
        import_category="users",
        status="success",
        started_at=datetime(2026, 2, 19, 12, 0),
        completed_at=datetime(2026, 2, 19, 12, 1),
    ))
    db_session.flush()

    freshness = db_session.execute(text(
        "SELECT import_category, MAX(completed_at) AS last_import_at "
        "FROM import_logs WHERE status IN ('success', 'partial') "
        "GROUP BY import_category"
    )).fetchall()
    freshness_lookup = {r[0]: r[1] for r in freshness}

    assert "time_entries" in freshness_lookup
    assert "users" in freshness_lookup
    # Most recent time_entries import should be the 12:03 one
    ts = freshness_lookup["time_entries"]
    # SQLite returns strings; PostgreSQL returns datetime objects
    if isinstance(ts, str):
        assert "12:03" in ts
    else:
        assert ts.hour == 12
        assert ts.minute == 3


# ---------------------------------------------------------------------------
# Section 5: Migration file validation
# ---------------------------------------------------------------------------


def test_migration_016_exists():
    """Verify migration 016 file exists and contains expected SQL."""
    from pathlib import Path

    migration_path = Path(__file__).parent.parent / "src" / "database" / "migrations" / "016_update_mapping_constraint.sql"
    assert migration_path.exists(), "Migration 016 not found"

    content = migration_path.read_text()
    assert "DROP CONSTRAINT" in content
    assert "idx_ps_mapping_unique" in content
    assert "COALESCE" in content


# ---------------------------------------------------------------------------
# Section 6: Sidebar navigation
# ---------------------------------------------------------------------------


def test_sidebar_pages_include_project_mapping():
    """Verify the sidebar uses 'Project Mapping' (not 'Jira Mapping')."""
    from pathlib import Path

    app_path = Path(__file__).parent.parent / "src" / "app.py"
    content = app_path.read_text()

    assert '"Project Mapping"' in content
    assert 'elif page == "Project Mapping"' in content
    # Old name should be gone
    assert 'elif page == "Jira Mapping"' not in content
