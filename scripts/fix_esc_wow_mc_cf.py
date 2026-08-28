#!/usr/bin/env python3
"""
Fix two issues:
1. Escalation sheet KPIs: add WoW comparison using escalations_wow from kpi_snapshots
2. MC Customer Health table: fix CF to use solid CE colors (visible on MIDNIGHT theme)
"""
import boto3, json, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

# ── 1. Add escalations_wow as calculated field if not already present ──────
calc_fields = defn.setdefault('CalculatedFields', [])
if not any(c['Name'] == 'escalations_prev' for c in calc_fields):
    calc_fields.append({
        'DataSetIdentifier': 'kpi_snapshots',
        'Name': 'escalations_prev',
        'Expression': '{open_escalations} - {escalations_wow}'
    })
    print('Added calculated field: escalations_prev')

# ── 2. Add escalations_prev to kpi_snapshots dataset declarations ──────────
# escalations_wow must be declared — check if it exists
ds_decls = defn['DataSetIdentifierDeclarations']
kpi_ds = next(d for d in ds_decls if d['Identifier'] == 'kpi_snapshots')
print(f'kpi_snapshots dataset: {kpi_ds["DataSetArn"]}')

# ── 3. Fix escalation KPI tiles — add TargetValues using escalations_prev ──
esc_sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-escalations')
kpi_fixes = {
    'kpi-esc-total': ('issue_key', 'DISTINCT_COUNT', 'escalations', 'escalations_prev', 'kpi_snapshots'),
}
# The escalation KPIs use the escalations dataset (live Jira data), not kpi_snapshots
# WoW comparison: add a filter-based prior week KPI using kpi_snapshots.open_escalations
# Replace kpi-esc-total to use kpi_snapshots for WoW
for v in esc_sheet['Visuals']:
    kpi = v.get('KPIVisual', {})
    vid = kpi.get('VisualId', '')
    if vid == 'kpi-esc-total':
        # Switch to kpi_snapshots for WoW-capable data
        kpi['ChartConfiguration']['FieldWells'] = {
            'Values': [{'NumericalMeasureField': {
                'FieldId': 'kpi-esc-total-v',
                'Column': {'DataSetIdentifier': 'kpi_snapshots', 'ColumnName': 'open_escalations'},
                'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
            }}],
            'TargetValues': [{'NumericalMeasureField': {
                'FieldId': 'kpi-esc-total-prev',
                'Column': {'DataSetIdentifier': 'kpi_snapshots', 'ColumnName': 'escalations_prev'},
                'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
            }}],
            'TrendGroups': []
        }
        kpi['ChartConfiguration']['KPIOptions'] = {
            'Comparison': {'ComparisonMethod': 'DIFFERENCE'},
            'PrimaryValueDisplayType': 'ACTUAL',
            'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE', 'TooltipVisibility': 'HIDDEN'}
        }
        print(f'Fixed {vid}: now uses kpi_snapshots with WoW')

    elif vid == 'kpi-esc-high':
        kpi['ChartConfiguration']['FieldWells'] = {
            'Values': [{'NumericalMeasureField': {
                'FieldId': 'kpi-esc-high-v',
                'Column': {'DataSetIdentifier': 'kpi_snapshots', 'ColumnName': 'escalations_high_priority'},
                'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
            }}],
            'TargetValues': [],
            'TrendGroups': []
        }
        print(f'Fixed {vid}: now uses kpi_snapshots')

# ── 4. Fix MC Customer Health table CF ─────────────────────────────────────
mc_sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-mc-delivery')
for v in mc_sheet['Visuals']:
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') != 'tbl-mc':
        continue

    # Disable row alternate colors so cell CF is visible
    tbl['ChartConfiguration']['TableOptions']['RowAlternateColorOptions'] = {
        'Status': 'ENABLED', 'RowAlternateColors': ['#2A1545']
    }

    # Replace pastel row CF with solid cell CF on health_overall (g1)
    tbl['ConditionalFormatting'] = {'ConditionalFormattingOptions': [
        {'Cell': {'FieldId': 'tbl-mc-g1', 'TextFormat': {'BackgroundColor': {'Solid': {
            'Expression': "{health_overall} = 'Red'", 'Color': '#D74018'}}}}},
        {'Cell': {'FieldId': 'tbl-mc-g1', 'TextFormat': {'BackgroundColor': {'Solid': {
            'Expression': "{health_overall} = 'Green'", 'Color': '#33A94F'}}}}},
    ]}
    print('Fixed tbl-mc: solid CE colors on health_overall cell')
    break

# ── 5. Update analysis + republish dashboard ───────────────────────────────
qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print('Analysis updated')

resp2 = qs.update_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    Name='COO Operational Dashboard (prod)', Definition=defn, ThemeArn=THEME_ARN)
new_ver = resp2['VersionArn'].split('/')[-1]
print(f'Dashboard version {new_ver} creating...')

for _ in range(30):
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if str(v['VersionNumber']) == str(new_ver)), None)
    if match and match['Status'] == 'CREATION_SUCCESSFUL':
        break
    if match and 'FAILED' in match.get('Status', ''):
        print(f'Failed: {match["Status"]}'); exit(1)
    time.sleep(3)

qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=int(new_ver))
print(f'✅ Published version {new_ver}')
