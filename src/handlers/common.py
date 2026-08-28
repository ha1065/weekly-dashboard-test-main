"""Common bootstrap helpers shared across all handler modules.

Provides:
  - get_secrets           – retrieve dict from AWS Secrets Manager
  - get_db_endpoint       – resolve DB host from SSM or env
  - set_environment_from_secrets – populate os.environ so database config
                            can be imported safely afterward
  - send_sns_notification – fire-and-forget SNS publish
"""

import json
import os
from typing import Dict

import boto3


def get_secrets() -> Dict[str, str]:
    """Retrieve secrets from AWS Secrets Manager."""
    secret_name = os.environ.get('SECRET_NAME')
    region_name = os.environ.get('AWS_REGION', 'us-east-1')

    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error retrieving secrets: {e}")
        raise


def get_db_endpoint() -> str:
    """Get database endpoint from SSM Parameter Store."""
    parameter_name = os.environ.get('DB_ENDPOINT_PARAMETER')
    if not parameter_name:
        # Fallback to DB_HOST env var if parameter name not set
        return os.environ.get('DB_HOST', '')

    ssm = boto3.client('ssm')
    try:
        response = ssm.get_parameter(Name=parameter_name)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error retrieving DB endpoint from SSM: {e}")
        # Fallback to DB_HOST env var
        return os.environ.get('DB_HOST', '')


def set_environment_from_secrets(secrets: Dict[str, str]):
    """Set environment variables from secrets and build connection string."""
    # Get database info from environment variables and SSM
    db_host = get_db_endpoint()
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'weekly_reporting')
    db_user = os.environ.get('DB_USER', 'report_user')
    db_password = secrets.get('db_password', '')

    # Build connection string using pg8000 driver (pure Python, Lambda compatible)
    database_url = f"postgresql+pg8000://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    os.environ['DATABASE_URL'] = database_url
    os.environ['CLOCKIFY_API_KEY'] = secrets.get('clockify_api_key', '')
    os.environ['CLOCKIFY_WORKSPACE_ID'] = secrets.get('clockify_workspace_id', '')
    # Jira settings (optional)
    os.environ['JIRA_BASE_URL'] = secrets.get('jira_base_url', '')
    os.environ['JIRA_API_EMAIL'] = secrets.get('jira_api_email', '')
    os.environ['JIRA_API_TOKEN'] = secrets.get('jira_api_token', '')
    os.environ['JIRA_PROJECT_KEYS'] = secrets.get('jira_project_keys', '')
    os.environ['JIRA_PHASE_FIELD_ID'] = secrets.get('jira_phase_field_id', '')


def send_sns_notification(topic_arn: str, subject: str, message: str):
    """Send notification via SNS."""
    if not topic_arn:
        return

    sns = boto3.client('sns')
    try:
        sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print(f"Failed to send SNS notification: {e}")
