"""Entry point for jira-data-pull-lambda."""
from src.utils.secrets import load_secrets

load_secrets()  # must run before settings is imported via jira integration modules

import json
from src.integrations.import_jira_data import run_jira_import


def lambda_handler(event, context):
    try:
        run_jira_import()
        return {"statusCode": 200, "body": json.dumps({"status": "success"})}
    except Exception as e:
        print(f"Jira import failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"status": "error", "message": str(e)})}
