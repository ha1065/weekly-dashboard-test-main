#!/usr/bin/env python3
"""
Rebuild kpi-weekly-snapshots-prod dataset schema from actual vw_kpi_ytd columns,
then republish the dashboard.
"""
import boto3, json, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
ACCOUNT = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# 1. Get actual columns from live view
print('Getting live vw_kpi_ytd columns...')
result = q("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'vw_kpi_ytd'
    ORDER BY ordinal_position
""")
cols_raw = json.loads(result['body'])['rows']
print(f'  Found {len(cols_raw)} columns')

# Map postgres types to QuickSight types
def qs_type(pg_type):
    if 'int' in pg_type: return 'INTEGER'
    if pg_type in ('numeric', 'real', 'double precision', 'decimal'): return 'DECIMAL'
    if 'timestamp' in pg_type or 'date' in pg_type: return 'DATETIME'
    return 'STRING'

input_cols = [{'Name': row[0], 'Type': qs_type(row[1])} for row in cols_raw]

# 2. Get current dataset
ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod')['DataSet']

# 3. Replace physical table columns
for pt_id, pt in ds['PhysicalTableMap'].items():
    if 'RelationalTable' in pt:
        pt['RelationalTable']['InputColumns'] = input_cols
        print(f'  Updated {pt_id} with {len(input_cols)} columns')

# 4. Update logical table projected columns
for lt_id, lt in ds.get('LogicalTableMap', {}).items():
    for t in lt.get('DataTransforms', []):
        if 'ProjectOperation' in t:
            t['ProjectOperation']['ProjectedColumns'] = [c['Name'] for c in input_cols]

# 5. Update dataset
qs.update_data_set(
    AwsAccountId=ACCOUNT,
    DataSetId='kpi-weekly-snapshots-prod',
    Name=ds['Name'], ImportMode=ds['ImportMode'],
    PhysicalTableMap=ds['PhysicalTableMap'],
    LogicalTableMap=ds['LogicalTableMap'],
)
print('✅ Dataset schema updated')

# 6. Trigger SPICE refresh and wait
ingestion_id = f'rebuild-{int(time.time())}'
qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod',
    IngestionId=ingestion_id)
print('Waiting for SPICE...')
for _ in range(40):
    ing = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod')['Ingestions']
    match = next((i for i in ing if i['IngestionId'] == ingestion_id), None)
    if match:
        status = match['IngestionStatus']
        if status == 'COMPLETED':
            print(f'✅ SPICE completed ({match["RowInfo"].get("RowsIngested")} rows)')
            break
        if 'FAILED' in status:
            print(f'❌ SPICE failed: {match.get("ErrorInfo")}')
            exit(1)
    time.sleep(3)

# 7. Republish dashboard
print('Republishing dashboard...')
resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='coo-operational-analysis-prod')
defn = resp['Definition']

resp2 = qs.update_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    Name='COO Operational Dashboard (prod)', Definition=defn, ThemeArn=THEME_ARN)
new_ver = resp2['VersionArn'].split('/')[-1]

for _ in range(30):
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if str(v['VersionNumber']) == str(new_ver)), None)
    if match and match['Status'] == 'CREATION_SUCCESSFUL':
        break
    if match and 'FAILED' in match.get('Status', ''):
        # Get errors
        errors = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
            VersionNumber=int(new_ver))['Dashboard']['Version'].get('Errors', [])
        for e in errors[:5]:
            print(f'  ERROR: {e["Type"]}: {e["Message"][:150]}')
        exit(1)
    time.sleep(3)

qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    VersionNumber=int(new_ver))
print(f'✅ Dashboard published at version {new_ver}')
