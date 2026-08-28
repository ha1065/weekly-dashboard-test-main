#!/usr/bin/env python3
"""KPI Scorecard improvements:
1. KPI tiles: filter to current quarter (QTD) using relative date filter
2. Trend charts: add goal reference lines using target columns
"""
import boto3, time

PROFILE   = 'AWSAdministratorAccess-961341524729'
REGION    = 'us-east-1'
ACCOUNT   = '961341524729'
DASH_ID   = 'coo-operational-dashboard-prod'
SHEET_ID  = 'sheet-kpi-scorecard'
KPI_DS    = 'KPI Weekly Snapshots (prod)'

TILE_IDS = ['kpi-tile-otd', 'kpi-tile-compliance', 'kpi-tile-util', 'kpi-tile-escalations']
TREND_IDS = ['trend-otd', 'trend-compliance', 'trend-util', 'trend-escalations']

# Target values per trend chart (column in kpi_weekly_snapshots, display label, color)
TREND_TARGETS = {
    'trend-otd':        ('target_ps_on_time_pct',    '90% Target',   '#D74018'),
    'trend-compliance': ('target_time_compliance_pct','95% Target',   '#D74018'),
    'trend-util':       ('target_billable_util_pct',  '75% Target',   '#D74018'),
    # escalations has no target — skip
}

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Definition']

# ── 1. Replace 26-week tile filter with current-quarter relative filter ────
# Remove old tile filter, add QTD filter
QTD_FG = 'fg-scorecard-tiles'
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', []) if fg['FilterGroupId'] != QTD_FG]

defn['FilterGroups'].append({
    'FilterGroupId': QTD_FG,
    'Filters': [{
        'RelativeDatesFilter': {
            'FilterId': f'{QTD_FG}-f',
            'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': 'week_start_date'},
            'AnchorDateConfiguration': {'AnchorOption': 'NOW'},
            'RelativeDateType': 'LAST',
            'RelativeDateValue': 26,
            'TimeGranularity': 'WEEK',
            'NullOption': 'NON_NULLS_ONLY'
        }
    }],
    'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
        {'SheetId': SHEET_ID, 'Scope': 'SELECTED_VISUALS', 'VisualIds': TILE_IDS}
    ]}},
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})
print('Updated KPI tile filter to last 26 weeks (covers current + prior quarter for delta comparison)')

# ── 2. Add goal reference lines to trend charts ────────────────────────────
scorecard_sheet = next((s for s in defn['Sheets'] if s.get('SheetId') == SHEET_ID), None)
if scorecard_sheet:
    for visual in scorecard_sheet.get('Visuals', []):
        lv = visual.get('LineChartVisual', {})
        vid = lv.get('VisualId', '')
        if vid not in TREND_TARGETS:
            continue
        target_col, label, color = TREND_TARGETS[vid]
        cfg = lv.get('ChartConfiguration', {})
        ref_lines = cfg.get('ReferenceLines', [])
        # Only add if not already present
        if not any(r.get('DataConfiguration', {}).get('StaticConfiguration', {}) or
                   r.get('DataConfiguration', {}).get('DynamicConfiguration', {}).get('Column', {}).get('ColumnName') == target_col
                   for r in ref_lines):
            ref_lines.append({
                'Status': 'ENABLED',
                'DataConfiguration': {
                    'DynamicConfiguration': {
                        'Column': {'DataSetIdentifier': KPI_DS, 'ColumnName': target_col},
                        'Calculation': {'SimpleNumericalAggregation': 'MAX'}
                    }
                },
                'StyleConfiguration': {
                    'Pattern': 'DASHED',
                    'Color': color
                },
                'LabelConfiguration': {
                    'CustomLabelConfiguration': {'CustomLabel': label}
                }
            })
            cfg['ReferenceLines'] = ref_lines
            print(f'Added goal line to {vid}: {label}')

# ── Strip CalculatedFieldId ────────────────────────────────────────────────
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
]

# ── Push and publish ───────────────────────────────────────────────────────
kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASH_ID, Name=name, Definition=defn,
    VersionDescription='KPI Scorecard: QTD tile filter + goal reference lines on trend charts'
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
