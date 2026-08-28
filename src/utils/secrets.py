import json
import os
from typing import Optional
import boto3

_cache: Optional[dict] = None


def load_secrets() -> None:
    """Fetch secret from Secrets Manager and populate env vars. Cached per Lambda container."""
    global _cache
    if _cache is not None:
        return

    secret_name = os.environ.get("SECRET_NAME")
    if not secret_name:
        return  # local dev without Secrets Manager

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    response = client.get_secret_value(SecretId=secret_name)
    _cache = json.loads(response["SecretString"])

    for key, env_var in (
        ("jira_api_token", "JIRA_API_TOKEN"),
        ("clockify_api_key", "CLOCKIFY_API_KEY"),
        ("clockify_workspace_id", "CLOCKIFY_WORKSPACE_ID"),
    ):
        if key in _cache and not os.environ.get(env_var):
            os.environ[env_var] = _cache[key]
