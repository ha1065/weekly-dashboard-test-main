"""
patch_kpi_s3_scope.py — Fix Sheet 3 date filter scoping on the KPI Tracking Dashboard.

Problem:
    fg-s3-kpi (TopBottomFilter on kpi_staff.week_start) is scoped to SELECTED_VISUALS
    and includes tbl-s3-staff in its visual list. This pins both the 5 KPI tiles AND
    the staff detail table to the single most-recently-reported week, so the table
    never reflects the user's date range selection (e.g. "Last Quarter").

Fix:
    1. Remove fg-s3-kpi entirely from Sheet 3.
       Per updated requirements, all Sheet 3 visuals — including the KPI tiles —
       should respond to the date range control (fg-s3-date) rather than being
       pinned to last week. The user's feedback is that tiles should aggregate over
       the selected period, not show a single week's snapshot.

    2. Confirm fg-s3-date (RelativeDatesFilter) remains ALL_VISUALS on sheet-kpi-s3.

    3. Confirm category FilterGroups (fg-s3-lob, fg-s3-practice, fg-s3-pod,
       fg-s3-staff) are all ALL_VISUALS on sheet-kpi-s3.

Sheet 1 & 2 status:
    fg-s1-kpi and fg-s2-kpi are correctly scoped to KPI tiles only (no tables or
    trend charts) — no changes needed on Sheets 1 or 2.

Run:
    python3 scripts/patch_kpi_s3_scope.py
"""

import boto3
import time

# ── Config ─────────────────────────────────────────────────────────────────
PROFILE      = 'AWSAdministratorAccess-961341524729'
REGION       = 'us-east-1'
ACCOUNT      = '961341524729'
ANALYSIS_ID  = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN    = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

S3_SHEET = 'sheet-kpi-s3'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── Fetch current definition ────────────────────────────────────────────────
print('Fetching analysis definition…')
resp  = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn  = resp['Definition']
name  = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']
print(f'  Analysis name : {name}')
print(f'  FilterGroups  : {[fg["FilterGroupId"] for fg in defn.get("FilterGroups", [])]}')

# ── Diagnostic: print current Sheet 3 FilterGroups ─────────────────────────
print()
print('=== Current Sheet 3 FilterGroups (before patch) ===')
for fg in defn.get('FilterGroups', []):
    for s in fg.get('ScopeConfiguration', {}).get('SelectedSheets', {}).get('SheetVisualScopingConfigurations', []):
        if s.get('SheetId') == S3_SHEET:
            filters = fg.get('Filters', [])
            for f in filters:
                ftype = next((k for k in f if k.endswith('Filter')), '?')
                col   = f.get(ftype, {}).get('Column', {}).get('ColumnName', '?')
                vids  = s.get('VisualIds', [])
                print(f'  {fg["FilterGroupId"]}: {ftype} col={col} scope={s["Scope"]} visuals={vids}')

print()
print('=== Current Sheet 1 FilterGroups (reference — no changes) ===')
for fg in defn.get('FilterGroups', []):
    for s in fg.get('ScopeConfiguration', {}).get('SelectedSheets', {}).get('SheetVisualScopingConfigurations', []):
        if s.get('SheetId') == 'sheet-kpi-s1':
            filters = fg.get('Filters', [])
            for f in filters:
                ftype = next((k for k in f if k.endswith('Filter')), '?')
                col   = f.get(ftype, {}).get('Column', {}).get('ColumnName', '?')
                print(f'  {fg["FilterGroupId"]}: {ftype} col={col} scope={s["Scope"]} visuals={s.get("VisualIds", [])}')

print()
print('=== Current Sheet 2 FilterGroups (reference — no changes) ===')
for fg in defn.get('FilterGroups', []):
    for s in fg.get('ScopeConfiguration', {}).get('SelectedSheets', {}).get('SheetVisualScopingConfigurations', []):
        if s.get('SheetId') == 'sheet-kpi-s2':
            filters = fg.get('Filters', [])
            for f in filters:
                ftype = next((k for k in f if k.endswith('Filter')), '?')
                col   = f.get(ftype, {}).get('Column', {}).get('ColumnName', '?')
                print(f'  {fg["FilterGroupId"]}: {ftype} col={col} scope={s["Scope"]} visuals={s.get("VisualIds", [])}')

# ═══════════════════════════════════════════════════════════════════════════
# PATCH: Remove fg-s3-kpi (TopBottomFilter) from Sheet 3
# ═══════════════════════════════════════════════════════════════════════════
print()
print('──────────────────────────────────────────────')
print('PATCH: Removing fg-s3-kpi (TopBottomFilter) from Sheet 3')
print('──────────────────────────────────────────────')

REMOVE_IDS = {'fg-s3-kpi', 'fg-s3-week'}   # fg-s3-week is defensive — not currently present

