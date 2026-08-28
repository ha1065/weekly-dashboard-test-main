"""Entry point for clockify-data-processor."""
from src.utils.secrets import load_secrets

load_secrets()  # must run before settings is imported via clockify integration modules

import json
from src.integrations.import_clockify_data import run_incremental_import


def lambda_handler(event, context):
    try:
        run_incremental_import()
        return {"statusCode": 200, "body": json.dumps({"status": "success"})}
    except Exception as e:
        print(f"Clockify import failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"status": "error", "message": str(e)})}
