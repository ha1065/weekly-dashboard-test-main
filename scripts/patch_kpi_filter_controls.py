"""
patch_kpi_filter_controls.py
Apply filter control consistency fixes to the KPI Tracking Dashboard analysis.

Changes:
  1. Add pWeekStart DateTimeParameterDeclaration
  2. Replace FilterControl.RelativeDateTime with ParameterControl.DateTimePicker
     on all 3 sheets (sheet-kpi-s1, sheet-kpi-s2, sheet-kpi-s3)
  3. Replace RelativeDatesFilter with TimeEqualityFilter for fg-s*-date FilterGroups
  4. Rename 'POD' -> 'POD Assignment' and 'Individual' -> 'Staff Member' on sheet-kpi-s3
Then republish the dashboard.
"""

import boto3
import time
import json

qs = boto3.Session(
    profile_name='AWSAdministratorAccess-961341524729',
    region_name='us-east-1'
).client('quicksight')

ACCOUNT = '961341524729'
ANALYSIS_ID = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

# ── Fetch current definition ──────────────────────────────────────────────────
print('Fetching analysis definition...')
defn = qs.describe_analysis_definition(
    AwsAccountId=ACCOUNT,
    AnalysisId=ANALYSIS_ID
)['Definition']
name = qs.describe_analysis(
    AwsAccountId=ACCOUNT,
    AnalysisId=ANALYSIS_ID
)['Analysis']['Name']
print(f'  Analysis name: {name}')

# Diagnostic: show current parameters
print('\n[Diagnostic] Current ParameterDeclarations:')
for p in defn.get('ParameterDeclarations', []):
    ptype = list(p.keys())[0]
    pname = p[ptype].get('Name', '?')
    print(f'  {ptype}: {pname}')

# Diagnostic: show FilterGroups that may be date-related
print('\n[Diagnostic] FilterGroups:')
for fg in defn.get('FilterGroups', []):
    fgid = fg.get('FilterGroupId', '?')
    filters = fg.get('Filters', [])
    ftypes = [list(f.keys())[0] for f in filters]
    print(f'  {fgid}: {ftypes}')

# Diagnostic: show sheet filter controls
print('\n[Diagnostic] Sheet FilterControls:')
for sheet in defn.get('Sheets', []):
    sid = sheet.get('SheetId', '?')
    fcs = sheet.get('FilterControls', [])
    pcs = sheet.get('ParameterControls', [])
    print(f'  Sheet {sid}:')
    for fc in fcs:
        fc_type = list(fc.keys())[0]
        inner = fc[fc_type]
        title = inner.get('Title', '?')
        print(f'    FilterControl.{fc_type}: "{title}"')
    for pc in pcs:
        pc_type = list(pc.keys())[0]
        inner = pc[pc_type]
        title = inner.get('Title', '?')
        print(f'    ParameterControl.{pc_type}: "{title}"')


# ── Change 1: Add pWeekStart DateTimeParameterDeclaration ─────────────────────
print('\n[Change 1] Adding pWeekStart parameter...')
params = defn.get('ParameterDeclarations', [])
existing_names = []
for p in params:
    ptype = list(p.keys())[0]
    existing_names.append(p[ptype].get('Name', ''))

if 'pWeekStart' not in existing_names:
    params.append({
        'DateTimeParameterDeclaration': {
            'Name': 'pWeekStart',
            'DefaultValues': {
                'StaticValues': ['2026-07-07T00:00:00Z']
            },
            'TimeGranularity': 'DAY'
        }
    })
    print('  ✓ Added pWeekStart parameter')
else:
    print('  ✓ pWeekStart already exists — skipping')
defn['ParameterDeclarations'] = params


# ── Change 3: Replace RelativeDatesFilter with TimeEqualityFilter ─────────────
# Must be done before Change 2 since we reference the same FilterGroupIds
print('\n[Change 3] Replacing RelativeDatesFilter → TimeEqualityFilter...')
date_filter_map = {
    'fg-s1-date': ('kpi_snapshots', 'week_start_date'),
    'fg-s2-date': ('kpi_practice', 'week_start'),
    'fg-s3-date': ('kpi_staff', 'week_start'),
}

