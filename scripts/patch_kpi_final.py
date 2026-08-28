"""
patch_kpi_final.py — Three targeted patches to the KPI Tracking Dashboard analysis.

Patch 1 — Add TopBottomFilter FilterGroups (fg-s*-kpi) scoped to KPI tile visuals only.
           These always show the most-recently-reported week on the tiles regardless of
           the date-range control selection.

Patch 2 — Change fg-s1-date and fg-s2-date scope from SELECTED_VISUALS → ALL_VISUALS
           so the RelativeDateTime date-range control also drives the trend charts.
           (fg-s3-date is already ALL_VISUALS — left unchanged.)

Patch 3 — Ensure dropdown FilterControls on Sheets 2 and 3 are correctly configured
           (SINGLE_SELECT, SelectAllOptions VISIBLE, no hardcoded SelectableValues).
           Idempotent — current state is already correct, but we apply defensively.

Run:
    python3 scripts/patch_kpi_final.py
"""

import boto3
import json
import time

# ── Config ─────────────────────────────────────────────────────────────────
PROFILE   = 'AWSAdministratorAccess-961341524729'
REGION    = 'us-east-1'
ACCOUNT   = '961341524729'
ANALYSIS_ID  = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN    = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── Fetch current definition ────────────────────────────────────────────────
print('Fetching analysis definition…')
resp   = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn   = resp['Definition']
name   = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']
print(f'  Analysis name : {name}')
print(f'  FilterGroups  : {[fg["FilterGroupId"] for fg in defn.get("FilterGroups", [])]}')
print()

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 2 — Change fg-s1-date and fg-s2-date scope to ALL_VISUALS
# ═══════════════════════════════════════════════════════════════════════════
print('──────────────────────────────────────────────')
print('PATCH 2: Setting fg-s1-date and fg-s2-date to ALL_VISUALS')
print('──────────────────────────────────────────────')

for fg in defn.get('FilterGroups', []):
    if fg['FilterGroupId'] in ('fg-s1-date', 'fg-s2-date'):
        scope_configs = fg['ScopeConfiguration']['SelectedSheets']['SheetVisualScopingConfigurations']
        for s in scope_configs:
            old_scope = s['Scope']
            s['Scope'] = 'ALL_VISUALS'
            s.pop('VisualIds', None)       # remove explicit visual list — not needed for ALL_VISUALS
            print(f"  {fg['FilterGroupId']}: scope {old_scope} → ALL_VISUALS")

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 1 — Add TopBottomFilter groups for KPI tiles
# ═══════════════════════════════════════════════════════════════════════════
print()
print('──────────────────────────────────────────────')
print('PATCH 1: Adding TopBottomFilter groups for KPI tiles')
print('──────────────────────────────────────────────')

kpi_tile_configs = [
    {
        'fg_id':      'fg-s1-kpi',
        'filter_id':  'f-s1-kpi',          # inner FilterId must be unique
        'dataset':    'kpi_snapshots',
        'column':     'week_start_date',
        'sheet_id':   'sheet-kpi-s1',
        'visual_ids': [
            'kpi-s1-billable-util',
            'kpi-s1-compliance',
            'kpi-s1-ps-ontime',
            'kpi-s1-escalations',
            'kpi-s1-resources',
            'kpi-s1-eng-duration',
            'kpi-s1-red-pct',
            'kpi-s1-mc-ontime',
        ],
    },
    {
        'fg_id':      'fg-s2-kpi',
        'filter_id':  'f-s2-kpi',
        'dataset':    'kpi_practice',
        'column':     'week_start',
        'sheet_id':   'sheet-kpi-s2',
        'visual_ids': [
            'kpi-s2-headcount',
            'kpi-s2-billable',
            'kpi-s2-compliance',
        ],
    },
    {
        'fg_id':      'fg-s3-kpi',
        'filter_id':  'f-s3-kpi',
        'dataset':    'kpi_staff',
        'column':     'week_start',
        'sheet_id':   'sheet-kpi-s3',
        'visual_ids': [
            'kpi-s3-headcount',
            'kpi-s3-billable',
            'kpi-s3-compliance',
            'kpi-s3-billhours',
        ],
    },
]

