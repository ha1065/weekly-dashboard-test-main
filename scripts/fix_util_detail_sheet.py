#!/usr/bin/env python3
"""Fix Utilization Detail sheet: rebuild with correct column names from vw_productive_utilization.

Root cause: add_util_detail_sheet.py referenced 'user_name' which doesn't exist.
Actual column is 'employee_name'. Also confirms correct nb column name.

vw_productive_utilization actual columns (from create_views.sql):
  employee_name, pod_assignment, cloudelligent_title, practice_alignment,
  location, employment_designation, week_start, available_hours,
  billable_hours, nb_productive_hours, nb_non_productive_hours, non_logged_hours
  (+ billable_pct, productive_util_pct etc. from outer SELECT)
"""
import boto3, time

PROFILE      = 'AWSAdministratorAccess-961341524729'
REGION       = 'us-east-1'
ACCOUNT      = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
DATASET_ID   = 'utilization-history'
UTIL_ID      = 'utilization_history'

SHEET_ID   = 'sheet-util-detail'
TREND_ID   = 'visual-util-trend'
TABLE_ID   = 'visual-util-table'
POD_FG     = 'fg-ud-pod'
USER_FG    = 'fg-ud-person'
WEEK_FG    = 'fg-ud-week'
POD_CTRL   = 'ctrl-ud-pod'
USER_CTRL  = 'ctrl-ud-person'
WEEK_CTRL  = 'ctrl-ud-week'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── 1. Confirm actual columns in the SPICE dataset ────────────────────────
ds   = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId=DATASET_ID)['DataSet']
cols = [c['Name'] for c in ds.get('OutputColumns', [])]
print(f'SPICE columns: {cols}')

# Resolve column names defensively
user_col     = 'employee_name' if 'employee_name' in cols else next((c for c in cols if 'name' in c.lower()), None)
pod_col      = 'pod_assignment' if 'pod_assignment' in cols else next((c for c in cols if 'pod' in c.lower()), None)
week_col     = 'week_start' if 'week_start' in cols else 'week_start_date'
nb_prod_col  = 'nb_productive_hours'
nb_nprod_col = 'nb_non_productive_hours' if 'nb_non_productive_hours' in cols else 'nb_nonproductive_hours'
nonlog_col   = 'non_logged_hours' if 'non_logged_hours' in cols else None

print(f'Using: user={user_col}, pod={pod_col}, week={week_col}, nb_nonprod={nb_nprod_col}, non_logged={nonlog_col}')

# ── 2. Get dashboard definition ───────────────────────────────────────────
d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Definition']

# Ensure dataset is registered
existing_ds = {x['Identifier'] for x in defn.get('DataSetIdentifierDeclarations', [])}
if UTIL_ID not in existing_ds:
    ds_arn = ds['Arn']
    defn['DataSetIdentifierDeclarations'].append({'Identifier': UTIL_ID, 'DataSetArn': ds_arn})
    print(f'Registered dataset: {UTIL_ID}')

# ── 3. Remove existing sheet and filter groups (idempotent) ───────────────
defn['Sheets']       = [s  for s  in defn['Sheets']       if s['SheetId']       != SHEET_ID]
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', [])
                        if fg['FilterGroupId'] not in (POD_FG, USER_FG, WEEK_FG)]

# ── 4. Build visuals ───────────────────────────────────────────────────────
scope = {'SelectedSheets': {'SheetVisualScopingConfigurations': [
    {'SheetId': SHEET_ID, 'Scope': 'ALL_VISUALS'}
]}}

# Trend line chart: stacked lines per utilization category over weeks
trend_values = [
    {'NumericalMeasureField': {'FieldId': 'trend-billable',  'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': 'billable_hours'},     'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
    {'NumericalMeasureField': {'FieldId': 'trend-nb-prod',   'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': nb_prod_col},           'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
    {'NumericalMeasureField': {'FieldId': 'trend-nb-nprod',  'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': nb_nprod_col},          'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
]
if nonlog_col:
    trend_values.append(
        {'NumericalMeasureField': {'FieldId': 'trend-nonlog', 'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': nonlog_col}, 'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}}
    )

trend_visual = {
    'LineChartVisual': {
        'VisualId': TREND_ID,
        'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Utilization Trend by Week'}},
        'ChartConfiguration': {
            'FieldWells': {
                'LineChartAggregatedFieldWells': {
                    'Category': [{'DateDimensionField': {
                        'FieldId': 'trend-week',
                        'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': week_col},
                        'DateGranularity': 'WEEK'
                    }}],
                    'Values': trend_values,
                    'Colors': []
                }
            },
            'Type': 'LINE',
            'Legend': {'Visibility': 'VISIBLE'},
        }
    }
}

# Table: per-person per-week breakdown
group_by = [
    {'DateDimensionField': {'FieldId': 'tbl-week', 'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': week_col}, 'DateGranularity': 'WEEK'}},
]
if user_col:
    group_by.append({'CategoricalDimensionField': {'FieldId': 'tbl-user', 'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': user_col}}})
if pod_col:
    group_by.append({'CategoricalDimensionField': {'FieldId': 'tbl-pod',  'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': pod_col}}})

