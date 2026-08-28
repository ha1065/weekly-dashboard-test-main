#!/usr/bin/env python3
"""Fix utilization-history dataset: remove non-existent user_name column, trigger refresh."""
import boto3, time

PROFILE = 'AWSAdministratorAccess-961341524729'
REGION  = 'us-east-1'
ACCOUNT = '961341524729'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')
ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='utilization-history')['DataSet']

for pt_id, pt in ds['PhysicalTableMap'].items():
    if 'CustomSql' in pt:
        before = len(pt['CustomSql']['Columns'])
        pt['CustomSql']['Columns'] = [c for c in pt['CustomSql']['Columns'] if c['Name'] != 'user_name']
        after = len(pt['CustomSql']['Columns'])
        print(f'Removed user_name: {before} → {after} columns')
        print(f'Columns now: {[c["Name"] for c in pt["CustomSql"]["Columns"]]}')

# Also fix LogicalTableMap projected columns if present
for lt_id, lt in ds.get('LogicalTableMap', {}).items():
    for t in lt.get('DataTransforms', []):
        if 'ProjectOperation' in t:
            t['ProjectOperation']['ProjectedColumns'] = [
                c for c in t['ProjectOperation']['ProjectedColumns'] if c != 'user_name'
            ]

qs.update_data_set(AwsAccountId=ACCOUNT, DataSetId='utilization-history',
    Name=ds['Name'], ImportMode=ds['ImportMode'],
    PhysicalTableMap=ds['PhysicalTableMap'],
    LogicalTableMap=ds.get('LogicalTableMap', {}))

iid = f'fix-username-{int(time.time())}'
qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId='utilization-history', IngestionId=iid)
print(f'\nIngestion triggered: {iid}')

# Wait for completion
deadline = time.time() + 300
while time.time() < deadline:
    time.sleep(10)
    status = qs.describe_ingestion(AwsAccountId=ACCOUNT, DataSetId='utilization-history', IngestionId=iid)['Ingestion']
    s = status['IngestionStatus']
    if s in ('COMPLETED', 'FAILED', 'CANCELLED'):
        rows = status.get('RowInfo', {}).get('RowsIngested', 0)
        err  = status.get('ErrorInfo', {}).get('Message', '')
        print(f'{"✅" if s=="COMPLETED" else "❌"} {s}  rows={rows}  {err}')
        break
