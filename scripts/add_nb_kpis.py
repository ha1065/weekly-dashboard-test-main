#!/usr/bin/env python3
"""Add non-billable productive and non-productive KPI tiles to Time & Utilization sheet."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']
sheet5 = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-time-util')
visuals = sheet5['Visuals']
layout_els = sheet5['Layouts'][0]['Configuration']['GridLayout']['Elements']

def kpi_v(vid, title, ds, col, col_idx, row_idx, cs=9, rs=4):
    return {
        'KPIVisual': {
            'VisualId': vid,
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': title}},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{'NumericalMeasureField': {
                        'FieldId': f'{vid}-v',
                        'Column': {'DataSetIdentifier': ds, 'ColumnName': col},
                        'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'},
                    }}],
                    'TargetValues': [], 'TrendGroups': [],
                },
                'KPIOptions': {
                    'PrimaryValueDisplayType': 'ACTUAL',
                    'TrendArrows': {'Visibility': 'VISIBLE'},
                    'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE'},
                },
            },
            'ColumnHierarchies': [],
        }
    }, {'ElementId': vid, 'ElementType': 'VISUAL',
        'ColumnIndex': col_idx, 'RowIndex': row_idx, 'ColumnSpan': cs, 'RowSpan': rs}

# Current row 0 has 4 KPIs at col 0,9,18,27 (span 9 each)
# Shift existing KPIs to row 0 cols 0-17 (span 6 each) and add 2 new ones at cols 18-35
# Simpler: keep existing 4 at row 0, add 2 new ones at row 4 (above the tables)
# Actually: move tables down and add new KPIs at row 4

# Add 2 new KPI tiles at row 4, cols 0 and 18
v1, l1 = kpi_v('kpi-nb-productive', 'Non-Billable Productive Hours',
                'productive_util', 'nb_productive_hours', col_idx=0, row_idx=4, cs=18, rs=4)
v2, l2 = kpi_v('kpi-nb-non-productive', 'Non-Billable Non-Productive Hours',
                'productive_util', 'nb_non_productive_hours', col_idx=18, row_idx=4, cs=18, rs=4)

# Shift existing tables down by 4 rows
for el in layout_els:
    if el.get('RowIndex', 0) >= 4:
        el['RowIndex'] += 4

visuals.extend([v1, v2])
layout_els.extend([l1, l2])
print('Added kpi-nb-productive and kpi-nb-non-productive at row 4')

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
