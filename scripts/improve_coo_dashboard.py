#!/usr/bin/env python3
"""COO Dashboard improvements:
1. Add project_type parameter filter to PS Delivery sheet
2. Fix Utilization Detail trend to show history (remove week equality filter)
3. Add billable_pct + productive_util_pct to Utilization by Person table
4. Add goal lines (TargetValues) to 4 KPI scorecard tiles
"""
import boto3, time

PROFILE   = 'AWSAdministratorAccess-961341524729'
REGION    = 'us-east-1'
ACCOUNT   = '961341524729'
DASH_ID   = 'coo-operational-dashboard-prod'

PS_SHEET_NAME      = 'PS Delivery'
UTIL_SHEET_ID      = 'sheet-util-detail'
SCORECARD_SHEET_ID = 'sheet-kpi-scorecard'
TREND_VID          = 'visual-util-trend'
TABLE_VID          = 'visual-util-table'
UTIL_DS            = 'utilization_history'
KPI_DS             = 'KPI Weekly Snapshots (prod)'
PS_DS              = 'ps_project_status'

# KPI tile IDs and their target column names in kpi_weekly_snapshots
KPI_TARGETS = {
    'kpi-tile-otd':        ('ps_on_time_pct',      'target_ps_on_time_pct'),
    'kpi-tile-compliance': ('time_compliance_pct',  'target_time_compliance_pct'),
    'kpi-tile-util':       ('billable_util_pct',    'target_billable_util_pct'),
    # open_escalations has no target column — skip goal line for that tile
}

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Definition']

# ── 1. Add project_type parameter + filter to PS Delivery sheet ───────────
ps_sheet_idx = next((i for i, s in enumerate(defn['Sheets']) if s.get('Name') == PS_SHEET_NAME), None)

if ps_sheet_idx is not None:
    ps_sheet = defn['Sheets'][ps_sheet_idx]
    PARAM_NAME = 'ProjectType'
    FG_ID      = 'fg-ps-project-type'
    CTRL_ID    = 'ctrl-ps-project-type'

    # Add filter group scoped to PS Delivery sheet
    existing_fg_ids = {fg['FilterGroupId'] for fg in defn.get('FilterGroups', [])}
    if FG_ID not in existing_fg_ids:
        defn.setdefault('FilterGroups', []).append({
            'FilterGroupId': FG_ID,
            'Filters': [{
                'CategoryFilter': {
                    'FilterId': f'{FG_ID}-f',
                    'Column': {'DataSetIdentifier': PS_DS, 'ColumnName': 'type'},
                    'Configuration': {
                        'FilterListConfiguration': {
                            'MatchOperator': 'CONTAINS',
                            'SelectAllOptions': 'FILTER_ALL_VALUES'
                        }
                    }
                }
            }],
            'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
                {'SheetId': ps_sheet['SheetId'], 'Scope': 'ALL_VISUALS'}
            ]}},
            'Status': 'ENABLED',
            'CrossDataset': 'SINGLE_DATASET'
        })
        print(f'Added filter group: {FG_ID}')

    # Add dropdown control to PS Delivery sheet
    existing_ctrl_ids = {list(c.values())[0].get('FilterControlId', '') for c in ps_sheet.get('FilterControls', [])}
    if CTRL_ID not in existing_ctrl_ids:
        ps_sheet.setdefault('FilterControls', []).insert(0, {
            'Dropdown': {
                'FilterControlId': CTRL_ID,
                'Title': 'Project Type',
                'SourceFilterId': f'{FG_ID}-f',
                'SelectableValues': {},
                'Type': 'SINGLE_SELECT'
            }
        })
        print('Added Project Type dropdown to PS Delivery sheet')

