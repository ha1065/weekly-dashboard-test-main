#!/usr/bin/env python3
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

# Show current calculated fields
for cf in defn.get('CalculatedFields', []):
    if cf['Name'] == 'needs_attention':
        print(f'Current expression: {cf["Expression"]}')

# Fix: use a string calculated field that QuickSight can filter on
# budget_percent_used is DECIMAL, health_schedule and escalation are STRING
for cf in defn.get('CalculatedFields', []):
    if cf['Name'] == 'needs_attention':
        cf['Expression'] = "ifelse(isNotNull({budget_percent_used}) AND {budget_percent_used} > 100, '1', ifelse({health_schedule} = 'Red', '1', ifelse({escalation} = 'Yes', '1', '0')))"
        print(f'Updated expression: {cf["Expression"]}')
        break

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