table_values = [
    {'NumericalMeasureField': {'FieldId': 'tbl-avail',    'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': 'available_hours'},  'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
    {'NumericalMeasureField': {'FieldId': 'tbl-billable', 'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': 'billable_hours'},   'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
    {'NumericalMeasureField': {'FieldId': 'tbl-nb-prod',  'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': nb_prod_col},        'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
    {'NumericalMeasureField': {'FieldId': 'tbl-nb-nprod', 'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': nb_nprod_col},       'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
]
if nonlog_col:
    table_values.append(
        {'NumericalMeasureField': {'FieldId': 'tbl-nonlog', 'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': nonlog_col}, 'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}}
    )

table_visual = {
    'TableVisual': {
        'VisualId': TABLE_ID,
        'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Utilization by Person'}},
        'ChartConfiguration': {
            'FieldWells': {
                'TableAggregatedFieldWells': {'GroupBy': group_by, 'Values': table_values}
            },
            'SortConfiguration': {
                'RowSort': [{'FieldSort': {'FieldId': 'tbl-week', 'Direction': 'DESC'}}]
            }
        }
    }
}

# ── 5. Build sheet ─────────────────────────────────────────────────────────
filter_controls = []
if pod_col:
    filter_controls.append({'Dropdown': {'FilterControlId': POD_CTRL,  'Title': 'POD',    'SourceFilterId': f'{POD_FG}-f',  'SelectableValues': {}, 'Type': 'MULTI_SELECT'}})
if user_col:
    filter_controls.append({'Dropdown': {'FilterControlId': USER_CTRL, 'Title': 'Person', 'SourceFilterId': f'{USER_FG}-f', 'SelectableValues': {}, 'Type': 'MULTI_SELECT'}})
filter_controls.append({'DateTimePicker': {'FilterControlId': WEEK_CTRL, 'Title': 'Reporting Week', 'SourceFilterId': f'{WEEK_FG}-f', 'Type': 'SINGLE_VALUED'}})

new_sheet = {
    'SheetId': SHEET_ID,
    'Name': 'Utilization Detail',
    'FilterControls': filter_controls,
    'Visuals': [trend_visual, table_visual],
    'Layouts': [{'Configuration': {'GridLayout': {'Elements': [
        {'ElementId': TREND_ID, 'ElementType': 'VISUAL', 'ColumnIndex': 0, 'ColumnSpan': 36, 'RowIndex': 2,  'RowSpan': 12},
        {'ElementId': TABLE_ID, 'ElementType': 'VISUAL', 'ColumnIndex': 0, 'ColumnSpan': 36, 'RowIndex': 14, 'RowSpan': 14},
    ]}}}]
}
defn['Sheets'].append(new_sheet)

# ── 6. Add filter groups ───────────────────────────────────────────────────
if pod_col:
    defn['FilterGroups'].append({
        'FilterGroupId': POD_FG,
        'Filters': [{'CategoryFilter': {
            'FilterId': f'{POD_FG}-f',
            'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': pod_col},
            'Configuration': {'FilterListConfiguration': {'MatchOperator': 'CONTAINS', 'SelectAllOptions': 'FILTER_ALL_VALUES'}}
        }}],
        'ScopeConfiguration': scope, 'Status': 'ENABLED', 'CrossDataset': 'SINGLE_DATASET'
    })

if user_col:
    defn['FilterGroups'].append({
        'FilterGroupId': USER_FG,
        'Filters': [{'CategoryFilter': {
            'FilterId': f'{USER_FG}-f',
            'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': user_col},
            'Configuration': {'FilterListConfiguration': {'MatchOperator': 'CONTAINS', 'SelectAllOptions': 'FILTER_ALL_VALUES'}}
        }}],
        'ScopeConfiguration': scope, 'Status': 'ENABLED', 'CrossDataset': 'SINGLE_DATASET'
    })

defn['FilterGroups'].append({
    'FilterGroupId': WEEK_FG,
    'Filters': [{'TimeEqualityFilter': {
        'FilterId': f'{WEEK_FG}-f',
        'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': week_col},
        'TimeGranularity': 'DAY',
        'RollingDate': {'Expression': 'truncDate("WK", now())'}
    }}],
    'ScopeConfiguration': scope, 'Status': 'ENABLED', 'CrossDataset': 'SINGLE_DATASET'
})

# ── 7. Push and publish ────────────────────────────────────────────────────
kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, Name=name,
    Definition=defn,
    VersionDescription='Fix Utilization Detail sheet: correct column names (employee_name, week_start)'
)
if theme_arn:
    kwargs['ThemeArn'] = theme_arn

resp    = qs.update_dashboard(**kwargs)
version = int(resp['VersionArn'].split('/')[-1])
print(f'Version {version} created. Waiting...')
time.sleep(8)

ver_resp = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
errors   = ver_resp.get('Errors', [])
if errors:
    for e in errors:
        print(f'  ❌ {e.get("Type")}: {e.get("Message")}')
    print('Not published — check errors above.')
else:
    qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
    print(f'✅ Published version {version} — Utilization Detail sheet rebuilt with correct columns.')
