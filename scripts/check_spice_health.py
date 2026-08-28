#!/usr/bin/env python3
"""Check SPICE refresh health for all production datasets."""
import boto3

PROFILE = 'AWSAdministratorAccess-961341524729'
REGION  = 'us-east-1'
ACCOUNT = '961341524729'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# Get all datasets
datasets = qs.list_data_sets(AwsAccountId=ACCOUNT)['DataSetSummaries']

print(f'Checking {len(datasets)} datasets...\n')
print(f'{"Dataset":<50} {"Status":<12} {"Date":<22} {"Error"}')
print('-' * 120)

failed = []
for ds in sorted(datasets, key=lambda x: x['Name']):
    ds_id   = ds['DataSetId']
    ds_name = ds['Name']
    try:
        ingestions = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId=ds_id)['Ingestions']
        if not ingestions:
            print(f'{ds_name:<50} {"NO INGESTIONS":<12}')
            continue
        latest  = sorted(ingestions, key=lambda x: x['CreatedTime'], reverse=True)[0]
        status  = latest['IngestionStatus']
        date    = latest['CreatedTime'].strftime('%Y-%m-%d %H:%M')
        error   = latest.get('ErrorInfo', {}).get('Message', '')[:60]
        icon    = '✅' if status == 'COMPLETED' else '❌' if status == 'FAILED' else '⏳'
        print(f'{icon} {ds_name:<48} {status:<12} {date:<22} {error}')
        if status == 'FAILED':
            failed.append((ds_name, ds_id, error))
    except Exception as e:
        print(f'⚠️  {ds_name:<48} ERROR: {str(e)[:60]}')

print(f'\n{"="*120}')
if failed:
    print(f'\n❌ {len(failed)} FAILED datasets:')
    for name, ds_id, err in failed:
        print(f'  - {name} ({ds_id})')
        print(f'    {err}')
else:
    print('\n✅ All datasets healthy.')
