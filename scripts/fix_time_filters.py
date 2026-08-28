#!/usr/bin/env python3
"""Add new NB KPI tiles to week filter scope on Time & Utilization sheet."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

# Show current filter scopes on sheet-time-util
print('Current filters on sheet-time-util:')
for fg in defn['FilterGroups']:
    for sc in fg.get('ScopeConfiguration',{}).get('SelectedSheets',{}).get('SheetVisualScopingConfigurations',[]):
        if sc.get('SheetId') == 'sheet-time-util':
            print(f'  {fg["FilterGroupId"]}: scope={sc.get("Scope")}, visuals={sc.get("VisualIds",[])}')

# Add new KPI IDs to fg-util-s5 (productive_util week filter)
for fg in defn['FilterGroups']:
    if fg['FilterGroupId'] == 'fg-util-s5':
        for sc in fg['ScopeConfiguration']['SelectedSheets']['SheetVisualScopingConfigurations']:
            if sc.get('SheetId') == 'sheet-time-util':
                current = sc.get('VisualIds', [])
                new_ids = ['kpi-nb-productive', 'kpi-nb-non-productive']
                for vid in new_ids:
                    if vid not in current:
                        current.append(vid)
                sc['VisualIds'] = current
                sc['Scope'] = 'SELECTED_VISUALS'
                print(f'Updated fg-util-s5 visuals: {current}')
                break

# Also add compliance table (tbl-missing) to a week filter
# vw_missing_time_submissions uses week_start_date
# Check if there's already a filter for it
has_missing_filter = any(
    fg['FilterGroupId'] == 'fg-missing-week'
    for fg in defn['FilterGroups']
)
if not has_missing_filter:
    defn['FilterGroups'].append({
        'FilterGroupId': 'fg-missing-week',
        'Filters': [{'TimeEqualityFilter': {
            'FilterId': 'fg-missing-week',
            'Column': {'DataSetIdentifier': 'compliance', 'ColumnName': 'week_start_date'},
            'ParameterName': 'pWeekEnd',
            'TimeGranularity': 'WEEK',
        }}],
        'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [{
            'SheetId': 'sheet-time-util',
            'Scope': 'SELECTED_VISUALS',
            'VisualIds': ['tbl-missing', 'kpi-tu-missing'],
        }]}},
        'Status': 'ENABLED',
        'CrossDataset': 'SINGLE_DATASET',
    })
    print('Added fg-missing-week filter for compliance table and KPI')

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
