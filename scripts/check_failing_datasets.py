#!/usr/bin/env python3
"""Get the SQL/schema for the 4 failing datasets."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

failing = [
    'clockify-missing-time-submissions',
    'clockify-missing-time-submissions-prod',
    'kpi-weekly-snapshots-prod',
    'mc-v2-audit-by-phase',
]

for ds_id in failing:
    print(f'\n{"="*60}')
    print(f'Dataset: {ds_id}')
    try:
        ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId=ds_id)['DataSet']
        for tbl_id, tbl in ds.get('PhysicalTableMap', {}).items():
            if 'CustomSql' in tbl:
                print(f'SQL: {tbl["CustomSql"]["SqlQuery"][:500]}')
            elif 'RelationalTable' in tbl:
                print(f'Table: {tbl["RelationalTable"].get("Name")}')
        print(f'Columns: {[c["Name"] for c in ds.get("OutputColumns", [])[:20]]}')
    except Exception as e:
        print(f'Error: {e}')
