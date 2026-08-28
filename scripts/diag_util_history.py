#!/usr/bin/env python3
import boto3, json
PROFILE = 'AWSAdministratorAccess-961341524729'
REGION  = 'us-east-1'
ACCOUNT = '961341524729'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')
lc = boto3.Session(profile_name=PROFILE, region_name=REGION).client('lambda')

# 1. Check latest ingestion status
ingestions = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId='utilization-history')['Ingestions']
latest = sorted(ingestions, key=lambda x: x['CreatedTime'], reverse=True)[0]
print(f"utilization-history ingestion: {latest['IngestionStatus']}")
print(f"  rows: {latest.get('RowInfo',{})}")
print(f"  error: {latest.get('ErrorInfo',{})}")

# 2. Check what the SQL query actually is
ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='utilization-history')['DataSet']
for pt_id, pt in ds['PhysicalTableMap'].items():
    if 'CustomSql' in pt:
        print(f"\nSQL: {pt['CustomSql']['SqlQuery'][:500]}")
        print(f"Columns defined: {[c['Name'] for c in pt['CustomSql']['Columns']]}")

# 3. Check if the view has data in the DB
r = json.loads(lc.invoke(FunctionName='production-clockify-import',
    Payload=json.dumps({'mode':'run_query','sql':'SELECT COUNT(*), MIN(week_start), MAX(week_start) FROM vw_utilization_history;'}).encode())['Payload'].read())
print(f"\nvw_utilization_history DB rows: {json.loads(r['body'])['rows']}")
