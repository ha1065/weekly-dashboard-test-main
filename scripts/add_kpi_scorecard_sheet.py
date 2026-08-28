#!/usr/bin/env python3
"""S01-09: Add Org KPI Scorecard sheet to the COO Operational Analysis dashboard.

Layout:
  Row 0-3  : 4 KPI tiles (On-Time Delivery, Compliance, Utilization, Open Escalations)
  Row 4-23 : 2x2 grid of monthly trend line charts (monthly AVG, last 6 months)

KPI tile approach (per architect review):
  - Filter the sheet to last 13 weeks (current quarter + prior quarter minimum coverage)
  - Trend charts get a separate 6-month filter
  - KPI tiles use LAST_VALUE window function equivalent via calculated field:
    week_rank = denseRank(week_start_date, [week_start_date], DESC, PRE_FILTER)
    Primary value = MAX filtered to week_rank = 1 (current week)
    Target value  = MAX filtered to week_rank = prior-quarter-same-ISO-week row
  - Simpler approach: no per-visual filters on tiles; rely on a single "current week"
    filter group scoped to tile visuals only, and a separate "prior quarter same week"
    filter group scoped to the target fields via a calculated field flag.

  QuickSight limitation: you cannot scope primary vs target values to different filter groups
  within the same visual. The reliable approach is to use two separate calculated fields:
    - current_week_<col>  = ifelse(week_start_date = maxOver(week_start_date, [], PRE_FILTER), <col>, NULL)
    - prior_week_<col>    = ifelse(week_start_date = prior_qtr_same_week_date, <col>, NULL)
  Then MAX aggregate each. The NULL-safe MAX will pick the one non-null value per filter context.

FR refs: FR-17-001, FR-17-002
"""
import boto3, time

PROFILE      = 'AWSAdministratorAccess-961341524729'
REGION       = 'us-east-1'
ACCOUNT      = '961341524729'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
DS_ID        = 'KPI Weekly Snapshots (prod)'

SHEET_ID   = 'sheet-kpi-scorecard'
SHEET_NAME = 'Org KPI Scorecard'

TILE_OTD_ID   = 'kpi-tile-otd'
TILE_COMP_ID  = 'kpi-tile-compliance'
TILE_UTIL_ID  = 'kpi-tile-util'
TILE_ESC_ID   = 'kpi-tile-escalations'
TREND_OTD_ID  = 'trend-otd'
TREND_COMP_ID = 'trend-compliance'
TREND_UTIL_ID = 'trend-util'
TREND_ESC_ID  = 'trend-escalations'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── 1. Get current dashboard ───────────────────────────────────────────────
d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Definition']

ids = {x['Identifier'] for x in defn.get('DataSetIdentifierDeclarations', [])}
if DS_ID not in ids:
    raise SystemExit(f'Dataset "{DS_ID}" not registered in dashboard. Found: {ids}')
print(f'Dataset "{DS_ID}" confirmed.')

# ── 2. Remove existing sheet/filters (idempotent) ─────────────────────────
FG_IDS = ('fg-scorecard-6month', 'fg-scorecard-cur-qtr', 'fg-scorecard-tiles')
defn['Sheets']       = [s  for s  in defn['Sheets']       if s['SheetId']       != SHEET_ID]
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', []) if fg['FilterGroupId'] not in FG_IDS]

# ── 3. Calculated fields ───────────────────────────────────────────────────
# Remove old versions of our CFs so we can re-add with correct expressions
OUR_CF_NAMES = {
    'month_label', 'month_sort_key', 'quarter_label', 'is_current_quarter',
    'is_qtd_latest_week', 'is_prior_qtr_same_week',
    'cur_ps_on_time_pct', 'pri_ps_on_time_pct',
    'cur_time_compliance_pct', 'pri_time_compliance_pct',
    'cur_billable_util_pct', 'pri_billable_util_pct',
    'cur_open_escalations', 'pri_open_escalations',
}
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
    if cf.get('Name') not in OUR_CF_NAMES
]

def add_cf(cf_id, cf_name, expression):
    defn['CalculatedFields'].append({
        'DataSetIdentifier': DS_ID,
        'Name': cf_name,
        'Expression': expression
    })

# Only add calculated fields actually used in visuals (cur_*/pri_* for KPI tiles)
# Drop month_label, month_sort_key, quarter_label, is_current_quarter — not referenced in visuals

for cf_name, col in [
    ('cur_ps_on_time_pct',      'ps_on_time_pct'),
    ('cur_time_compliance_pct',  'time_compliance_pct'),
    ('cur_billable_util_pct',    'billable_util_pct'),
    ('cur_open_escalations',     'open_escalations'),
]:
    add_cf(None, cf_name,
           f"ifelse(week_start_date = maxOver(week_start_date, [], PRE_FILTER), {{{col}}}, NULL)")

