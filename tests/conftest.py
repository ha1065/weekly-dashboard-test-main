"""Shared test fixtures for deployment smoke tests.

This module runs before any test collection to set up the environment
so that application modules can be imported safely without a real
database or Streamlit runtime.
"""

import os
import sys
from unittest.mock import MagicMock

# ----------------------------------------------------------------
# 1. Set DATABASE_URL before ANY src imports.
#    src/database/config.py calls get_database_url() at module level
#    and raises ValueError if no database config is found.
# ----------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# ----------------------------------------------------------------
# 2. Mock streamlit before any import of src.app.
#    app.py uses st.session_state, st.set_page_config, etc. at
#    module level which would fail without a running Streamlit server.
# ----------------------------------------------------------------
class _AttrDict(dict):
    """Dict that supports attribute-style access (like Streamlit's session_state)."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return MagicMock()
    def __setattr__(self, name, value):
        self[name] = value
    def __delattr__(self, name):
        del self[name]

mock_st = MagicMock()
mock_st.session_state = _AttrDict()
sys.modules.setdefault("streamlit", mock_st)
sys.modules.setdefault("streamlit_authenticator", MagicMock())

# ----------------------------------------------------------------
# 3. Shared fixtures
# ----------------------------------------------------------------
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def sqlite_engine():
    """Create an in-memory SQLite engine with all tables."""
    from src.database.models import Base
    from sqlalchemy import text

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # Create migration-only tables not in SQLAlchemy models
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS forecast_dropped_users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name    VARCHAR(255) NOT NULL,
                import_log_id INTEGER,
                dropped_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

    return engine


@pytest.fixture
def db_session(sqlite_engine):
    """Provide a clean database session for each test.

    Deletes all rows after each test to ensure isolation.
    """
    from src.database.models import Base

    Session = sessionmaker(bind=sqlite_engine)
    session = Session()

    yield session

    session.rollback()
    session.close()

    # Clean up all tables after each test
    with sqlite_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()
