"""Initialize database schema."""

from src.database.config import engine, Base
from src.database.models import (
    ClockifyUser,
    ClockifyProject,
    ClockifyTimeEntry,
    UserSkill,
    PSResourceForecast,
    PSResourceForecastHistory,
    ImportLog
)

def init_database():
    """Create all tables in the database."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully!")

if __name__ == "__main__":
    init_database()