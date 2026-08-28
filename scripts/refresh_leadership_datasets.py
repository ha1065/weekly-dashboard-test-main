import boto3, time
qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
datasets = ['kpi-weekly-snapshots-prod','category-hours-summary-prod','project-hours-current-week-prod','ps-stage-trend','time-compliance-history','utilization-history']
ts = int(time.time())
ingestions = {}
for ds in datasets:
    try:
        qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId=ds, IngestionId=f'pre-mtg-{ts}-{ds[:12]}')
        ingestions[ds] = f'pre-mtg-{ts}-{ds[:12]}'
        print(f'  Started: {ds}')
    except Exception as e:
        print(f'  Error {ds}: {e}')

print('\nWaiting...')
deadline = time.time() + 600
while ingestions and time.time() < deadline:
    time.sleep(15)
    done = []
    for ds, iid in list(ingestions.items()):
        status = qs.describe_ingestion(AwsAccountId=ACCOUNT, DataSetId=ds, IngestionId=iid)['Ingestion']['IngestionStatus']
        if status in ('COMPLETED', 'FAILED', 'CANCELLED'):
            print(f'  {"OK" if status=="COMPLETED" else "FAIL"} {ds}: {status}')
            done.append(ds)
    for ds in done:
        del ingestions[ds]
print('Done.')
