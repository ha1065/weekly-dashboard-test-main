#!/usr/bin/env python3
"""
Republish dashboard from CURRENT analysis definition (not cache).
Then retry failed SPICE ingestions.
"""
import boto3, json, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

# 1. Get CURRENT analysis definition (not cache)
print('Fetching current analysis definition...')
resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']
sheets = [s['Name'] for s in defn.get('Sheets', [])]
print(f'  Sheets: {sheets}')

# 2. Publish dashboard from current analysis
resp2 = qs.update_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    Name='COO Operational Dashboard (prod)', Definition=defn, ThemeArn=THEME_ARN)
new_ver = resp2['VersionArn'].split('/')[-1]
print(f'Dashboard version {new_ver} creating...')

for _ in range(30):
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if str(v['VersionNumber']) == str(new_ver)), None)
    if match and match['Status'] == 'CREATION_SUCCESSFUL':
        break
    if match and 'FAILED' in match.get('Status', ''):
        print(f'Dashboard creation failed: {match["Status"]}')
        exit(1)
    time.sleep(3)

qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=int(new_ver))
print(f'✅ Dashboard published at version {new_ver}')

# 3. Retry failed SPICE ingestions
datasets = [
    'clockify-missing-time-submissions-prod',
    'ps-project-status-view',
]
ts = int(time.time())
for ds_id in datasets:
    try:
        qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId=ds_id,
            IngestionId=f'fix-{ts}-{ds_id[:8]}')
        print(f'✅ SPICE refresh triggered: {ds_id}')
    except Exception as e:
        print(f'⚠️  {ds_id}: {e}')
