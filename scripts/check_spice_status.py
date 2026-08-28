#!/usr/bin/env python3
"""Check SPICE ingestion status and verify escalation values in dataset."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
ACCOUNT = '961341524729'

# 1. Check latest ingestion status for ps-project-status-view
ingestions = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId='ps-project-status-view')['Ingestions']
latest = sorted(ingestions, key=lambda x: x['CreatedTime'], reverse=True)[0]
print(f"Latest ingestion: {latest['IngestionId']}")
print(f"  Status: {latest['IngestionStatus']}")
print(f"  Created: {latest['CreatedTime']}")
if 'RowInfo' in latest:
    print(f"  Rows: {latest['RowInfo'].get('RowsIngested')}")

# 2. Check live DB escalation values
def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('\n=== Live DB escalation values (after view fix) ===')
result = q("SELECT client_name, project_name, escalation, length(escalation) as len FROM vw_ps_project_status WHERE status_category != 'Done' AND escalation IS NOT NULL LIMIT 10")
print(json.dumps(result, indent=2))
