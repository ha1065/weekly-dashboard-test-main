#!/usr/bin/env python3
"""
Add productive_util_pct KPI tiles to the KPI Tracking dashboard.
- Sheet 2 (Practice Scorecard): adds after existing KPI tiles
- Sheet 3 (Staff Detail): adds after existing KPI tiles
"""
import boto3
import json
import time

qs = boto3.Session(
    profile_name='AWSAdministratorAccess-961341524729',
    region_name='us-east-1'
).client('quicksight')

ACCOUNT     = '961341524729'
ANALYSIS_ID = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN   = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

# ── Fetch live analysis definition ──────────────────────────────────────────
defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
name = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']

# ── Helper: build a KPI visual dict ─────────────────────────────────────────
def make_kpi_visual(visual_id, title, dataset_identifier, column_name, field_id):
    return {
        'KPIVisual': {
            'VisualId': visual_id,
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': title}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{
                        'NumericalMeasureField': {
                            'FieldId': field_id,
                            'Column': {
                                'DataSetIdentifier': dataset_identifier,
                                'ColumnName': column_name
                            },
                            'AggregationFunction': {
                                'SimpleNumericalAggregation': 'AVERAGE'
                            }
                        }
                    }],
                    'TargetValues': [],
                    'TrendGroups': []
                },
                'SortConfiguration': {},
                'KPIOptions': {
                    'PrimaryValueDisplayType': 'ACTUAL',
                    'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE'},
                    'ProgressBar': {'Visibility': 'HIDDEN'}
                }
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }

# ── Sheet 2: Practice Scorecard ──────────────────────────────────────────────
# Current layout: 4 KPI tiles at row=2, each 9 cols wide (total=36, no room).
# Strategy: resize each of the 4 tiles from 9→7 cols (4×7=28), add new tile at col=28 width=8.
S2_KPI_ELEMENT_IDS = [
    'kpi-s2-headcount', 'kpi-s2-billable', 'kpi-s2-compliance', 'kpi-s2-hours'
]
NEW_VISUAL_S2  = 'kpi-s2-productive-util'
S2_KPI_ROW     = 2
S2_KPI_ROWSPAN = 4

added_s2 = False
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] != 'sheet-kpi-s2':
        continue

    # Add visual if not already present
    existing_ids = [
        v.get(list(v.keys())[0], {}).get('VisualId', '')
        for v in sheet.get('Visuals', [])
    ]
    if NEW_VISUAL_S2 in existing_ids:
        print(f'Sheet 2: {NEW_VISUAL_S2} visual already present')
    else:
        sheet['Visuals'].append(make_kpi_visual(
            NEW_VISUAL_S2, 'Productive Util %',
            'kpi_practice', 'productive_util_pct', 'kpi-s2-prod-util-v'
        ))
        print(f'Sheet 2: Added {NEW_VISUAL_S2} visual')

    for layout in sheet.get('Layouts', []):
        grid     = layout.get('Configuration', {}).get('GridLayout', {})
        elements = grid.get('Elements', [])
        el_ids   = [e.get('ElementId') for e in elements]

        if NEW_VISUAL_S2 in el_ids:
            print(f'Sheet 2: {NEW_VISUAL_S2} already in layout, skipping')
            added_s2 = True
            break

        # Resize the 4 existing tiles: sort by ColumnIndex, assign cols 0,7,14,21 width 7
        kpi_els = [e for e in elements if e.get('ElementId') in S2_KPI_ELEMENT_IDS]
        kpi_els_sorted = sorted(kpi_els, key=lambda e: e.get('ColumnIndex', 0))
        new_col = 0
        for el in kpi_els_sorted:
            el['ColumnIndex'] = new_col
            el['ColumnSpan']  = 7
            new_col += 7
        print(f'Sheet 2: Resized {len(kpi_els_sorted)} existing tiles to width 7')

        # Add new tile at col=28 width=8 (28+8=36)
        elements.append({
            'ElementId':   NEW_VISUAL_S2,
            'ElementType': 'VISUAL',
            'ColumnIndex': 28,
            'ColumnSpan':  8,
            'RowIndex':    S2_KPI_ROW,
            'RowSpan':     S2_KPI_ROWSPAN,
        })
        print(f'Sheet 2: Placed {NEW_VISUAL_S2} at col=28 row=2 span=8x4')
        added_s2 = True
        break
    break

