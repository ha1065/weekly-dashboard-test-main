#!/usr/bin/env python3
"""Add a new 'Utilization Detail' sheet to the COO Operational Dashboard.

Sheet layout:
- POD filter (multi-select dropdown)
- Person filter (multi-select dropdown)
- Stacked line chart: billable_hours, nb_productive_hours, nb_non_productive_hours,
  non_logged_hours by week_start — both filters applied
- Table: per-person weekly utilization breakdown — both filters applied
"""

import boto3, json, time, uuid

PROFILE      = 'AWSAdministratorAccess-961341524729'
REGION       = 'us-east-1'
ACCOUNT      = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
DATASET_ID   = 'utilization-history'   # registered yesterday, has pod_assignment + user_name

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── 1. Get current dashboard definition ───────────────────────────────────
resp = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)
defn = resp['Definition']
dashboard_name = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']['Name']

# ── 2. Verify utilization-history dataset is registered in the dashboard ──
existing_ds_ids = {d['Identifier'] for d in defn.get('DataSetIdentifierDeclarations', [])}
print(f'Existing datasets: {existing_ds_ids}')

UTIL_IDENTIFIER = 'utilization_history'

# Get dataset ARN
ds_info = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId=DATASET_ID)['DataSet']
ds_arn  = ds_info['Arn']
cols    = [c['Name'] for c in ds_info.get('OutputColumns', [])]
print(f'utilization-history columns: {[c for c in cols if any(k in c for k in ["pod","user","billable","nb_","non_","week"])]}')

if UTIL_IDENTIFIER not in existing_ds_ids:
    defn['DataSetIdentifierDeclarations'].append({
        'Identifier': UTIL_IDENTIFIER,
        'DataSetArn': ds_arn
    })
    print(f'Registered dataset: {UTIL_IDENTIFIER}')

# ── 3. Define IDs ──────────────────────────────────────────────────────────
SHEET_ID        = 'sheet-util-detail'
TREND_ID        = 'visual-util-trend'
TABLE_ID        = 'visual-util-table'
POD_FILTER_ID   = 'fg-ud-pod'
USER_FILTER_ID  = 'fg-ud-person'
POD_CTRL_ID     = 'ctrl-ud-pod'
USER_CTRL_ID    = 'ctrl-ud-person'

# ── 4. Remove sheet if already exists (idempotent) ─────────────────────────
defn['Sheets'] = [s for s in defn['Sheets'] if s['SheetId'] != SHEET_ID]
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', [])
                        if fg['FilterGroupId'] not in (POD_FILTER_ID, USER_FILTER_ID)]

# ── 5. Build the sheet ─────────────────────────────────────────────────────
scope = {
    'SelectedSheets': {
        'SheetVisualScopingConfigurations': [{
            'SheetId': SHEET_ID,
            'Scope': 'ALL_VISUALS'
        }]
    }
}

# Trend line chart — 4 lines (one per utilization category) over week_start
trend_visual = {
    'LineChartVisual': {
        'VisualId': TREND_ID,
        'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Utilization Trend by Week'}},
        'ChartConfiguration': {
            'FieldWells': {
                'LineChartAggregatedFieldWells': {
                    'Category': [{
                        'DateDimensionField': {
                            'FieldId': 'trend-week',
                            'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': 'week_start'},
                            'DateGranularity': 'WEEK'
                        }
                    }],
                    'Values': [
                        {'NumericalMeasureField': {'FieldId': 'trend-billable',     'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': 'billable_hours'},          'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
                        {'NumericalMeasureField': {'FieldId': 'trend-nb-prod',      'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': 'nb_productive_hours'},     'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
                        {'NumericalMeasureField': {'FieldId': 'trend-nb-nonprod',   'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': 'nb_non_productive_hours'}, 'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
                        {'NumericalMeasureField': {'FieldId': 'trend-non-logged',   'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': 'non_logged_hours'},        'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
                    ]
                }
            },
            'Type': 'LINE',
            'Legend': {'Visibility': 'VISIBLE'},
        }
    }
}

# Detect actual column names for nb categories
nb_nonprod_col = 'nb_non_productive_hours' if 'nb_non_productive_hours' in cols else 'nb_nonproductive_hours'
non_logged_col = 'non_logged_hours' if 'non_logged_hours' in cols else 'non_logged_pct'

# Fix column names in trend visual based on actual schema
trend_visual['LineChartVisual']['ChartConfiguration']['FieldWells']['LineChartAggregatedFieldWells']['Values'][2]['NumericalMeasureField']['Column']['ColumnName'] = nb_nonprod_col

if non_logged_col in cols:
    trend_visual['LineChartVisual']['ChartConfiguration']['FieldWells']['LineChartAggregatedFieldWells']['Values'][3]['NumericalMeasureField']['Column']['ColumnName'] = non_logged_col
else:
    # Remove non-logged if column doesn't exist
    trend_visual['LineChartVisual']['ChartConfiguration']['FieldWells']['LineChartAggregatedFieldWells']['Values'] = \
        trend_visual['LineChartVisual']['ChartConfiguration']['FieldWells']['LineChartAggregatedFieldWells']['Values'][:3]

# Table visual — per person per week
user_col = 'employee_name' if 'employee_name' in cols else next((c for c in cols if 'user' in c.lower() or 'employee' in c.lower()), None)
if not user_col:
    print(f'WARNING: no user column found, table will group by POD only')
pod_col  = 'pod_assignment' if 'pod_assignment' in cols else next((c for c in cols if 'pod' in c.lower()), None)

table_cols = [
    ('tbl-week',     'week_start',         'DIMENSION', 'DATE'),
]
if user_col:
    table_cols.append(('tbl-user', user_col, 'DIMENSION', 'STRING'))
if pod_col:
    table_cols.append(('tbl-pod', pod_col, 'DIMENSION', 'STRING'))
table_cols += [
    ('tbl-billable',   'billable_hours',       'MEASURE', 'DECIMAL'),
    ('tbl-nb-prod',    'nb_productive_hours',  'MEASURE', 'DECIMAL'),
    ('tbl-nb-nonprod', nb_nonprod_col,         'MEASURE', 'DECIMAL'),
]
if non_logged_col in cols:
    table_cols.append(('tbl-nonlogged', non_logged_col, 'MEASURE', 'DECIMAL'))
table_cols.append(('tbl-util-pct', 'billable_pct' if 'billable_pct' in cols else 'billable_hours', 'MEASURE', 'DECIMAL'))

def make_table_field(fid, col, ftype, dtype):
    if ftype == 'DIMENSION':
        if dtype == 'DATE':
            return {'DateDimensionField': {'FieldId': fid, 'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': col}, 'DateGranularity': 'WEEK'}}
        return {'CategoricalDimensionField': {'FieldId': fid, 'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': col}}}
    return {'NumericalMeasureField': {'FieldId': fid, 'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': col}, 'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}}

table_visual = {
    'TableVisual': {
        'VisualId': TABLE_ID,
        'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Utilization by Person'}},
        'ChartConfiguration': {
            'FieldWells': {
                'TableAggregatedFieldWells': {
                    'GroupBy': [make_table_field(fid, col, ftype, dtype)
                                for fid, col, ftype, dtype in table_cols if ftype == 'DIMENSION'],
                    'Values':  [make_table_field(fid, col, ftype, dtype)
                                for fid, col, ftype, dtype in table_cols if ftype == 'MEASURE'],
                }
            },
            'SortConfiguration': {
                'RowSort': [{'FieldSort': {'FieldId': 'tbl-week', 'Direction': 'DESC'}}]
            }
        }
    }
}

