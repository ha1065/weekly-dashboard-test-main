#!/usr/bin/env python3
"""Switch escalation phase visuals from escalation_state to status column."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

sheet4 = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-escalations')

for v in sheet4['Visuals']:
    bar = v.get('BarChartVisual', {})
    vid = bar.get('VisualId', '')

    # Fix phase bar chart: use status instead of escalation_state
    if vid == 'bar-esc-phase':
        fw = bar['ChartConfiguration']['FieldWells']['BarChartAggregatedFieldWells']
        fw['Category'][0]['CategoricalDimensionField']['Column']['ColumnName'] = 'status'
        fw['Category'][0]['CategoricalDimensionField']['FieldId'] = 'esc-status-cat'
        # Update color map to use status values
        bar['ChartConfiguration']['VisualPalette'] = {'ColorMap': [
            {'Element': {'FieldId': 'esc-status-cat', 'FieldValue': 'To Do'},       'Color': '#D74018'},
            {'Element': {'FieldId': 'esc-status-cat', 'FieldValue': 'In Progress'}, 'Color': '#FF9B00'},
            {'Element': {'FieldId': 'esc-status-cat', 'FieldValue': 'Watching'},    'Color': '#0089DD'},
            {'Element': {'FieldId': 'esc-status-cat', 'FieldValue': 'Done'},        'Color': '#33A94F'},
        ]}
        print(f'Fixed {vid}: using status column')

    # Fix open escalations table: replace escalation_state with status
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') == 'tbl-esc':
        fw = tbl['ChartConfiguration']['FieldWells']['TableAggregatedFieldWells']
        for i, f in enumerate(fw.get('GroupBy', [])):
            col = f.get('CategoricalDimensionField', {}).get('Column', {})
            if col.get('ColumnName') == 'escalation_state':
                col['ColumnName'] = 'status'
                f['CategoricalDimensionField']['FieldId'] = f'tbl-esc-g{i}-status'
                print(f'Fixed tbl-esc: escalation_state → status')

# Also fix fg-esc-open filter to use status = Done
for fg in defn['FilterGroups']:
    if fg['FilterGroupId'] == 'fg-esc-open':
        col = fg['Filters'][0]['CategoryFilter']['Column']
        col['ColumnName'] = 'status'
        print('Fixed fg-esc-open filter: using status column')
        break

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