# Prior quarter same-ISO-week value: row where year/quarter is one quarter back
# and week_num matches the latest week_num in current quarter.
# Instead of using week_num (which repeats annually), extract the ISO week from
# week_start_date, then filter for rows where:
#   - quarter is one quarter prior (or Q4 if current is Q1)
#   - quarter(week_start_date) matches the extracted ISO week from current quarter's latest
#
# Implementation: Compare the INTEGER day-of-year offset within the quarter.
# Q4 of prior year = (year-1, Q4): dates from ~Oct 1 to Dec 31
# Current Q1 = (year, Q1): dates from ~Jan 1 to Mar 31
# Safe heuristic: filter for rows where quarter_offset matches current_qtr_latest_offset
for cf_name, col in [
    ('pri_ps_on_time_pct',     'ps_on_time_pct'),
    ('pri_time_compliance_pct', 'time_compliance_pct'),
    ('pri_billable_util_pct',   'billable_util_pct'),
    ('pri_open_escalations',    'open_escalations'),
]:
    add_cf(None, cf_name,
        f"ifelse("
        f"  dateDiff(week_start_date, maxOver(week_start_date, [], PRE_FILTER)) = -91,"
        f"  {{{col}}}, NULL"
        f")"
    )

print(f'Added {len(OUR_CF_NAMES)} calculated fields.')

# ── 4. Build KPI visuals ───────────────────────────────────────────────────
def kpi_visual(visual_id, cur_col, pri_col, title):
    """Primary = MAX(cur_col), Target = MAX(pri_col). Both NULL-safe — MAX ignores NULLs."""
    return {
        'KPIVisual': {
            'VisualId': visual_id,
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': title}},
            'Subtitle': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'vs same week prior quarter'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{'NumericalMeasureField': {
                        'FieldId': f'{visual_id}-val',
                        'Column': {'DataSetIdentifier': DS_ID, 'ColumnName': cur_col},
                        'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
                    }}],
                    'TargetValues': [{'NumericalMeasureField': {
                        'FieldId': f'{visual_id}-target',
                        'Column': {'DataSetIdentifier': DS_ID, 'ColumnName': pri_col},
                        'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}
                    }}],
                    'TrendGroups': []
                },
                'KPIOptions': {
                    'Comparison': {'ComparisonMethod': 'DIFFERENCE'},
                    'ProgressBar': {'Visibility': 'HIDDEN'},
                    'SecondaryValue': {'Visibility': 'VISIBLE'},
                }
            }
        }
    }

# ── 5. Build trend line visuals ────────────────────────────────────────────
def trend_visual(visual_id, col, title):
    return {
        'LineChartVisual': {
            'VisualId': visual_id,
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': title}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {
                            'FieldId': f'{visual_id}-month',
                            'Column': {'DataSetIdentifier': DS_ID, 'ColumnName': 'week_start_date'},
                            'DateGranularity': 'MONTH'
                        }}],
                        'Values': [{'NumericalMeasureField': {
                            'FieldId': f'{visual_id}-val',
                            'Column': {'DataSetIdentifier': DS_ID, 'ColumnName': col},
                            'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                        }}],
                        'Colors': []
                    }
                },
                'Type': 'LINE',
                'Legend': {'Visibility': 'HIDDEN'},
                'DataLabels': {'Visibility': 'HIDDEN'},
            }
        }
    }

