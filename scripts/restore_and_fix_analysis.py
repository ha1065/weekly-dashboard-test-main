#!/usr/bin/env python3
"""
Restore analysis from coo-analysis-live.json, then apply correct CF
(no trim() — data is now clean after fix_escalation_data.py).
"""
import boto3, json, time
from pathlib import Path

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

# Load last known good definition
cached = Path('/Users/cdx/weekly-reporting/weekly-reporting/coo-analysis-live.json')
defn = json.loads(cached.read_text())['Definition']
print(f"Restoring from cache: {len(defn.get('Sheets', []))} sheets")

# Apply correct CF to tbl-ps-projects (no trim, plain equality)
sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-ps-delivery')
for v in sheet['Visuals']:
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') != 'tbl-ps-projects':
        continue
    tbl['ChartConfiguration']['TableOptions']['RowAlternateColorOptions'] = {
        'Status': 'ENABLED', 'RowAlternateColors': ['#2A1545']
    }
    tbl['ConditionalFormatting'] = {'ConditionalFormattingOptions': [
        # Health (g5)
        {'Cell': {'FieldId': 'tbl-ps-projects-g5', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health} = 'Red'",    'Color': '#D74018'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g5', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health} = 'Yellow'", 'Color': '#FF9B00'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g5', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health} = 'Green'",  'Color': '#33A94F'}}}}},
        # Budget Health (g6)
        {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health_budget} = 'Red'",    'Color': '#D74018'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health_budget} = 'Yellow'", 'Color': '#FF9B00'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health_budget} = 'Green'",  'Color': '#33A94F'}}}}},
        # Schedule Health (g7)
        {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health_schedule} = 'Red'",    'Color': '#D74018'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health_schedule} = 'Yellow'", 'Color': '#FF9B00'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{health_schedule} = 'Green'",  'Color': '#33A94F'}}}}},
        # Escalation (g8) — data is now clean (no trailing space)
        {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{escalation} = 'Red'",   'Color': '#D74018'}}}}},
        {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {'BackgroundColor': {'Solid': {'Expression': "{escalation} = 'Green'", 'Color': '#33A94F'}}}}},
    ]}
    print('✅ CF applied to tbl-ps-projects')
    break

# Restore analysis
resp = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Analysis update status: {resp["Status"]}')

# Republish dashboard
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
        print(f'Failed: {match["Status"]}'); exit(1)
    time.sleep(3)

qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=int(new_ver))
print(f'✅ Published version {new_ver}')