# Sheet definition
new_sheet = {
    'SheetId': SHEET_ID,
    'Name': 'Utilization Detail',
    'FilterControls': [
        {'Dropdown': {'FilterControlId': POD_CTRL_ID,  'Title': 'POD',    'SourceFilterId': f'{POD_FILTER_ID}-f',  'SelectableValues': {}, 'Type': 'MULTI_SELECT'}},
        {'Dropdown': {'FilterControlId': USER_CTRL_ID, 'Title': 'Person', 'SourceFilterId': f'{USER_FILTER_ID}-f', 'SelectableValues': {}, 'Type': 'MULTI_SELECT'}},
    ],
    'Visuals': [trend_visual, table_visual],
    'Layouts': [{
        'Configuration': {
            'GridLayout': {
                'Elements': [
                    {'ElementId': TREND_ID, 'ElementType': 'VISUAL', 'ColumnIndex': 0, 'ColumnSpan': 36, 'RowIndex': 2,  'RowSpan': 12},
                    {'ElementId': TABLE_ID, 'ElementType': 'VISUAL', 'ColumnIndex': 0, 'ColumnSpan': 36, 'RowIndex': 14, 'RowSpan': 14},
                ]
            }
        }
    }]
}

defn['Sheets'].append(new_sheet)

# ── 6. Add filter groups ───────────────────────────────────────────────────
if pod_col:
    defn['FilterGroups'].append({
        'FilterGroupId': POD_FILTER_ID,
        'Filters': [{'CategoryFilter': {
            'FilterId': f'{POD_FILTER_ID}-f',
            'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': pod_col},
            'Configuration': {'FilterListConfiguration': {'MatchOperator': 'CONTAINS', 'SelectAllOptions': 'FILTER_ALL_VALUES'}}
        }}],
        'ScopeConfiguration': scope,
        'Status': 'ENABLED',
        'CrossDataset': 'SINGLE_DATASET'
    })

defn['FilterGroups'].append({
    'FilterGroupId': USER_FILTER_ID,
    'Filters': [{'CategoryFilter': {
        'FilterId': f'{USER_FILTER_ID}-f',
        'Column': {'DataSetIdentifier': UTIL_IDENTIFIER, 'ColumnName': user_col or pod_col},
        'Configuration': {'FilterListConfiguration': {'MatchOperator': 'CONTAINS', 'SelectAllOptions': 'FILTER_ALL_VALUES'}}
    }}],
    'ScopeConfiguration': scope,
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})

# ── 7. Push update ─────────────────────────────────────────────────────────
# Get the current theme ARN so we don't drop it
current = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']
theme_arn = current.get('Version', {}).get('ThemeArn')
print(f'Preserving theme: {theme_arn}')

print('Pushing dashboard update...')
update_kwargs = dict(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=dashboard_name,
    Definition=defn,
    VersionDescription='Add Utilization Detail sheet with POD and Person filters'
)
if theme_arn:
    update_kwargs['ThemeArn'] = theme_arn

resp = qs.update_dashboard(**update_kwargs)
version = int(resp['VersionArn'].split('/')[-1])
print(f'Version {version} created. Waiting 5s...')
time.sleep(5)

# Check version status
ver = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
status = ver.get('ResourceStatus', '')
print(f'Version status: {status}')
if 'SUCCESSFUL' in status or 'CREATION' in status:
    qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
    print(f'✅ Published version {version}. Refresh the COO dashboard to see the new "Utilization Detail" sheet.')
else:
    errors = ver.get('Errors', [])
    for e in errors:
        print(f'  ❌ {e.get("Type")}: {e.get("Message")}')
    print(f'Version not published due to errors above.')
