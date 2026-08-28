#!/usr/bin/env python3
"""Check vw_kpi_ytd data and SPICE status."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
ACCOUNT = '961341524729'

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# 1. Check view exists and has data
print('=== vw_kpi_ytd row count ===')
print(q("SELECT COUNT(*) FROM vw_kpi_ytd"))

# 2. Check latest 2 rows with key fields
print('\n=== Latest 2 weeks of KPI data ===')
print(q("""SELECT week_start_date, billable_util_pct, billable_util_prev,
           ps_active_projects, ps_active_prev, open_escalations, escalations_prev
           FROM vw_kpi_ytd ORDER BY week_start_date DESC LIMIT 2"""))

# 3. Check SPICE ingestion status
ingestions = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod')['Ingestions']
latest = sorted(ingestions, key=lambda x: x['CreatedTime'], reverse=True)[0]
print(f'\n=== kpi-weekly-snapshots-prod SPICE ===')
print(f'Status: {latest["IngestionStatus"]}')
print(f'Created: {latest["CreatedTime"]}')
if 'ErrorInfo' in latest:
    print(f'Error: {latest["ErrorInfo"]}')
if 'RowInfo' in latest:
    print(f'Rows: {latest["RowInfo"].get("RowsIngested")}')