# Remove any previous fg-s*-kpi groups to avoid duplicates on re-runs
before = len(defn.get('FilterGroups', []))
defn['FilterGroups'] = [
    fg for fg in defn.get('FilterGroups', [])
    if fg['FilterGroupId'] not in {c['fg_id'] for c in kpi_tile_configs}
]
removed = before - len(defn['FilterGroups'])
if removed:
    print(f'  Removed {removed} stale fg-s*-kpi group(s) from previous run')

for cfg in kpi_tile_configs:
    new_fg = {
        'FilterGroupId': cfg['fg_id'],
        'Filters': [
            {
                'TopBottomFilter': {
                    'FilterId': cfg['filter_id'],
                    'Column': {
                        'DataSetIdentifier': cfg['dataset'],
                        'ColumnName':        cfg['column'],
                    },
                    'Limit': 1,
                    'AggregationSortConfigurations': [
                        {
                            'Column': {
                                'DataSetIdentifier': cfg['dataset'],
                                'ColumnName':        cfg['column'],
                            },
                            'SortDirection':      'DESC',
                            'AggregationFunction': {
                                'DateAggregationFunction': 'MAX',
                            },
                        }
                    ],
                    # NOTE: 'Type' (TOP/BOTTOM) is NOT a valid boto3 parameter for TopBottomFilter.
                    # The sort direction (DESC) implicitly means TOP N by MAX date.
                    'TimeGranularity': 'WEEK',
                }
            }
        ],
        'ScopeConfiguration': {
            'SelectedSheets': {
                'SheetVisualScopingConfigurations': [
                    {
                        'SheetId':   cfg['sheet_id'],
                        'Scope':     'SELECTED_VISUALS',
                        'VisualIds': cfg['visual_ids'],
                    }
                ]
            }
        },
        'Status':       'ENABLED',
        'CrossDataset': 'SINGLE_DATASET',
    }
    defn['FilterGroups'].append(new_fg)
    print(f"  Added TopBottomFilter group: {cfg['fg_id']}  →  {len(cfg['visual_ids'])} KPI tile(s) on {cfg['sheet_id']}")

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 3 — Ensure dropdown controls are correctly configured (idempotent)
# ═══════════════════════════════════════════════════════════════════════════
print()
print('──────────────────────────────────────────────')
print('PATCH 3: Verifying/fixing dropdown controls on Sheets 2 and 3')
print('──────────────────────────────────────────────')

DROPDOWN_SHEET_IDS = ('sheet-kpi-s2', 'sheet-kpi-s3')
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] not in DROPDOWN_SHEET_IDS:
        continue
    for fc in sheet.get('FilterControls', []):
        if 'Dropdown' not in fc:
            continue
        dd  = fc['Dropdown']
        old_type = dd.get('Type')
        # Ensure correct type
        dd['Type'] = 'SINGLE_SELECT'
        # Ensure DisplayOptions has SelectAllOptions and TitleOptions visible
        dd['DisplayOptions'] = {
            'SelectAllOptions': {'Visibility': 'VISIBLE'},
            'TitleOptions':     {
                'Visibility':       'VISIBLE',
                'FontConfiguration': {
                    'FontSize': {'Relative': 'MEDIUM'}
                },
            },
        }
        # Do NOT set SelectableValues — QuickSight auto-populates from data
        dd.pop('SelectableValues', None)
        changed = '(updated)' if old_type != 'SINGLE_SELECT' else '(already correct)'
        print(f"  Dropdown '{dd.get('Title', dd.get('FilterControlId'))}' on {sheet['SheetId']}: Type=SINGLE_SELECT {changed}")

# ═══════════════════════════════════════════════════════════════════════════
# SUBMIT update_analysis (primary attempt with TopBottomFilter)
# ═══════════════════════════════════════════════════════════════════════════
print()
print('──────────────────────────────────────────────')
print('Submitting update_analysis…')
print('──────────────────────────────────────────────')

top_bottom_accepted = False
try:
    qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name=name,
        ThemeArn=THEME_ARN,
        Definition=defn,
    )
    print('  update_analysis submitted (all 3 patches including TopBottomFilter)')
    top_bottom_accepted = True
