#!/usr/bin/env python3
"""Fix all 4 failing datasets properly."""
import boto3, json, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
ACCOUNT = '961341524729'

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# ── 1. Fix vw_missing_time_submissions in DB directly ─────────────────────
# apply_views returned None — run the view SQL directly
print('Rebuilding vw_missing_time_submissions...')
view_sql = open('/Users/cdx/weekly-reporting/weekly-reporting/src/database/create_views.sql').read()
# Extract just the vw_missing_time_submissions block
start = view_sql.find('DROP VIEW IF EXISTS vw_missing_time_submissions')
end = view_sql.find('\n-- ===', start + 10)
missing_time_sql = view_sql[start:end].strip()
result = q(missing_time_sql)
print(f'  View rebuild: {result.get("statusCode")}')

# ── 2. Fix clockify-missing-time-submissions dataset (remove hours_bucket) ─
print('\nFixing clockify-missing-time-submissions...')
ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='clockify-missing-time-submissions')['DataSet']
for pt_id, pt in ds['PhysicalTableMap'].items():
    if 'RelationalTable' in pt:
        pt['RelationalTable']['InputColumns'] = [
            c for c in pt['RelationalTable']['InputColumns'] if c['Name'] != 'hours_bucket'
        ]
# Remove hours_bucket from LogicalTableMap projected columns
for lt_id, lt in ds.get('LogicalTableMap', {}).items():
    for t in lt.get('DataTransforms', []):
        if 'ProjectOperation' in t:
            t['ProjectOperation']['ProjectedColumns'] = [
                c for c in t['ProjectOperation']['ProjectedColumns'] if c != 'hours_bucket'
            ]
try:
    qs.update_data_set(
        AwsAccountId=ACCOUNT,
        DataSetId='clockify-missing-time-submissions',
        Name=ds['Name'], ImportMode=ds['ImportMode'],
        PhysicalTableMap=ds['PhysicalTableMap'],
        LogicalTableMap=ds['LogicalTableMap'],
    )
    print('  ✅ Updated')
except Exception as e:
    print(f'  ⚠️  {e}')

# ── 3. Fix kpi-weekly-snapshots-prod (remove week_label) ──────────────────
print('\nFixing kpi-weekly-snapshots-prod...')
ds2 = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod')['DataSet']
for pt_id, pt in ds2['PhysicalTableMap'].items():
    if 'RelationalTable' in pt:
        pt['RelationalTable']['InputColumns'] = [
            c for c in pt['RelationalTable']['InputColumns'] if c['Name'] != 'week_label'
        ]
for lt_id, lt in ds2.get('LogicalTableMap', {}).items():
    for t in lt.get('DataTransforms', []):
        if 'ProjectOperation' in t:
            t['ProjectOperation']['ProjectedColumns'] = [
                c for c in t['ProjectOperation']['ProjectedColumns'] if c != 'week_label'
            ]
try:
    qs.update_data_set(
        AwsAccountId=ACCOUNT,
        DataSetId='kpi-weekly-snapshots-prod',
        Name=ds2['Name'], ImportMode=ds2['ImportMode'],
        PhysicalTableMap=ds2['PhysicalTableMap'],
        LogicalTableMap=ds2['LogicalTableMap'],
    )
    print('  ✅ Updated')
except Exception as e:
    print(f'  ⚠️  {e}')

# ── 4. Fix mc-v2-audit-by-phase (replace done_summary/remaining_summary with narrative) ──
print('\nFixing mc-v2-audit-by-phase...')
ds3 = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='mc-v2-audit-by-phase')['DataSet']
for pt_id, pt in ds3['PhysicalTableMap'].items():
    if 'CustomSql' in pt:
        pt['CustomSql']['SqlQuery'] = (
            "SELECT id, week_start, customer_name, jira_project_key, phase_name, "
            "phase_order, total_items, done_items, in_progress_items, todo_items, "
            "completion_pct, narrative, analyzed_at FROM mc_v2_audit_by_phase"
        )
        pt['CustomSql']['Columns'] = [
            c for c in pt['CustomSql']['Columns']
            if c['Name'] not in ('done_summary', 'remaining_summary')
        ]
        # Add narrative if not present
        if not any(c['Name'] == 'narrative' for c in pt['CustomSql']['Columns']):
            pt['CustomSql']['Columns'].append({'Name': 'narrative', 'Type': 'STRING'})
for lt_id, lt in ds3.get('LogicalTableMap', {}).items():
    for t in lt.get('DataTransforms', []):
        if 'ProjectOperation' in t:
            cols = t['ProjectOperation']['ProjectedColumns']
            cols[:] = [c for c in cols if c not in ('done_summary', 'remaining_summary')]
            if 'narrative' not in cols:
                cols.append('narrative')
try:
    qs.update_data_set(
        AwsAccountId=ACCOUNT,
        DataSetId='mc-v2-audit-by-phase',
        Name=ds3['Name'], ImportMode=ds3['ImportMode'],
        PhysicalTableMap=ds3['PhysicalTableMap'],
        LogicalTableMap=ds3['LogicalTableMap'],
    )
    print('  ✅ Updated')
except Exception as e:
    print(f'  ⚠️  {e}')

# ── 5. Trigger SPICE refreshes ─────────────────────────────────────────────
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
            IngestionId=f'fix3-{ts}-{ds_id[:12]}')
        print(f'  ✅ {ds_id}')
    except Exception as e:
        print(f'  ⚠️  {ds_id}: {e}')
