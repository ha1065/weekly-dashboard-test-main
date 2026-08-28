"""Database configuration and connection management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional
import os
import json
from dotenv import load_dotenv

load_dotenv()


def get_secret():
    """Get secrets from AWS Secrets Manager."""
    secret_name = os.getenv("SECRET_NAME")
    if not secret_name:
        return None

    try:
        import boto3
        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Warning: Could not retrieve secrets from Secrets Manager: {e}")
        return None


def get_database_url():
    """Construct database URL from environment or Secrets Manager."""
    # First try direct DATABASE_URL (for local development)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    # Try to build from individual components (for AWS deployment)
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "weekly_reporting")
    db_user = os.getenv("DB_USER", "postgres")

    # Get password from Secrets Manager or environment
    db_password = os.getenv("DB_PASSWORD")
    if not db_password:
        secrets = get_secret()
        if secrets:
            db_password = secrets.get("db_password")

    if db_host and db_password:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    raise ValueError(
        "Database configuration not found. Set DATABASE_URL or "
        "DB_HOST/DB_PASSWORD environment variables."
    )


class Settings:
    """Application settings."""

    def __init__(self):
        self.database_url = get_database_url()
        # Clockify settings - optional, only needed for imports
        self.clockify_api_key = os.getenv("CLOCKIFY_API_KEY", "")
        self.clockify_workspace_id = os.getenv("CLOCKIFY_WORKSPACE_ID", "")
        # Jira settings - optional, only needed for Jira imports
        self.jira_base_url = os.getenv("JIRA_BASE_URL", "")
        self.jira_api_email = os.getenv("JIRA_API_EMAIL", "")
        self.jira_api_token = os.getenv("JIRA_API_TOKEN", "")
        self.jira_project_keys = [k.strip() for k in os.getenv("JIRA_PROJECT_KEYS", "").split(",") if k.strip()]
        self.jira_phase_field_id = os.getenv("JIRA_PHASE_FIELD_ID", "")
        # Issue types that classify a Jira issue as Managed Cloud (MC); all others → PS
        _mc_types_raw = os.getenv("MC_ISSUE_TYPES", "Managed Services")
        self.mc_issue_types = [t.strip() for t in _mc_types_raw.split(",") if t.strip()]

        # Fall back to Secrets Manager for API credentials not in env vars
        # (needed in ECS/Streamlit context where Lambda secrets injection isn't used)
        if not self.clockify_api_key or not self.clockify_workspace_id:
            secrets = get_secret()
            if secrets:
                if not self.clockify_api_key:
                    self.clockify_api_key = secrets.get("clockify_api_key", "")
                if not self.clockify_workspace_id:
                    self.clockify_workspace_id = secrets.get("clockify_workspace_id", "")
                if not self.jira_base_url:
                    self.jira_base_url = secrets.get("jira_base_url", "")
                if not self.jira_api_email:
                    self.jira_api_email = secrets.get("jira_api_email", "")
                if not self.jira_api_token:
                    self.jira_api_token = secrets.get("jira_api_token", "")


settings = Settings()

# Create SQLAlchemy engine
engine = create_engine(settings.database_url)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()