#!/usr/bin/env python3
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

# Remove any existing issue_type filter to avoid duplicates
defn['FilterGroups'] = [fg for fg in defn['FilterGroups'] if fg['FilterGroupId'] != 'fg-ps-issue-emailed']

# Add: only show Emailed request issue type (standard PS projects on CST board)
defn['FilterGroups'].append({
    'FilterGroupId': 'fg-ps-issue-emailed',
    'Filters': [{'CategoryFilter': {
        'FilterId': 'fg-ps-issue-emailed',
        'Column': {'DataSetIdentifier': 'ps_projects', 'ColumnName': 'issue_type'},
        'Configuration': {'FilterListConfiguration': {
            'MatchOperator': 'CONTAINS',
            'CategoryValues': ['Emailed request'],
            'NullOption': 'NON_NULLS_ONLY',
        }},
    }}],
    'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
        {'SheetId': 'sheet-ps-delivery', 'Scope': 'ALL_VISUALS'}
    ]}},
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET',
})

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
