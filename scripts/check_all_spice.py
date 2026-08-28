#!/usr/bin/env python3
"""Check latest ingestion status and error details for all datasets."""
import boto3
from datetime import timezone

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

datasets = qs.list_data_sets(AwsAccountId=ACCOUNT)['DataSetSummaries']
print(f'{"Dataset":<50} {"Status":<25} {"Created":<30} {"Error"}')
print('-' * 130)

for ds in sorted(datasets, key=lambda x: x['DataSetId']):
    try:
        ingestions = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId=ds['DataSetId'])['Ingestions']
        if not ingestions:
            continue
        latest = sorted(ingestions, key=lambda x: x['CreatedTime'], reverse=True)[0]
        status = latest['IngestionStatus']
        created = latest['CreatedTime'].strftime('%Y-%m-%d %H:%M')
        error = latest.get('ErrorInfo', {}).get('Message', '') if 'FAILED' in status else ''
        print(f'{ds["DataSetId"]:<50} {status:<25} {created:<30} {error[:60]}')
    except Exception as e:
        print(f'{ds["DataSetId"]:<50} ERROR: {str(e)[:60]}')
