#!/usr/bin/env python3
"""Update Utilization Detail sheet:
1. Add reporting week date filter
2. Add billable_hours, available_hours, nb_productive_hours to table
3. Preserve theme
"""
import boto3, time

PROFILE      = 'AWSAdministratorAccess-961341524729'
REGION       = 'us-east-1'
ACCOUNT      = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
UTIL_ID      = 'utilization_history'
SHEET_ID     = 'sheet-util-detail'
TABLE_ID     = 'visual-util-table'
WEEK_FG      = 'fg-ud-week'
WEEK_CTRL    = 'ctrl-ud-week'

qs   = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')
d    = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']
name = d['Name']
theme = d['Version'].get('ThemeArn')
defn = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Definition']

sheet_idx = next(i for i, s in enumerate(defn['Sheets']) if s['SheetId'] == SHEET_ID)
sheet     = defn['Sheets'][sheet_idx]

# ── 1. Add week filter group ───────────────────────────────────────────────
if not any(fg['FilterGroupId'] == WEEK_FG for fg in defn.get('FilterGroups', [])):
    defn.setdefault('FilterGroups', []).append({
        'FilterGroupId': WEEK_FG,
        'Filters': [{'TimeEqualityFilter': {
            'FilterId': f'{WEEK_FG}-f',
            'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': 'week_start'},
            'TimeGranularity': 'DAY',
            'RollingDate': {'Expression': 'truncDate("WK", now())'}
        }}],
        'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
            {'SheetId': SHEET_ID, 'Scope': 'ALL_VISUALS'}
        ]}},
        'Status': 'ENABLED',
        'CrossDataset': 'SINGLE_DATASET'
    })
    print('Added week filter group')

# ── 2. Add week date picker control ───────────────────────────────────────
existing_ctrl_ids = {list(c.values())[0].get('FilterControlId','') for c in sheet.get('FilterControls',[])}
if WEEK_CTRL not in existing_ctrl_ids:
    sheet.setdefault('FilterControls', []).insert(0, {
        'DateTimePicker': {
            'FilterControlId': WEEK_CTRL,
            'Title': 'Reporting Week',
            'SourceFilterId': f'{WEEK_FG}-f',
            'Type': 'SINGLE_VALUED'
        }
    })
    print('Added week picker control')

# ── 3. Add columns to table ────────────────────────────────────────────────
for visual in sheet.get('Visuals', []):
    tv = visual.get('TableVisual', {})
    if tv.get('VisualId') != TABLE_ID:
        continue
    values = tv['ChartConfiguration']['FieldWells']['TableAggregatedFieldWells']['Values']
    existing_ids = {list(f.values())[0].get('FieldId','') for f in values}
    added = 0
    for fid, col in [('tbl-avail','available_hours'), ('tbl-total-logged','total_logged_hours')]:
        if fid not in existing_ids:
            values.append({'NumericalMeasureField': {
                'FieldId': fid,
                'Column': {'DataSetIdentifier': UTIL_ID, 'ColumnName': col},
                'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}
            }})
            added += 1
    print(f'Added {added} columns to table')

# ── 4. Push with theme ─────────────────────────────────────────────────────
kwargs = dict(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, Name=name,
              Definition=defn, VersionDescription='Add week filter + hours columns to Utilization Detail')
if theme:
    kwargs['ThemeArn'] = theme

resp    = qs.update_dashboard(**kwargs)
version = int(resp['VersionArn'].split('/')[-1])
print(f'Version {version} created. Waiting 5s...')
time.sleep(5)
qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
print(f'✅ Published version {version}')
