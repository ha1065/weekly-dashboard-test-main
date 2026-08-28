import boto3, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
name = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']

total_removed = 0
for sheet in defn.get('Sheets', []):
    for layout in sheet.get('Layouts', []):
        grid = layout.get('Configuration', {}).get('GridLayout', {})
        elements = grid.get('Elements', [])
        before = len(elements)
        # Remove any element with ElementType PARAMETER_CONTROL or FILTER_CONTROL
        grid['Elements'] = [
            e for e in elements
            if e.get('ElementType') not in ('PARAMETER_CONTROL', 'FILTER_CONTROL')
        ]
        removed = before - len(grid['Elements'])
        if removed:
            print(f"Sheet {sheet.get('Name','')}: removed {removed} control GridLayout element(s)")
            total_removed += removed

print(f"Total GridLayout control elements removed: {total_removed}")

# Update analysis
try:
    qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID, Name=name, ThemeArn=THEME_ARN, Definition=defn)
    print('update_analysis submitted')
except Exception as e:
    print(f'ERROR: {e}')
    raise

# Wait
for _ in range(20):
    time.sleep(5)
    status = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Status']
    print(f'Analysis: {status}')
    if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'): break
    if 'FAILED' in status:
        print(qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID).get('Errors', []))
        break

# Republish
defn2 = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
resp = qs.update_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)', Definition=defn2, ThemeArn=THEME_ARN)
new_ver = int(resp['VersionArn'].split('/')[-1])
print(f'Creating v{new_ver}...')
for _ in range(30):
    time.sleep(4)
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
    if match and match['Status'] == 'CREATION_SUCCESSFUL':
        qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=new_ver)
        print(f'Published v{new_ver}')
        break
    elif match and 'FAILED' in match.get('Status',''):
        print(f'FAILED: {match}')
        break
    elif match:
        print(f'  {match["Status"]}')
