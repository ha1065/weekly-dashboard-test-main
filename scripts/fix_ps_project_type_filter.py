#!/usr/bin/env python3
import boto3

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'
FG_ID = 'fg-ps-project-type'
CTRL_ID = 'ctrl-ps-project-type'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

# Check if already present
fg_ids = [fg['FilterGroupId'] for fg in defn.get('FilterGroups', [])]
ps_sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-ps-delivery')
ctrl_ids = [list(fc.values())[0]['FilterControlId'] for fc in ps_sheet.get('FilterControls', [])]

if FG_ID in fg_ids and CTRL_ID in ctrl_ids:
    print('Already present — nothing to do.')
    exit(0)

# Remove stale copies if partially present
defn['FilterGroups'] = [fg for fg in defn['FilterGroups'] if fg['FilterGroupId'] != FG_ID]
ps_sheet['FilterControls'] = [fc for fc in ps_sheet.get('FilterControls', [])
                               if list(fc.values())[0].get('FilterControlId') != CTRL_ID]

# Add FilterGroup
defn['FilterGroups'].append({
    'FilterGroupId': FG_ID,
    'Filters': [{
        'CategoryFilter': {
            'FilterId': FG_ID,
            'Column': {'DataSetIdentifier': 'ps_at_risk', 'ColumnName': 'type'},
            'Configuration': {'FilterListConfiguration': {
                'MatchOperator': 'CONTAINS',
                'SelectAllOptions': 'FILTER_ALL_VALUES',
            }},
        }
    }],
    'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
        {'SheetId': 'sheet-ps-delivery', 'Scope': 'ALL_VISUALS'}
    ]}},
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET',
})

# Add FilterControl to sheet-ps-delivery
ps_sheet.setdefault('FilterControls', []).append({
    'Dropdown': {
        'FilterControlId': CTRL_ID,
        'Title': 'Project Type',
        'SourceFilterId': FG_ID,
        'Type': 'MULTI_SELECT',
    }
})

resp2 = qs.update_analysis(
    AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn,
)
print(f'Status: {resp2["Status"]}')
