#!/usr/bin/env python3
"""Fix KPI Scorecard tiles: replace cur_*/pri_* calculated fields with direct MAX/MIN
aggregation on raw columns. MAX over 26-week window = latest week's value.
Prior quarter comparison via dateDiff calculated field is unreliable — remove TargetValues
and use QuickSight's built-in comparison (PERCENT_DIFFERENCE or DIFFERENCE vs prior period).
"""
import boto3, time, json

PROFILE   = 'AWSAdministratorAccess-961341524729'
REGION    = 'us-east-1'
ACCOUNT   = '961341524729'
DASH_ID   = 'coo-operational-dashboard-prod'
SHEET_ID  = 'sheet-kpi-scorecard'
KPI_DS    = 'KPI Weekly Snapshots (prod)'

TILE_CONFIG = [
    ('kpi-tile-otd',   'ps_on_time_pct',      'On-Time Delivery (PS)'),
    ('kpi-tile-compliance', 'time_compliance_pct', 'Timesheet Compliance'),
    ('kpi-tile-util',  'billable_util_pct',    'Utilization'),
    ('kpi-tile-escalations', 'open_escalations', 'Open Escalations'),
]

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Definition']

# ── 1. Remove all cur_*/pri_* calculated fields ────────────────────────────
OUR_CF_NAMES = {
    'cur_ps_on_time_pct', 'pri_ps_on_time_pct',
    'cur_time_compliance_pct', 'pri_time_compliance_pct',
    'cur_billable_util_pct', 'pri_billable_util_pct',
    'cur_open_escalations', 'pri_open_escalations',
    'cf_billable_pct', 'cf_prod_util_pct',
}
before = len(defn.get('CalculatedFields', []))
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
    if cf.get('Name') not in OUR_CF_NAMES
]
print(f'Removed {before - len(defn["CalculatedFields"])} calculated fields')

# ── 2. Also remove cf_billable_pct / cf_prod_util_pct from util table visual ──
DEAD_COLS = {'cf_billable_pct', 'cf_prod_util_pct'}
for sheet in defn['Sheets']:
    for visual in sheet.get('Visuals', []):
        tv = visual.get('TableVisual', {})
        fw = tv.get('ChartConfiguration', {}).get('FieldWells', {}).get('TableAggregatedFieldWells', {})
        if 'Values' in fw:
            before_count = len(fw['Values'])
            fw['Values'] = [
                f for f in fw['Values']
                if list(f.values())[0].get('Column', {}).get('ColumnName') not in DEAD_COLS
            ]
            removed = before_count - len(fw['Values'])
            if removed:
                print(f'Removed {removed} dead column references from {tv.get("VisualId","?")} table')

# ── 3. Rebuild KPI tile visuals
scorecard_sheet = next((s for s in defn['Sheets'] if s.get('SheetId') == SHEET_ID), None)
if scorecard_sheet:
    for visual in scorecard_sheet.get('Visuals', []):
        kv = visual.get('KPIVisual', {})
        vid = kv.get('VisualId', '')
        tile = next((t for t in TILE_CONFIG if t[0] == vid), None)
        if not tile:
            continue
        _, col, title = tile
        # Rebuild field wells: primary = MAX of raw column, no target (clean display)
        kv['ChartConfiguration']['FieldWells'] = {
            'Values': [{'NumericalMeasureField': {
                'FieldId': f'{vid}-val',
                'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': col},
                'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
            }}],
            'TargetValues': [],
            'TrendGroups': []
        }
        kv['ChartConfiguration']['KPIOptions'] = {
            'Comparison': {'ComparisonMethod': 'DIFFERENCE'},
            'ProgressBar': {'Visibility': 'HIDDEN'},
            'SecondaryValue': {'Visibility': 'VISIBLE'},
            'TrendArrows': {'Visibility': 'VISIBLE'},
            'PrimaryValueDisplayType': 'ACTUAL'
        }
        kv['Title'] = {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': title}}
        kv['Subtitle'] = {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Latest week in quarter'}}
        print(f'Rebuilt tile: {vid} → MAX({col})')

# ── 3. Strip CalculatedFieldId ─────────────────────────────────────────────
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
]

# ── Push and publish ───────────────────────────────────────────────────────
kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASH_ID, Name=name, Definition=defn,
    VersionDescription='Fix KPI tiles: direct MAX aggregation on raw columns, remove broken cur_* fields'
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