for fg in defn.get('FilterGroups', []):
    fgid = fg.get('FilterGroupId', '')
    if fgid not in date_filter_map:
        continue
    dataset, column = date_filter_map[fgid]
    current_filters = fg.get('Filters', [])
    current_types = [list(f.keys())[0] for f in current_filters]

    # Replace regardless of current type — idempotent
    fg['Filters'] = [{
        'TimeEqualityFilter': {
            'FilterId': fgid,
            'Column': {
                'DataSetIdentifier': dataset,
                'ColumnName': column
            },
            'ParameterName': 'pWeekStart',
            'TimeGranularity': 'DAY'
        }
    }]
    print(f'  ✓ {fgid}: {current_types} → TimeEqualityFilter (dataset={dataset}, column={column})')


# ── Changes 2 + 4: Update sheet controls ──────────────────────────────────────
print('\n[Changes 2+4] Updating sheet controls...')
sheet_map = {
    'sheet-kpi-s1': 's1',
    'sheet-kpi-s2': 's2',
    'sheet-kpi-s3': 's3',
}

for sheet in defn.get('Sheets', []):
    sid = sheet.get('SheetId', '')
    if sid not in sheet_map:
        continue
    suffix = sheet_map[sid]

    # Change 2a: Remove RelativeDateTime FilterControls
    old_fcs = sheet.get('FilterControls', [])
    new_fcs = []
    removed = []
    for fc in old_fcs:
        if 'RelativeDateTime' in fc:
            removed.append(fc)
        else:
            new_fcs.append(fc)

    sheet['FilterControls'] = new_fcs
    if removed:
        print(f'  ✓ {sid}: Removed {len(removed)} RelativeDateTime FilterControl(s)')
    else:
        print(f'  ~ {sid}: No RelativeDateTime controls found (may already be removed)')

    # Change 2b: Add DateTimePicker to ParameterControls (avoid duplicates)
    pcs = sheet.get('ParameterControls', [])
    existing_pc_ids = []
    for pc in pcs:
        pc_type = list(pc.keys())[0]
        existing_pc_ids.append(pc[pc_type].get('ParameterControlId', ''))

    ctrl_id = f'ctrl-week-{suffix}'
    if ctrl_id not in existing_pc_ids:
        new_pc = {
            'DateTimePicker': {
                'ParameterControlId': ctrl_id,
                'Title': 'Reporting Week',
                'SourceParameterName': 'pWeekStart',
                'DisplayOptions': {
                    'TitleOptions': {
                        'Visibility': 'VISIBLE',
                        'FontConfiguration': {
                            'FontSize': {'Relative': 'MEDIUM'}
                        }
                    },
                    'DateTimeFormat': 'MM/DD/YYYY'
                }
            }
        }
        pcs.insert(0, new_pc)  # insert at front so it appears first in the filter bar
        sheet['ParameterControls'] = pcs
        print(f'  ✓ {sid}: Added DateTimePicker ctrl-week-{suffix} "Reporting Week"')
    else:
        print(f'  ~ {sid}: DateTimePicker {ctrl_id} already exists — skipping')

    # Change 2c: Remove the old ctrl-s{N}-date element from the GridLayout.
    # ParameterControl (DateTimePicker) renders in the sheet's control bar automatically —
    # it does NOT need a GridLayout element. The COO dashboard confirms this pattern:
    # all its ParameterControl IDs are absent from layout Elements.
    old_ctrl_id = f'ctrl-{suffix}-date'
    for layout in sheet.get('Layouts', []):
        config = layout.get('Configuration', {})
        for layout_type, layout_body in config.items():
            before = len(layout_body.get('Elements', []))
            layout_body['Elements'] = [
                el for el in layout_body.get('Elements', [])
                if el.get('ElementId') != old_ctrl_id
            ]
            after = len(layout_body.get('Elements', []))
            if before != after:
                print(f'  ✓ {sid}: Removed layout element {old_ctrl_id} (ParameterControl needs no grid placement)')

    # Change 4: Rename dropdown labels on sheet-kpi-s3 only
    if sid == 'sheet-kpi-s3':
        for fc in sheet.get('FilterControls', []):
            if 'Dropdown' in fc:
                d = fc['Dropdown']
                if d.get('Title') == 'POD':
                    d['Title'] = 'POD Assignment'
                    print(f'  ✓ {sid}: Renamed dropdown "POD" → "POD Assignment"')
                elif d.get('Title') == 'Individual':
                    d['Title'] = 'Staff Member'
                    print(f'  ✓ {sid}: Renamed dropdown "Individual" → "Staff Member"')


# ── Submit update_analysis ─────────────────────────────────────────────────────
print('\n[Submitting] update_analysis...')
try:
    resp = qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name=name,
        ThemeArn=THEME_ARN,
        Definition=defn
    )
    print(f'  update_analysis submitted. RequestId={resp.get("RequestId", "?")}')
