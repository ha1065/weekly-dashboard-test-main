#!/usr/bin/env python3
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']
sheet2 = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-ps-delivery')

for v in sheet2['Visuals']:
    pie = v.get('PieChartVisual')
    if pie and pie.get('VisualId') == 'donut-ps-health':
        fw = pie['ChartConfiguration']['FieldWells']['PieChartAggregatedFieldWells']
        print(f'Current category: {fw["Category"][0].get("CategoricalDimensionField",{}).get("Column",{}).get("ColumnName")}')

        # Ensure category = health (health_overall aliased in view)
        fw['Category'] = [{'CategoricalDimensionField': {
            'FieldId': 'donut-cat',
            'Column': {'DataSetIdentifier': 'ps_projects', 'ColumnName': 'health'},
        }}]
        # Count projects per health value
        fw['Values'] = [{'NumericalMeasureField': {
            'FieldId': 'donut-val',
            'Column': {'DataSetIdentifier': 'ps_projects', 'ColumnName': 'budget_hours'},
            'AggregationFunction': {'SimpleNumericalAggregation': 'DISTINCT_COUNT'},
        }}]
        # Color map: Green, Red, Not Assigned (grey)
        pie['ChartConfiguration']['VisualPalette'] = {'ColorMap': [
            {'Element': {'FieldId': 'donut-cat', 'FieldValue': 'Green'},        'Color': '#33A94F'},
            {'Element': {'FieldId': 'donut-cat', 'FieldValue': 'Red'},          'Color': '#D74018'},
            {'Element': {'FieldId': 'donut-cat', 'FieldValue': 'Not Assigned'}, 'Color': '#AAAAAA'},
        ]}
        print('Fixed donut: health column, Green/Red/Not Assigned colors')
        break

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