# ── 6. Build sheet ─────────────────────────────────────────────────────────
new_sheet = {
    'SheetId': SHEET_ID,
    'Name': SHEET_NAME,
    'Visuals': [
        kpi_visual(TILE_OTD_ID,  'cur_ps_on_time_pct',     'pri_ps_on_time_pct',     'On-Time Delivery (PS)'),
        kpi_visual(TILE_COMP_ID, 'cur_time_compliance_pct', 'pri_time_compliance_pct', 'Timesheet Compliance'),
        kpi_visual(TILE_UTIL_ID, 'cur_billable_util_pct',   'pri_billable_util_pct',   'Utilization'),
        kpi_visual(TILE_ESC_ID,  'cur_open_escalations',    'pri_open_escalations',    'Open Escalations'),
        trend_visual(TREND_OTD_ID,  'ps_on_time_pct',      'On-Time Delivery Trend'),
        trend_visual(TREND_COMP_ID, 'time_compliance_pct', 'Timesheet Compliance Trend'),
        trend_visual(TREND_UTIL_ID, 'billable_util_pct',   'Utilization Trend'),
        trend_visual(TREND_ESC_ID,  'open_escalations',    'Open Escalations Trend'),
    ],
    'Layouts': [{'Configuration': {'GridLayout': {'Elements': [
        {'ElementId': TILE_OTD_ID,   'ElementType': 'VISUAL', 'ColumnIndex': 0,  'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': TILE_COMP_ID,  'ElementType': 'VISUAL', 'ColumnIndex': 9,  'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': TILE_UTIL_ID,  'ElementType': 'VISUAL', 'ColumnIndex': 18, 'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': TILE_ESC_ID,   'ElementType': 'VISUAL', 'ColumnIndex': 27, 'ColumnSpan': 9,  'RowIndex': 0,  'RowSpan': 4},
        {'ElementId': TREND_OTD_ID,  'ElementType': 'VISUAL', 'ColumnIndex': 0,  'ColumnSpan': 18, 'RowIndex': 4,  'RowSpan': 10},
        {'ElementId': TREND_COMP_ID, 'ElementType': 'VISUAL', 'ColumnIndex': 18, 'ColumnSpan': 18, 'RowIndex': 4,  'RowSpan': 10},
        {'ElementId': TREND_UTIL_ID, 'ElementType': 'VISUAL', 'ColumnIndex': 0,  'ColumnSpan': 18, 'RowIndex': 14, 'RowSpan': 10},
        {'ElementId': TREND_ESC_ID,  'ElementType': 'VISUAL', 'ColumnIndex': 18, 'ColumnSpan': 18, 'RowIndex': 14, 'RowSpan': 10},
    ]}}}]
}
defn['Sheets'].append(new_sheet)

# ── 7. Filter groups ───────────────────────────────────────────────────────
# Tiles: last 26 weeks (covers current + prior quarter fully)
defn['FilterGroups'].append({
    'FilterGroupId': 'fg-scorecard-tiles',
    'Filters': [{'RelativeDatesFilter': {
        'FilterId': 'fg-scorecard-tiles-f',
        'Column': {'DataSetIdentifier': DS_ID, 'ColumnName': 'week_start_date'},
        'AnchorDateConfiguration': {'AnchorOption': 'NOW'},
        'RelativeDateType': 'LAST',
        'RelativeDateValue': 26,
        'TimeGranularity': 'WEEK',
        'NullOption': 'NON_NULLS_ONLY'
    }}],
    'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
        {'SheetId': SHEET_ID, 'Scope': 'SELECTED_VISUALS',
         'VisualIds': [TILE_OTD_ID, TILE_COMP_ID, TILE_UTIL_ID, TILE_ESC_ID]}
    ]}},
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})

# Trend charts: last 6 months
defn['FilterGroups'].append({
    'FilterGroupId': 'fg-scorecard-6month',
    'Filters': [{'RelativeDatesFilter': {
        'FilterId': 'fg-scorecard-6month-f',
        'Column': {'DataSetIdentifier': DS_ID, 'ColumnName': 'week_start_date'},
        'AnchorDateConfiguration': {'AnchorOption': 'NOW'},
        'RelativeDateType': 'LAST',
        'RelativeDateValue': 6,
        'TimeGranularity': 'MONTH',
        'NullOption': 'NON_NULLS_ONLY'
    }}],
    'ScopeConfiguration': {'SelectedSheets': {'SheetVisualScopingConfigurations': [
        {'SheetId': SHEET_ID, 'Scope': 'SELECTED_VISUALS',
         'VisualIds': [TREND_OTD_ID, TREND_COMP_ID, TREND_UTIL_ID, TREND_ESC_ID]}
    ]}},
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})

# ── 8. Push and publish (with status poll) ────────────────────────────────
kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, Name=name, Definition=defn,
    VersionDescription='S01-09 v3: Org KPI Scorecard — cur/pri calculated fields, scoped filters'
)
if theme_arn:
    kwargs['ThemeArn'] = theme_arn

resp    = qs.update_dashboard(**kwargs)
version = int(resp['VersionArn'].split('/')[-1])
print(f'Version {version} created. Polling for status...')

deadline = time.time() + 60
while time.time() < deadline:
    time.sleep(5)
    ver = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
    status = ver.get('ResourceStatus', '')
    if 'SUCCESSFUL' in status or 'FAILED' in status:
        break

errors = ver.get('Errors', [])
if errors:
    for e in errors:
        print(f'  ❌ {e.get("Type")}: {e.get("Message")}')
    print('Not published.')
else:
    qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=version)
    print(f'✅ Published version {version} — "{SHEET_NAME}" is live.')
