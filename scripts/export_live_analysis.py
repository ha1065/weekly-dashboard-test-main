#!/usr/bin/env python3
"""Export live analysis definition to coo-analysis-live.json for IaC sync."""
import boto3, json
from pathlib import Path
from datetime import datetime

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='coo-operational-analysis-prod')
out = {
    'Status': resp['Status'],
    'AnalysisId': resp['AnalysisId'],
    'Name': resp['Name'],
    'ResourceStatus': resp['ResourceStatus'],
    'ThemeArn': resp['ThemeArn'],
    'Definition': resp['Definition'],
    'RequestId': resp['RequestId'],
}
Path('/Users/cdx/weekly-reporting/weekly-reporting/coo-analysis-live.json').write_text(
    json.dumps(out, indent=4, default=str)
)
sheets = [s['Name'] for s in resp['Definition'].get('Sheets', [])]
print(f'✅ Exported {len(sheets)} sheets: {sheets}')
