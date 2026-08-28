#!/usr/bin/env python3
"""Fix tbl-ps-projects: disable row alternate colors so cell conditional formatting is visible."""
import boto3

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-ps-delivery')

for v in sheet['Visuals']:
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') != 'tbl-ps-projects':
        continue

    # Disable alternating row colors so cell-level CF wins
    tbl['ChartConfiguration']['TableOptions']['RowAlternateColorOptions'] = {
        'Status': 'DISABLED'
    }
    print('Disabled row alternate colors on tbl-ps-projects')
    break

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