# ── 2. Fix Utilization Detail trend — remove week equality filter from trend visual ──
# The trend visual should show history; the week filter should scope to table only.
# Move fg-ud-week to scope only the TABLE visual, not ALL_VISUALS.
for fg in defn.get('FilterGroups', []):
    if fg['FilterGroupId'] == 'fg-ud-week':
        fg['ScopeConfiguration'] = {
            'SelectedSheets': {'SheetVisualScopingConfigurations': [
                {'SheetId': UTIL_SHEET_ID, 'Scope': 'SELECTED_VISUALS', 'VisualIds': [TABLE_VID]}
            ]}
        }
        print('Fixed fg-ud-week: scoped to table only (trend now shows full history)')
        break

# ── 3. Add billable_pct + productive_util_pct to Utilization by Person table ──
# ── 3. Add billable % + productive util % calculated fields + table columns ──
# Add calculated fields for utilization percentages (not in raw dataset)
UTIL_CF_NAMES = {'cf_billable_pct', 'cf_prod_util_pct'}
existing_cf_names = {cf.get('Name') for cf in defn.get('CalculatedFields', [])}
for cf_name, expr in [
    ('cf_billable_pct',  'sumOver(billable_hours, [], PRE_AGG) / nullIf(sumOver(available_hours, [], PRE_AGG), 0) * 100'),
    ('cf_prod_util_pct', 'sumOver(billable_hours + nb_productive_hours, [], PRE_AGG) / nullIf(sumOver(available_hours, [], PRE_AGG), 0) * 100'),
]:
    if cf_name not in existing_cf_names:
        defn.setdefault('CalculatedFields', []).append({
            'DataSetIdentifier': UTIL_DS,
            'Name': cf_name,
            'Expression': expr
        })

util_sheet = next((s for s in defn['Sheets'] if s.get('SheetId') == UTIL_SHEET_ID), None)
if util_sheet:
    for visual in util_sheet.get('Visuals', []):
        tv = visual.get('TableVisual', {})
        if tv.get('VisualId') == TABLE_VID:
            values = tv['ChartConfiguration']['FieldWells']['TableAggregatedFieldWells']['Values']
            existing_fids = {list(f.values())[0].get('FieldId', '') for f in values}
            added = 0
            for fid, col in [('tbl-billable-pct', 'cf_billable_pct'), ('tbl-prod-util-pct', 'cf_prod_util_pct')]:
                if fid not in existing_fids:
                    values.append({'NumericalMeasureField': {
                        'FieldId': fid,
                        'Column': {'DataSetIdentifier': UTIL_DS, 'ColumnName': col},
                        'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                    }})
                    added += 1
            print(f'Added {added} utilization % columns to Utilization by Person table')
            print(f'Added {added} columns to Utilization by Person table')

# ── 4. Add goal lines to KPI scorecard tiles ──────────────────────────────
scorecard_sheet = next((s for s in defn['Sheets'] if s.get('SheetId') == SCORECARD_SHEET_ID), None)
if scorecard_sheet:
    for visual in scorecard_sheet.get('Visuals', []):
        kv = visual.get('KPIVisual', {})
        vid = kv.get('VisualId', '')
        if vid in KPI_TARGETS:
            _, target_col = KPI_TARGETS[vid]
            fw = kv['ChartConfiguration']['FieldWells']
            # Add target value if not already present
            if not fw.get('TargetValues'):
                fw['TargetValues'] = [{
                    'NumericalMeasureField': {
                        'FieldId': f'{vid}-goal',
                        'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': target_col},
                        'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
                    }
                }]
                print(f'Added goal line to {vid} using {target_col}')

# ── Strip CalculatedFieldId from all CFs ──────────────────────────────────
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
]

# ── Push and publish ───────────────────────────────────────────────────────
kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASH_ID, Name=name, Definition=defn,
    VersionDescription='PS project type filter, util trend fix, util table columns, KPI goal lines'
)
if theme_arn:
    kwargs['ThemeArn'] = theme_arn

resp    = qs.update_dashboard(**kwargs)
version = int(resp['VersionArn'].split('/')[-1])
print(f'\nVersion {version} created. Polling...')

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
