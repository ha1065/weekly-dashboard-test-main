#!/usr/bin/env python3
"""
Fix tbl-ps-projects:
1. Restore alternating row colors (purple theme)
2. Fix health column — cell-level CF with dark theme colors
3. Fix escalation column — data values are Green/Red not Yes/No
"""
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

    # 1. Restore alternating row colors
    tbl['ChartConfiguration']['TableOptions']['RowAlternateColorOptions'] = {
        'Status': 'ENABLED',
        'RowAlternateColors': ['#2A1545']
    }

    # 2. Rebuild CF — cell-level only, solid CE colors visible on dark background
    tbl['ConditionalFormatting'] = {
        'ConditionalFormattingOptions': [
            # Health cell (g5) — values: Red, Yellow, Green
            {'Cell': {'FieldId': 'tbl-ps-projects-g5', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health} = 'Red'", 'Color': '#D74018'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g5', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health} = 'Yellow'", 'Color': '#FF9B00'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g5', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health} = 'Green'", 'Color': '#33A94F'}}}}},
            # Budget Health cell (g6)
            {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_budget} = 'Red'", 'Color': '#D74018'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_budget} = 'Yellow'", 'Color': '#FF9B00'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_budget} = 'Green'", 'Color': '#33A94F'}}}}},
            # Schedule Health cell (g7)
            {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_schedule} = 'Red'", 'Color': '#D74018'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_schedule} = 'Yellow'", 'Color': '#FF9B00'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_schedule} = 'Green'", 'Color': '#33A94F'}}}}},
            # Escalation cell (g8) — values are Green/Red (same as health)
            {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{escalation} = 'Red'", 'Color': '#D74018'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{escalation} = 'Green'", 'Color': '#33A94F'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{escalation} = 'Yes'", 'Color': '#D74018'}}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{escalation} = 'No'", 'Color': '#33A94F'}}}}},
        ]
    }
    print('✅ Fixed tbl-ps-projects CF and row colors')
    break

# Update analysis
qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print('Analysis updated')

# Publish dashboard
resp2 = qs.update_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    Name='COO Operational Dashboard (prod)', Definition=defn, ThemeArn=THEME_ARN)
new_ver = resp2['VersionArn'].split('/')[-1]
print(f'Dashboard version {new_ver} creating...')

for _ in range(30):
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if str(v['VersionNumber']) == str(new_ver)), None)
    status = match['Status'] if match else 'UNKNOWN'
    if status == 'CREATION_SUCCESSFUL':
        break
    if 'FAILED' in status:
        print(f'Failed: {status}'); exit(1)
    time.sleep(3)

qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=int(new_ver))
print(f'✅ Published version {new_ver}')
