#!/usr/bin/env python3
"""
Fix all 4 failing SPICE datasets:
1. clockify-missing-time-submissions: remove hours_bucket from schema
2. clockify-missing-time-submissions-prod: apply_views to restore last_updated_date
3. kpi-weekly-snapshots-prod: add week_label to vw_kpi_ytd or remove from dataset
4. mc-v2-audit-by-phase: check if columns exist in table
"""
import boto3, json, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
ACCOUNT = '961341524729'

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# Step 1: Apply views to fix vw_missing_time_submissions in DB
print('Applying views...')
r = lc.invoke(FunctionName='production-clockify-import',
              Payload=json.dumps({'mode': 'apply_views'}).encode())
result = json.loads(r['Payload'].read())
print(f'apply_views: {result.get("statusCode")} — {str(result.get("body",""))[:100]}')

# Step 2: Check what columns actually exist in vw_kpi_ytd
print('\n=== vw_kpi_ytd columns ===')
cols = q("SELECT column_name FROM information_schema.columns WHERE table_name = 'vw_kpi_ytd' ORDER BY ordinal_position")
print(cols)

# Step 3: Check mc_v2_audit_by_phase table columns
print('\n=== mc_v2_audit_by_phase columns ===')
cols2 = q("SELECT column_name FROM information_schema.columns WHERE table_name = 'mc_v2_audit_by_phase' ORDER BY ordinal_position")
print(cols2)

# Step 4: Fix clockify-missing-time-submissions dataset (remove hours_bucket)
print('\nFixing clockify-missing-time-submissions dataset schema...')
ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='clockify-missing-time-submissions')['DataSet']
# Remove hours_bucket from LogicalTableMap transforms if present
for lt_id, lt in ds.get('LogicalTableMap', {}).items():
    transforms = lt.get('DataTransforms', [])
    lt['DataTransforms'] = [t for t in transforms
                            if t.get('ProjectOperation', {}).get('ProjectedColumns') is None
                            or 'hours_bucket' not in str(t)]

# Update dataset to remove hours_bucket from physical table columns
for pt_id, pt in ds.get('PhysicalTableMap', {}).items():
    if 'RelationalTable' in pt:
        cols = pt['RelationalTable'].get('InputColumns', [])
        pt['RelationalTable']['InputColumns'] = [c for c in cols if c['Name'] != 'hours_bucket']
        print(f'  Removed hours_bucket from {pt_id}')

try:
    qs.update_data_set(
        AwsAccountId=ACCOUNT,
        DataSetId='clockify-missing-time-submissions',
        Name=ds['Name'],
        ImportMode=ds['ImportMode'],
        PhysicalTableMap=ds['PhysicalTableMap'],
        LogicalTableMap=ds.get('LogicalTableMap', {}),
    )
    print('  ✅ clockify-missing-time-submissions updated')
except Exception as e:
    print(f'  ⚠️  {e}')

# Step 5: Trigger SPICE refreshes for all 4 datasets
print('\nTriggering SPICE refreshes...')
ts = int(time.time())
for ds_id in [
    'clockify-missing-time-submissions',
    'clockify-missing-time-submissions-prod',
    'kpi-weekly-snapshots-prod',
    'mc-v2-audit-by-phase',
]:
    try:
        qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId=ds_id,
            IngestionId=f'fix2-{ts}-{ds_id[:12]}')
        print(f'  ✅ {ds_id}')
    except Exception as e:
        print(f'  ⚠️  {ds_id}: {e}')
