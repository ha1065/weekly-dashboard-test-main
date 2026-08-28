#!/usr/bin/env python3
"""Restore the CE theme on the COO dashboard after update_dashboard reset it."""
import boto3, time

PROFILE      = 'AWSAdministratorAccess-961341524729'
REGION       = 'us-east-1'
ACCOUNT      = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# Find the CE theme
themes = qs.list_themes(AwsAccountId=ACCOUNT, Type='CUSTOM')['ThemeSummaryList']
for t in themes:
    print(f"  {t['ThemeId']}  {t['Name']}")

theme = next((t for t in themes if 'cloud' in t['Name'].lower() or 'ce' in t['Name'].lower()), None)
if not theme:
    print('CE theme not found above — set THEME_ID manually')
    raise SystemExit

THEME_ID  = theme['ThemeId']
THEME_ARN = theme['Arn']
print(f'\nRestoring theme: {theme["Name"]} ({THEME_ID})')

# Get current definition
resp  = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)
defn  = resp['Definition']
name  = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']['Name']

# Apply theme ARN
resp2 = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=name,
    Definition=defn,
    ThemeArn=THEME_ARN,
    VersionDescription='Restore CE theme after Utilization Detail sheet addition'
)
version = int(resp2['VersionArn'].split('/')[-1])
print(f'Version {version} created. Waiting 5s...')
time.sleep(5)

qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
print(f'✅ Theme restored and version {version} published.')