except Exception as primary_err:
    print(f'  Primary attempt failed: {primary_err}')
    print()
    print('  update_analysis rejected — falling back to patches 2+3 only.')
    print('  Fetching fresh definition for fallback…')

    # Re-fetch clean definition and apply only patches 2 and 3
    defn2 = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']

    # Patch 2 again on fresh copy
    for fg in defn2.get('FilterGroups', []):
        if fg['FilterGroupId'] in ('fg-s1-date', 'fg-s2-date'):
            for s in fg['ScopeConfiguration']['SelectedSheets']['SheetVisualScopingConfigurations']:
                s['Scope'] = 'ALL_VISUALS'
                s.pop('VisualIds', None)
            print(f"  (Fallback) Patched scope: {fg['FilterGroupId']} → ALL_VISUALS")

    # Patch 3 again on fresh copy
    for sheet in defn2.get('Sheets', []):
        if sheet['SheetId'] not in DROPDOWN_SHEET_IDS:
            continue
        for fc in sheet.get('FilterControls', []):
            if 'Dropdown' not in fc:
                continue
            dd = fc['Dropdown']
            dd['Type'] = 'SINGLE_SELECT'
            dd['DisplayOptions'] = {
                'SelectAllOptions': {'Visibility': 'VISIBLE'},
                'TitleOptions':     {'Visibility': 'VISIBLE', 'FontConfiguration': {'FontSize': {'Relative': 'MEDIUM'}}},
            }
            dd.pop('SelectableValues', None)

    try:
        qs.update_analysis(
            AwsAccountId=ACCOUNT,
            AnalysisId=ANALYSIS_ID,
            Name=name,
            ThemeArn=THEME_ARN,
            Definition=defn2,
        )
        print('  Fallback (patches 2+3 only) submitted successfully')
    except Exception as fallback_err:
        print(f'  FATAL: Fallback also failed: {fallback_err}')
        raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════════════════
# Wait for analysis update to complete
# ═══════════════════════════════════════════════════════════════════════════
print()
print('Waiting for analysis update to complete…')
for attempt in range(24):
    time.sleep(5)
    status_resp = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
    status = status_resp['Analysis']['Status']
    print(f'  [{attempt+1:02d}] Analysis status: {status}')
    if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
        print('  ✓ Analysis update succeeded')
        break
    if 'FAILED' in status:
        errors = qs.describe_analysis_definition(
            AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID
        ).get('Errors', [])
        print(f'  ✗ Analysis update FAILED. Errors:')
        for e in errors:
            print(f'      {e}')
        raise SystemExit(1)
else:
    print('  Timed out waiting for analysis update — check console.')
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════════════════
# Republish dashboard
# ═══════════════════════════════════════════════════════════════════════════
print()
print('──────────────────────────────────────────────')
print('Republishing dashboard…')
print('──────────────────────────────────────────────')

# Use the updated analysis definition for the dashboard
defn_final = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']

pub_resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)',
    Definition=defn_final,
    ThemeArn=THEME_ARN,
)
new_version = int(pub_resp['VersionArn'].split('/')[-1])
print(f'  Dashboard update submitted — awaiting version {new_version}…')

for attempt in range(30):
    time.sleep(4)
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)
    match = next(
        (v for v in versions.get('DashboardVersionSummaryList', []) if v['VersionNumber'] == new_version),
        None,
    )
    if not match:
        print(f'  [{attempt+1:02d}] Version {new_version} not yet listed…')
        continue
    vstatus = match['Status']
    print(f'  [{attempt+1:02d}] Dashboard v{new_version} status: {vstatus}')
    if vstatus == 'CREATION_SUCCESSFUL':
        qs.update_dashboard_published_version(
            AwsAccountId=ACCOUNT,
            DashboardId=DASHBOARD_ID,
            VersionNumber=new_version,
        )
        print(f'  ✓ Dashboard v{new_version} published successfully')
        break
    if 'FAILED' in vstatus:
        print(f'  ✗ Dashboard version FAILED: {match}')
        raise SystemExit(1)
else:
    print('  Timed out waiting for dashboard version — check console.')
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
print()
print('══════════════════════════════════════════════')
print('PATCHES APPLIED:')
print(f'  Patch 1 (TopBottomFilter for KPI tiles) : {"ACCEPTED ✓" if top_bottom_accepted else "SKIPPED — TopBottomFilter unsupported, fallback applied"}')
print( '  Patch 2 (Date filter scope ALL_VISUALS)  : APPLIED ✓')
print( '  Patch 3 (Dropdown DisplayOptions)        : APPLIED ✓ (idempotent)')
print(f'  Dashboard version published              : v{new_version}')
print('══════════════════════════════════════════════')