# ── Sheet 3: Staff Detail ─────────────────────────────────────────────────────
# Current layout: 5 KPI tiles at row=2 (widths: 7,7,7,7,8 = 36, no room).
# Strategy: resize all 5 to width 6 (5×6=30), add new tile at col=30 width=6.
S3_KPI_ELEMENT_IDS = [
    'kpi-s3-headcount', 'kpi-s3-billable', 'kpi-s3-compliance',
    'kpi-s3-billhours', 'kpi-s3-ontime'
]
NEW_VISUAL_S3  = 'kpi-s3-productive-util'
S3_KPI_ROW     = 2
S3_KPI_ROWSPAN = 4

added_s3 = False
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] != 'sheet-kpi-s3':
        continue

    existing_ids = [
        v.get(list(v.keys())[0], {}).get('VisualId', '')
        for v in sheet.get('Visuals', [])
    ]
    if NEW_VISUAL_S3 in existing_ids:
        print(f'Sheet 3: {NEW_VISUAL_S3} visual already present')
    else:
        sheet['Visuals'].append(make_kpi_visual(
            NEW_VISUAL_S3, 'Productive Util %',
            'kpi_staff', 'productive_util_pct', 'kpi-s3-prod-util-v'
        ))
        print(f'Sheet 3: Added {NEW_VISUAL_S3} visual')

    for layout in sheet.get('Layouts', []):
        grid     = layout.get('Configuration', {}).get('GridLayout', {})
        elements = grid.get('Elements', [])
        el_ids   = [e.get('ElementId') for e in elements]

        if NEW_VISUAL_S3 in el_ids:
            print(f'Sheet 3: {NEW_VISUAL_S3} already in layout, skipping')
            added_s3 = True
            break

        # Resize 5 existing tiles to width 6, re-pack left-to-right
        kpi_els = [e for e in elements if e.get('ElementId') in S3_KPI_ELEMENT_IDS]
        kpi_els_sorted = sorted(kpi_els, key=lambda e: e.get('ColumnIndex', 0))
        new_col = 0
        for el in kpi_els_sorted:
            el['ColumnIndex'] = new_col
            el['ColumnSpan']  = 6
            new_col += 6
        print(f'Sheet 3: Resized {len(kpi_els_sorted)} existing tiles to width 6')

        # Add new tile at col=30 width=6 (30+6=36)
        elements.append({
            'ElementId':   NEW_VISUAL_S3,
            'ElementType': 'VISUAL',
            'ColumnIndex': 30,
            'ColumnSpan':  6,
            'RowIndex':    S3_KPI_ROW,
            'RowSpan':     S3_KPI_ROWSPAN,
        })
        print(f'Sheet 3: Placed {NEW_VISUAL_S3} at col=30 row=2 span=6x4')
        added_s3 = True
        break
    break

# ── Update analysis ──────────────────────────────────────────────────────────
print()
print('Updating analysis...')
try:
    qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name=name,
        ThemeArn=THEME_ARN,
        Definition=defn
    )
except Exception as e:
    print(f'update_analysis error: {e}')
    raise

# Wait for analysis update
for _ in range(24):
    time.sleep(5)
    status = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Status']
    print(f'  Analysis: {status}')
    if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
        print('Analysis update successful')
        break
    if 'FAILED' in status:
        errs = qs.describe_analysis_definition(
            AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID
        ).get('Errors', [])
        print('ERRORS:', json.dumps(errs, indent=2, default=str))
        raise SystemExit(1)

# ── Republish dashboard ──────────────────────────────────────────────────────
print()
print('Republishing dashboard...')
defn2 = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)',
    Definition=defn2,
    ThemeArn=THEME_ARN
)
new_ver = int(resp['VersionArn'].split('/')[-1])
print(f'Waiting for v{new_ver} to be created...')

for _ in range(40):
    time.sleep(4)
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
    if not match:
        continue
    s = match['Status']
    if s == 'CREATION_SUCCESSFUL':
        qs.update_dashboard_published_version(
            AwsAccountId=ACCOUNT,
            DashboardId=DASHBOARD_ID,
            VersionNumber=new_ver
        )
        print(f'✅ Published dashboard v{new_ver}')
        break
    elif 'FAILED' in s:
        print(f'Dashboard creation FAILED: {match}')
        raise SystemExit(1)
    else:
        print(f'  Status: {s}')

print()
print('Done! Summary:')
print(f'  Sheet 2 visual added: {added_s2}')
print(f'  Sheet 3 visual added: {added_s3}')
print(f'  Dashboard version:    v{new_ver}')
