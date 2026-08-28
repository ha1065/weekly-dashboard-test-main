"""Apply database migrations."""

from pathlib import Path
from sqlalchemy import text
from src.database.config import engine


def apply_migration(migration_file: str):
    """Apply a specific migration file."""
    sql_file = Path(__file__).parent / "migrations" / migration_file

    if not sql_file.exists():
        print(f"Migration file not found: {sql_file}")
        return False

    print(f"Applying migration: {migration_file}")

    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()

        with engine.begin() as connection:
            # Split and execute statements one by one for better error handling
            statements = []
            current = []

            for line in sql_content.split('\n'):
                # Skip empty lines and comments at the start
                stripped = line.strip()
                if stripped.startswith('--'):
                    continue
                current.append(line)
                if stripped.endswith(';'):
                    stmt = '\n'.join(current).strip()
                    if stmt and not stmt.startswith('--'):
                        statements.append(stmt)
                    current = []

            for i, stmt in enumerate(statements, 1):
                if stmt.strip():
                    print(f"  Executing statement {i}/{len(statements)}...")
                    connection.execute(text(stmt))

        print(f"✅ Migration {migration_file} applied successfully!")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def apply_all_migrations():
    """Apply all pending migrations in order."""
    print("=" * 60)
    print("🔨 Applying Database Migrations")
    print("=" * 60)

    migrations_dir = Path(__file__).parent / "migrations"

    if not migrations_dir.exists():
        print("No migrations directory found.")
        return

    # Get all SQL files sorted by name (numbered order)
    migration_files = sorted([f.name for f in migrations_dir.glob("*.sql")])

    if not migration_files:
        print("No migration files found.")
        return

    print(f"\nFound {len(migration_files)} migration(s):")
    for f in migration_files:
        print(f"  - {f}")

    print()

    for migration_file in migration_files:
        apply_migration(migration_file)

    print("\n" + "=" * 60)
    print("✅ All migrations complete!")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Apply specific migration
        apply_migration(sys.argv[1])
    else:
        # Apply all migrations
        apply_all_migrations()
