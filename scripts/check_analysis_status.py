#!/usr/bin/env python3
"""Check analysis status and top-level definition keys."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='coo-operational-analysis-prod')
print('Top-level keys:', list(resp.keys()))
print('ResourceStatus:', resp.get('ResourceStatus'))
print('Errors:', resp.get('Errors'))
if 'Definition' in resp:
    print('Definition keys:', list(resp['Definition'].keys()))
    print('Sheet count:', len(resp['Definition'].get('Sheets', [])))
    for s in resp['Definition'].get('Sheets', []):
        print(f"  {s['SheetId']} — {s['Name']}")
