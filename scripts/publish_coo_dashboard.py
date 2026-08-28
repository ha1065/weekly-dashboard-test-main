#!/usr/bin/env python3
"""Republish COO Operational dashboard from the latest analysis version."""
import boto3

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

# Get current dashboard to preserve name and permissions
dash = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']
current_version = dash['Version']['VersionNumber']
dash_name = dash['Name']
print(f'Current published version: {current_version}')

# Pull definition from analysis and push to dashboard
analysis_defn = qs.describe_analysis_definition(
    AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID
)['Definition']

resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=dash_name,
    Definition=analysis_defn,
    ThemeArn=THEME_ARN,
)
new_version = resp['VersionArn'].split('/')[-1]
print(f'New version created: {new_version}')

# Wait for the specific new version to finish creating
import time
print('Waiting for version to be ready...')
for _ in range(30):
    versions = qs.list_dashboard_versions(
        AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID
    )['DashboardVersionSummaryList']
    match = next((v for v in versions if str(v['VersionNumber']) == str(new_version)), None)
    status = match['Status'] if match else 'UNKNOWN'
    print(f'  status: {status}')
    if status == 'CREATION_SUCCESSFUL':
        break
    if 'FAILED' in status:
        print(f'Version creation failed: {status}')
        exit(1)
    time.sleep(3)
print('Version ready')

# Publish the new version
qs.update_dashboard_published_version(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    VersionNumber=int(new_version),
)
print(f'✅ Dashboard published at version {new_version}')
