#!/usr/bin/env python3
"""S03-05: Update mc-v2-audit QS dataset SQL to JOIN artifact_verification."""
import boto3

PROFILE = 'AWSAdministratorAccess-961341524729'
REGION = 'us-east-1'
ACCOUNT = '961341524729'
DATASET_ID = 'mc-v2-audit'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')
ds = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId=DATASET_ID)['DataSet']

for pt_id, pt in ds['PhysicalTableMap'].items():
    if 'CustomSql' in pt:
        existing_sql = pt['CustomSql']['SqlQuery']
        if 'artifact_verification' not in existing_sql:
            print(f'Existing SQL (first 500 chars):\n{existing_sql[:500]}')
            print('\nAdd LEFT JOIN artifact_verification av ON ps.issue_key = av.jira_issue_id')
            print('And SELECT: av.artifact_present, av.artifact_url, av.artifact_verified_at')
            print('Then update pt["CustomSql"]["SqlQuery"] and pt["CustomSql"]["Columns"] accordingly')
        break

print('\nRun this script to inspect the current SQL, then update manually or extend this script.')
