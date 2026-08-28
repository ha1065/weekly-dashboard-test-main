#!/usr/bin/env python3
"""Dump tbl-ps-projects current state for diagnosis."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-ps-delivery')

for v in sheet['Visuals']:
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') != 'tbl-ps-projects':
        continue

    print('=== RowAlternateColorOptions ===')
    print(json.dumps(tbl['ChartConfiguration']['TableOptions'].get('RowAlternateColorOptions'), indent=2))

    print('\n=== ConditionalFormatting ===')
    print(json.dumps(tbl.get('ConditionalFormatting', {}), indent=2))

    print('\n=== GroupBy field IDs ===')
    for f in tbl['ChartConfiguration']['FieldWells']['TableAggregatedFieldWells']['GroupBy']:
        cdf = f.get('CategoricalDimensionField', {})
        print(f"  {cdf.get('FieldId')} → {cdf.get('Column', {}).get('ColumnName')}")
    break
