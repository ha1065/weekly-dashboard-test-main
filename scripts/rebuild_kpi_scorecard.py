#!/usr/bin/env python3
"""Rebuild KPI Scorecard sheet from scratch with correct filter scoping.

KPI tiles: filter to last 2 weeks (gets latest completed week via MAX)
Trend charts: filter to last 6 months, DateDimensionField MONTH granularity
Goal lines already added in previous script — preserve them.
"""
import boto3, time

PROFILE   = 'AWSAdministratorAccess-961341524729'
REGION    = 'us-east-1'
ACCOUNT   = '961341524729'
DASH_ID   = 'coo-operational-dashboard-prod'
SHEET_ID  = 'sheet-kpi-scorecard'
KPI_DS    = 'KPI Weekly Snapshots (prod)'

TILE_IDS  = ['kpi-tile-otd', 'kpi-tile-compliance', 'kpi-tile-util', 'kpi-tile-escalations']
TREND_IDS = ['trend-otd', 'trend-compliance', 'trend-util', 'trend-escalations']

TILE_CONFIG = [
    ('kpi-tile-otd',         'ps_on_time_pct',       'On-Time Delivery (PS)',  'target_ps_on_time_pct'),
    ('kpi-tile-compliance',  'time_compliance_pct',  'Timesheet Compliance',   'target_time_compliance_pct'),
    ('kpi-tile-util',        'billable_util_pct',    'Utilization',            'target_billable_util_pct'),
    ('kpi-tile-escalations', 'open_escalations',     'Open Escalations',       None),
]
TREND_CONFIG = [
    ('trend-otd',         'ps_on_time_pct',      'On-Time Delivery Trend',      90.0,  '90% Target'),
    ('trend-compliance',  'time_compliance_pct', 'Timesheet Compliance Trend',  95.0,  '95% Target'),
    ('trend-util',        'billable_util_pct',   'Utilization Trend',           75.0,  '75% Target'),
    ('trend-escalations', 'open_escalations',    'Open Escalations Trend',      None,  None),
]

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')
d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Definition']

# ── Remove scorecard sheet and its filter groups ───────────────────────────
SCORECARD_FG_IDS = {'fg-scorecard-6month', 'fg-scorecard-tiles'}
defn['Sheets']       = [s  for s  in defn['Sheets']       if s['SheetId'] != SHEET_ID]
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', []) if fg['FilterGroupId'] not in SCORECARD_FG_IDS]

# ── Remove any scorecard calculated fields ─────────────────────────────────
OUR_CF_NAMES = {
    'cur_ps_on_time_pct','pri_ps_on_time_pct','cur_time_compliance_pct','pri_time_compliance_pct',
    'cur_billable_util_pct','pri_billable_util_pct','cur_open_escalations','pri_open_escalations',
}
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
    if cf.get('Name') not in OUR_CF_NAMES
]

# ── Build KPI tile visuals ─────────────────────────────────────────────────
def make_tile(vid, col, title, target_col):
    fw = {
        'Values': [{'NumericalMeasureField': {
            'FieldId': f'{vid}-val',
            'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': col},
            'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
        }}],
        'TargetValues': [],
        'TrendGroups': []
    }
    if target_col:
        fw['TargetValues'] = [{'NumericalMeasureField': {
            'FieldId': f'{vid}-target',
            'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': target_col},
            'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
        }}]
    return {
        'KPIVisual': {
            'VisualId': vid,
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': title}},
            'Subtitle': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Latest completed week'}},
            'ChartConfiguration': {
                'FieldWells': fw,
                'KPIOptions': {
                    'Comparison': {'ComparisonMethod': 'DIFFERENCE'},
                    'ProgressBar': {'Visibility': 'HIDDEN'},
                    'SecondaryValue': {'Visibility': 'VISIBLE'},
                    'TrendArrows': {'Visibility': 'VISIBLE'},
                    'PrimaryValueDisplayType': 'ACTUAL'
                }
            }
        }
    }

# ── Build trend line visuals ───────────────────────────────────────────────
def make_trend(vid, col, title, target_val, target_label):
    ref_lines = []
    if target_val is not None and target_label:
        ref_lines.append({
            'Status': 'ENABLED',
            'DataConfiguration': {
                'StaticConfiguration': {'Value': target_val}
            },
            'StyleConfiguration': {'Pattern': 'DASHED', 'Color': '#D74018'},
            'LabelConfiguration': {'CustomLabelConfiguration': {'CustomLabel': target_label}}
        })
    cfg = {
        'FieldWells': {
            'LineChartAggregatedFieldWells': {
                'Category': [{'DateDimensionField': {
                    'FieldId': f'{vid}-month',
                    'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': 'week_start_date'},
                    'DateGranularity': 'WEEK'
                }}],
                'Values': [{'NumericalMeasureField': {
                    'FieldId': f'{vid}-val',
                    'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': col},
                    'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
                }}],
                'Colors': []
            }
        },
        'Type': 'LINE',
        'Legend': {'Visibility': 'HIDDEN'},
        'DataLabels': {'Visibility': 'HIDDEN'},
    }
    if ref_lines:
        cfg['ReferenceLines'] = ref_lines
    return {
        'LineChartVisual': {
            'VisualId': vid,
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': title}},
            'ChartConfiguration': cfg
        }
    }

