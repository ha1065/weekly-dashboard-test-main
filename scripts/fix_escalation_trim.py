#!/usr/bin/env python3
"""Fix escalation CF: use trim() to handle trailing space in 'Green ' value."""
import boto3, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-ps-delivery')

for v in sheet['Visuals']:
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') != 'tbl-ps-projects':
        continue

    opts = tbl['ConditionalFormatting']['ConditionalFormattingOptions']

    # Replace escalation CF rules with trim()-based expressions
    opts[:] = [o for o in opts if o.get('Cell', {}).get('FieldId') != 'tbl-ps-projects-g8']

    opts += [
        {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {
            'Expression': "trim({escalation}) = 'Red'", 'Color': '#D74018'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {
            'Expression': "trim({escalation}) = 'Green'", 'Color': '#33A94F'}}}}},
    ]
    print('✅ Updated escalation CF with trim()')
    break

qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)

resp2 = qs.update_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    Name='COO Operational Dashboard (prod)', Definition=defn, ThemeArn=THEME_ARN)
new_ver = resp2['VersionArn'].split('/')[-1]

for _ in range(30):
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if str(v['VersionNumber']) == str(new_ver)), None)
    if match and match['Status'] == 'CREATION_SUCCESSFUL':
        break
    if match and 'FAILED' in match['Status']:
        print(f'Failed: {match["Status"]}'); exit(1)
    time.sleep(3)

qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=int(new_ver))
print(f'✅ Published version {new_ver}')
