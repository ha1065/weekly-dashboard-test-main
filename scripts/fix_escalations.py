#!/usr/bin/env python3
"""Update Escalations sheet: add phase bar chart, fix filter to use Done."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

# 1. Fix the open escalations filter: exclude 'Done' (not 'Resolved')
for fg in defn['FilterGroups']:
    if fg['FilterGroupId'] == 'fg-esc-open':
        flc = fg['Filters'][0]['CategoryFilter']['Configuration']['FilterListConfiguration']
        flc['CategoryValues'] = ['Done']
        print('Fixed fg-esc-open: now excludes Done (was Resolved)')
        break

# 2. Add phase bar chart to Escalations sheet
sheet4 = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-escalations')
visuals = sheet4['Visuals']
layout_els = sheet4['Layouts'][0]['Configuration']['GridLayout']['Elements']

# Add bar chart: escalation_state (phase) by count — placed at row 4, col 0, span 18x12
phase_bar_vid = 'bar-esc-phase'
if not any(list(v.keys())[0] == 'BarChartVisual' and v.get('BarChartVisual',{}).get('VisualId') == phase_bar_vid for v in visuals):
    phase_bar = {
        'BarChartVisual': {
            'VisualId': phase_bar_vid,
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Escalations by Phase'}},
            'ChartConfiguration': {
                'FieldWells': {'BarChartAggregatedFieldWells': {
                    'Category': [{'CategoricalDimensionField': {
                        'FieldId': 'esc-phase-cat',
                        'Column': {'DataSetIdentifier': 'escalations', 'ColumnName': 'escalation_state'},
                    }}],
                    'Values': [{'NumericalMeasureField': {
                        'FieldId': 'esc-phase-val',
                        'Column': {'DataSetIdentifier': 'escalations', 'ColumnName': 'days_open'},
                        'AggregationFunction': {'SimpleNumericalAggregation': 'DISTINCT_COUNT'},
                    }}],
                    'Colors': [],
                }},
                'Orientation': 'HORIZONTAL',
                'Legend': {'Visibility': 'HIDDEN'},
                'DataLabels': {'Visibility': 'VISIBLE', 'Overlap': 'DISABLE_OVERLAP'},
                'VisualPalette': {
                    'ColorMap': [
                        {'Element': {'FieldId': 'esc-phase-cat', 'FieldValue': 'New'},         'Color': '#D74018'},
                        {'Element': {'FieldId': 'esc-phase-cat', 'FieldValue': 'In Progress'}, 'Color': '#FF9B00'},
                        {'Element': {'FieldId': 'esc-phase-cat', 'FieldValue': 'Watching'},    'Color': '#0089DD'},
                        {'Element': {'FieldId': 'esc-phase-cat', 'FieldValue': 'Done'},        'Color': '#33A94F'},
                    ]
                },
                'SortConfiguration': {'CategoryItemsLimit': {'OtherCategories': 'INCLUDE'}},
            },
        }
    }
    visuals.append(phase_bar)
    print(f'Added phase bar chart: {phase_bar_vid}')

# 3. Rearrange layout: 3 bar charts each 12 cols wide in row 4
for el in layout_els:
    if el['ElementId'] == 'bar-esc-cust':
        el['ColumnIndex'], el['ColumnSpan'] = 0, 12
    elif el['ElementId'] == 'bar-esc-asgn':
        el['ColumnIndex'], el['ColumnSpan'] = 12, 12
# Remove any prior bar-esc-phase layout entry, then add correct one
layout_els[:] = [el for el in layout_els if el['ElementId'] != 'bar-esc-phase']
layout_els.append({
    'ElementId': 'bar-esc-phase', 'ElementType': 'VISUAL',
    'ColumnIndex': 24, 'RowIndex': 4, 'ColumnSpan': 12, 'RowSpan': 12,
})

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