# ── Build sheet ────────────────────────────────────────────────────────────
new_sheet = {
    'SheetId': SHEET_ID,
    'Name': 'Org KPI Scorecard',
    'Visuals': (
        [make_tile(*t) for t in TILE_CONFIG] +
        [make_trend(*t) for t in TREND_CONFIG]
    ),
    'Layouts': [{'Configuration': {'GridLayout': {'Elements': [
        {'ElementId': 'kpi-tile-otd',         'ElementType': 'VISUAL', 'ColumnIndex': 0,  'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': 'kpi-tile-compliance',  'ElementType': 'VISUAL', 'ColumnIndex': 9,  'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': 'kpi-tile-util',        'ElementType': 'VISUAL', 'ColumnIndex': 18, 'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': 'kpi-tile-escalations', 'ElementType': 'VISUAL', 'ColumnIndex': 27, 'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': 'trend-otd',            'ElementType': 'VISUAL', 'ColumnIndex': 0,  'ColumnSpan': 18, 'RowIndex': 4,  'RowSpan': 10},
        {'ElementId': 'trend-compliance',     'ElementType': 'VISUAL', 'ColumnIndex': 18, 'ColumnSpan': 18, 'RowIndex': 4,  'RowSpan': 10},
        {'ElementId': 'trend-util',           'ElementType': 'VISUAL', 'ColumnIndex': 0,  'ColumnSpan': 18, 'RowIndex': 14, 'RowSpan': 10},
        {'ElementId': 'trend-escalations',    'ElementType': 'VISUAL', 'ColumnIndex': 18, 'ColumnSpan': 18, 'RowIndex': 14, 'RowSpan': 10},
    ]}}}]
}
defn['Sheets'].append(new_sheet)

# ── Filter groups ──────────────────────────────────────────────────────────
# Tiles: last 2 weeks (MAX picks the latest completed week)
defn['FilterGroups'].append({
    'FilterGroupId': 'fg-scorecard-tiles',
    'Filters': [{'RelativeDatesFilter': {
        'FilterId': 'fg-scorecard-tiles-f',
        'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': 'week_start_date'},
        'AnchorDateConfiguration': {'AnchorOption': 'NOW'},
        'RelativeDateType': 'LAST',
        'RelativeDateValue': 2,
        'TimeGranularity': 'WEEK',
        'NullOption': 'NON_NULLS_ONLY'
    }}],
    'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
        {'SheetId': SHEET_ID, 'Scope': 'SELECTED_VISUALS', 'VisualIds': TILE_IDS}
    ]}},
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})

# Trends: last 13 weeks
defn['FilterGroups'].append({
    'FilterGroupId': 'fg-scorecard-6month',
    'Filters': [{'RelativeDatesFilter': {
        'FilterId': 'fg-scorecard-6month-f',
        'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': 'week_start_date'},
        'AnchorDateConfiguration': {'AnchorOption': 'NOW'},
        'RelativeDateType': 'LAST',
        'RelativeDateValue': 13,
        'TimeGranularity': 'WEEK',
        'NullOption': 'NON_NULLS_ONLY'
    }}],
    'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
        {'SheetId': SHEET_ID, 'Scope': 'SELECTED_VISUALS', 'VisualIds': TREND_IDS}
    ]}},
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})

print(f'Rebuilt scorecard sheet with {len(new_sheet["Visuals"])} visuals')

# ── Push and publish ───────────────────────────────────────────────────────
kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASH_ID, Name=name, Definition=defn,
    VersionDescription='Rebuild KPI Scorecard: clean tiles with 2-week filter, trends with 6-month filter + goal lines'
)
if theme_arn:
    kwargs['ThemeArn'] = theme_arn

resp    = qs.update_dashboard(**kwargs)
version = int(resp['VersionArn'].split('/')[-1])
print(f'Version {version} created. Polling...')

deadline = time.time() + 90
while time.time() < deadline:
    time.sleep(6)
    ver = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASH_ID, VersionNumber=version)
    status = ver.get('ResourceStatus', '')
    if 'SUCCESSFUL' in status or 'FAILED' in status:
        break

errors = ver.get('Errors', [])
if errors:
    for e in errors:
        print(f'  ❌ {e.get("Type")}: {e.get("Message")}')
    print('Not published.')
else:
    qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASH_ID, VersionNumber=version)
    print(f'✅ Published version {version}')