except Exception as e:
    print(f'\nERROR during update_analysis:\n  {e}')
    # Dump errors from definition if available
    try:
        err_details = qs.describe_analysis_definition(
            AwsAccountId=ACCOUNT,
            AnalysisId=ANALYSIS_ID
        ).get('Errors', [])
        if err_details:
            print('  Analysis errors:')
            for err in err_details:
                print(f'    {err}')
    except Exception:
        pass
    raise


# ── Wait for analysis update ───────────────────────────────────────────────────
print('\nWaiting for analysis update...')
for i in range(24):
    time.sleep(5)
    resp = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
    status = resp['Analysis']['Status']
    print(f'  [{i*5}s] Analysis: {status}')
    if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
        print('  ✓ Analysis update successful')
        break
    if 'FAILED' in status or 'ERROR' in status:
        err_details = qs.describe_analysis_definition(
            AwsAccountId=ACCOUNT,
            AnalysisId=ANALYSIS_ID
        ).get('Errors', [])
        print(f'\nAnalysis update FAILED with status: {status}')
        print('Errors:')
        for err in err_details:
            print(f'  {json.dumps(err, indent=2, default=str)}')
        raise RuntimeError(f'Analysis update failed: {status}')
else:
    print('  WARNING: Timed out waiting for analysis update — proceeding anyway')


# ── Republish dashboard ────────────────────────────────────────────────────────
print('\n[Republishing] Fetching updated definition for dashboard...')
defn2 = qs.describe_analysis_definition(
    AwsAccountId=ACCOUNT,
    AnalysisId=ANALYSIS_ID
)['Definition']

print('Calling update_dashboard...')
try:
    dash_resp = qs.update_dashboard(
        AwsAccountId=ACCOUNT,
        DashboardId=DASHBOARD_ID,
        Name='KPI Tracking Dashboard (prod)',
        Definition=defn2,
        ThemeArn=THEME_ARN
    )
    new_ver = int(dash_resp['VersionArn'].split('/')[-1])
    print(f'  Dashboard update submitted. Creating version {new_ver}...')
except Exception as e:
    print(f'\nERROR during update_dashboard:\n  {e}')
    raise

# Wait for new version to be created
print(f'Waiting for dashboard version {new_ver}...')
published = False
for i in range(30):
    time.sleep(4)
    versions = qs.list_dashboard_versions(
        AwsAccountId=ACCOUNT,
        DashboardId=DASHBOARD_ID
    )['DashboardVersionSummaryList']
    match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
    if match:
        vstat = match.get('Status', '?')
        print(f'  [{i*4}s] Version {new_ver}: {vstat}')
        if vstat == 'CREATION_SUCCESSFUL':
            print('  ✓ Version created successfully')
            # Publish
            qs.update_dashboard_published_version(
                AwsAccountId=ACCOUNT,
                DashboardId=DASHBOARD_ID,
                VersionNumber=new_ver
            )
            print(f'  ✓ Published dashboard version {new_ver}')
            published = True
            break
        elif 'FAILED' in vstat or 'ERROR' in vstat:
            print(f'\nDashboard version creation FAILED: {vstat}')
            print('Version details:')
            print(json.dumps(match, indent=2, default=str))
            raise RuntimeError(f'Dashboard version {new_ver} failed: {vstat}')
    else:
        print(f'  [{i*4}s] Version {new_ver} not yet visible...')

if not published:
    print(f'\nWARNING: Timed out waiting for dashboard version {new_ver}')


# ── Summary ────────────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('PATCH COMPLETE')
print('='*60)
print(f'Analysis:  {ANALYSIS_ID}')
print(f'Dashboard: {DASHBOARD_ID}')
print(f'Published: v{new_ver}' if published else f'Version {new_ver} (status unclear)')
print()
print('Changes applied:')
print('  [1] pWeekStart DateTimeParameterDeclaration added')
print('  [2] FilterControl.RelativeDateTime replaced with ParameterControl.DateTimePicker')
print('      on sheet-kpi-s1, sheet-kpi-s2, sheet-kpi-s3')
print('  [3] RelativeDatesFilter replaced with TimeEqualityFilter')
print('      on fg-s1-date, fg-s2-date, fg-s3-date')
print('  [4] Renamed "POD" → "POD Assignment" on sheet-kpi-s3')
print('  [4] Renamed "Individual" → "Staff Member" on sheet-kpi-s3')
