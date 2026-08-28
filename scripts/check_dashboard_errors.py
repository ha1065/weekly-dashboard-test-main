#!/usr/bin/env python3
"""Get dashboard version 12 error details."""
import boto3

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'

versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
for v in sorted(versions, key=lambda x: x['VersionNumber'], reverse=True)[:3]:
    print(f"Version {v['VersionNumber']}: {v['Status']}")
    if v['Status'] == 'CREATION_FAILED':
        detail = qs.describe_dashboard(
            AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
            VersionNumber=v['VersionNumber']
        )
        errors = detail['Dashboard']['Version'].get('Errors', [])
        for e in errors:
            print(f"  {e['Type']}: {e['Message'][:200]}")
