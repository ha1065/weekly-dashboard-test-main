"""Secure database configuration with enhanced security features.

This is an enhanced version of config.py with additional security measures.
To use this version, replace config.py with this file.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import Pool
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import os
import re
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation."""

    database_url: str = Field(..., min_length=1, description="PostgreSQL connection URL")
    clockify_api_key: str = Field(..., min_length=20, description="Clockify API key")
    clockify_workspace_id: str = Field(..., min_length=10, description="Clockify workspace ID")

    # Optional security settings
    db_ssl_mode: str = Field(default="prefer", description="Database SSL mode")
    db_connect_timeout: int = Field(default=10, description="Database connection timeout")
    db_statement_timeout: int = Field(default=30000, description="Query timeout in ms")
    enable_sql_echo: bool = Field(default=False, description="Enable SQL logging (dev only)")

    class Config:
        env_file = ".env"
        extra = "ignore"

    @validator('database_url')
    def validate_database_url(cls, v):
        """Validate database URL."""
        if not v or v.strip() == "":
            raise ValueError("DATABASE_URL must be set")

        # Check for weak passwords
        if "password@" in v.lower() or "123456" in v:
            raise ValueError("Weak or default password detected in DATABASE_URL")

        # Ensure it's a PostgreSQL URL
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")

        return v

    @validator('clockify_api_key')
    def validate_api_key(cls, v):
        """Validate Clockify API key."""
        if not v or len(v) < 20:
            raise ValueError("Invalid Clockify API key (too short)")

        if v.lower() == "your_api_key_here" or v == "test":
            raise ValueError("Please set a real Clockify API key")

        return v

    @validator('clockify_workspace_id')
    def validate_workspace_id(cls, v):
        """Validate workspace ID."""
        if not v or len(v) < 10:
            raise ValueError("Invalid Clockify workspace ID")

        if v == "your_workspace_id":
            raise ValueError("Please set a real Clockify workspace ID")

        return v

    def get_masked_database_url(self) -> str:
        """Return database URL with password masked for logging."""
        if not self.database_url:
            return ""

        # Mask password in URL
        return re.sub(
            r'(postgresql://[^:]+:)([^@]+)(@.*)',
            r'\1***\3',
            self.database_url
        )


# Initialize settings with validation
try:
    settings = Settings()
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    print("\nPlease check your .env file:")
    print("  - DATABASE_URL is set correctly")
    print("  - CLOCKIFY_API_KEY is valid")
    print("  - CLOCKIFY_WORKSPACE_ID is valid")
    raise


def get_engine_connect_args():
    """Get connection arguments with security settings."""
    connect_args = {
        "connect_timeout": settings.db_connect_timeout,
        "application_name": "weekly-reporting"
    }

    # Add SSL settings
    if settings.db_ssl_mode in ("require", "verify-ca", "verify-full"):
        connect_args["sslmode"] = settings.db_ssl_mode

    # Add statement timeout
    if settings.db_statement_timeout > 0:
        connect_args["options"] = f"-c statement_timeout={settings.db_statement_timeout}"

    return connect_args


# Create SQLAlchemy engine with security features
engine = create_engine(
    settings.database_url,
    # Connection pooling
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour

    # Security
    connect_args=get_engine_connect_args(),
    echo=settings.enable_sql_echo,  # Should be False in production
    hide_parameters=True,  # Mask parameters in logs

    # Performance
    pool_timeout=30,
    isolation_level="READ COMMITTED"
)


# Add connection event listeners for security monitoring
@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log new database connections (optional)."""
    # You can add custom connection setup here
    # For example, setting session parameters
    pass


@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Validate connection on checkout."""
    # Verify connection is still alive
    # SQLAlchemy does this with pool_pre_ping, but you can add custom checks
    pass


# Create SessionLocal class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevent lazy loading issues
)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Get database session with proper cleanup."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_database_connection():
    """Test database connection with security checks."""
    print("Testing database connection...")
    print(f"Database URL: {settings.get_masked_database_url()}")

    try:
        # Test connection
        with engine.connect() as conn:
            result = conn.execute("SELECT version();")
            version = result.scalar()
            print(f"✓ Connected to: {version}")

            # Check SSL status
            ssl_result = conn.execute("SHOW ssl;")
            ssl_status = ssl_result.scalar()
            if ssl_status == "on":
                print("✓ SSL is enabled")
            else:
                print("⚠️  Warning: SSL is not enabled")

            # Check connection settings
            timeout_result = conn.execute("SHOW statement_timeout;")
            timeout = timeout_result.scalar()
            print(f"✓ Statement timeout: {timeout}")

        print("✅ Database connection successful!")
        return True

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def sanitize_error_message(error_msg: str) -> str:
    """Remove sensitive information from error messages."""
    # Remove connection strings
    sanitized = re.sub(
        r'postgresql://[^/]+@[^/]+/[^\s]+',
        'postgresql://***:***@***/***',
        str(error_msg)
    )

    # Remove API keys
    sanitized = re.sub(
        r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[\w-]+',
        r'\1***',
        sanitized,
        flags=re.IGNORECASE
    )

    # Remove passwords
    sanitized = re.sub(
        r'(password["\']?\s*[:=]\s*["\']?)[\w-]+',
        r'\1***',
        sanitized,
        flags=re.IGNORECASE
    )

    return sanitized


if __name__ == "__main__":
    # Validate configuration
    print("Configuration validation:")
    print(f"  Database URL: {settings.get_masked_database_url()}")
    print(f"  Clockify API Key: {'*' * 20}...{settings.clockify_api_key[-4:]}")
    print(f"  Workspace ID: {settings.clockify_workspace_id}")
    print(f"  SSL Mode: {settings.db_ssl_mode}")
    print(f"  Connect Timeout: {settings.db_connect_timeout}s")
    print(f"  Statement Timeout: {settings.db_statement_timeout}ms")
    print()

    test_database_connection()