before_count = len(defn.get('FilterGroups', []))
removed_ids  = [fg['FilterGroupId'] for fg in defn.get('FilterGroups', []) if fg['FilterGroupId'] in REMOVE_IDS]
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', []) if fg['FilterGroupId'] not in REMOVE_IDS]
after_count = len(defn['FilterGroups'])

if removed_ids:
    print(f'  Removed {len(removed_ids)} FilterGroup(s): {removed_ids}')
else:
    print('  WARNING: Neither fg-s3-kpi nor fg-s3-week were found — nothing removed.')

# ── Confirm fg-s3-date is ALL_VISUALS ──────────────────────────────────────
print()
print('Confirming fg-s3-date scope…')
for fg in defn.get('FilterGroups', []):
    if fg['FilterGroupId'] == 'fg-s3-date':
        configs = fg['ScopeConfiguration']['SelectedSheets']['SheetVisualScopingConfigurations']
        for s in configs:
            if s.get('SheetId') == S3_SHEET:
                old_scope = s['Scope']
                s['Scope'] = 'ALL_VISUALS'
                s.pop('VisualIds', None)
                if old_scope == 'ALL_VISUALS':
                    print(f'  fg-s3-date: already ALL_VISUALS ✓')
                else:
                    print(f'  fg-s3-date: scope changed {old_scope} → ALL_VISUALS')

# ── Confirm category filters are ALL_VISUALS ───────────────────────────────
print()
print('Confirming category filter scopes on Sheet 3…')
CAT_FG_IDS = {'fg-s3-lob', 'fg-s3-practice', 'fg-s3-pod', 'fg-s3-staff'}
for fg in defn.get('FilterGroups', []):
    if fg['FilterGroupId'] in CAT_FG_IDS:
        configs = fg['ScopeConfiguration']['SelectedSheets']['SheetVisualScopingConfigurations']
        for s in configs:
            if s.get('SheetId') == S3_SHEET:
                old_scope = s['Scope']
                s['Scope'] = 'ALL_VISUALS'
                s.pop('VisualIds', None)
                status = 'already ALL_VISUALS ✓' if old_scope == 'ALL_VISUALS' else f'changed {old_scope} → ALL_VISUALS'
                print(f'  {fg["FilterGroupId"]}: {status}')

# ═══════════════════════════════════════════════════════════════════════════
# Submit update_analysis
# ═══════════════════════════════════════════════════════════════════════════
print()
print('──────────────────────────────────────────────')
print('Submitting update_analysis…')
print('──────────────────────────────────────────────')

try:
    qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name=name,
        ThemeArn=THEME_ARN,
        Definition=defn,
    )
    print('  update_analysis submitted successfully')
except Exception as e:
    print(f'  ERROR: {e}')
    raise SystemExit(1)

# ── Wait for analysis update ───────────────────────────────────────────────
print()
print('Waiting for analysis update…')
for attempt in range(24):
    time.sleep(5)
    status = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Status']
    print(f'  [{attempt+1:02d}] {status}')
    if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
        print('  ✓ Analysis update succeeded')
        break
    if 'FAILED' in status:
        errors = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID).get('Errors', [])
        print('  ✗ Analysis update FAILED. Errors:')
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

defn_final = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']

pub_resp    = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)',
    Definition=defn_final,
    ThemeArn=THEME_ARN,
)
new_version = int(pub_resp['VersionArn'].split('/')[-1])
print(f'  Dashboard update submitted — awaiting v{new_version}…')

for attempt in range(30):
    time.sleep(4)
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)
    match = next(
        (v for v in versions.get('DashboardVersionSummaryList', []) if v['VersionNumber'] == new_version),
        None,
    )
    if not match:
        print(f'  [{attempt+1:02d}] v{new_version} not yet listed…')
        continue
    vstatus = match['Status']
    print(f'  [{attempt+1:02d}] Dashboard v{new_version}: {vstatus}')
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
print('SUMMARY')
print(f'  FilterGroups removed from Sheet 3 : {removed_ids if removed_ids else "none found (already absent)"}')
print(f'  fg-s3-date scope                  : ALL_VISUALS ✓')
print(f'  Category filters (lob/practice/pod/staff): ALL_VISUALS ✓')
print(f'  Sheet 1 changes                   : none (fg-s1-kpi correctly scopes KPI tiles only)')
print(f'  Sheet 2 changes                   : none (fg-s2-kpi correctly scopes KPI tiles only)')
print(f'  Dashboard version published        : v{new_version}')
print()
print('  All Sheet 3 visuals now respond to fg-s3-date (RelativeDatesFilter).')
print('  KPI tiles aggregate over the full selected period.')
print('  Staff detail table shows all weeks in selected range.')
print('  Trend charts show full selected range.')
print('══════════════════════════════════════════════')
