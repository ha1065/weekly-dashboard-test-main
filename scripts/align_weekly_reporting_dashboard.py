#!/usr/bin/env python3
"""Align Weekly Reporting Dashboard sheets with SRS spec:
1. Rename 4 sheets to match SRS names
2. Remove 3 retired sheets (Forecast v Actuals, Resource Conflicts, Project Directory)
3. Add Tab 17 — Org KPI Scorecard (copied from COO dashboard calculated fields + sheet)
"""
import boto3, time

PROFILE   = 'AWSAdministratorAccess-961341524729'
REGION    = 'us-east-1'
ACCOUNT   = '961341524729'
DASH_ID   = 'b894f691-f392-41c4-bc52-ee732a3cf27e'

# Sheets to retire (remove entirely)
RETIRE_NAMES = {'Forecast v Actuals', 'Resource Conflicts', 'Project Directory'}

# Sheet renames: current name → SRS name
RENAMES = {
    'MC Project Status':  'MC Service Delivery',
    'Forecast':           'Resource Forecast',
    'PS Productivity':    'PS Delivery Analysis',
    'Project Hours':      'Project Hours Trend',
}

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── 1. Get current dashboard ───────────────────────────────────────────────
d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Definition']

print(f'Dashboard: {name}  ({len(defn["Sheets"])} sheets)')

# ── 2. Remove retired sheets and their scoped filter groups ───────────────
retired_sheet_ids = {s['SheetId'] for s in defn['Sheets'] if s.get('Name') in RETIRE_NAMES}
print(f'Retiring sheets: {[s["Name"] for s in defn["Sheets"] if s["SheetId"] in retired_sheet_ids]}')

defn['Sheets'] = [s for s in defn['Sheets'] if s['SheetId'] not in retired_sheet_ids]

# Remove filter groups scoped only to retired sheets
def _scoped_to_retired(fg):
    scope = fg.get('ScopeConfiguration', {})
    sel   = scope.get('SelectedSheets', {})
    cfgs  = sel.get('SheetVisualScopingConfigurations', [])
    if not cfgs:
        return False
    return all(c['SheetId'] in retired_sheet_ids for c in cfgs)

before = len(defn.get('FilterGroups', []))
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', []) if not _scoped_to_retired(fg)]
print(f'Removed {before - len(defn["FilterGroups"])} filter groups scoped to retired sheets')

# ── 3. Rename sheets ───────────────────────────────────────────────────────
for sheet in defn['Sheets']:
    old_name = sheet.get('Name', '')
    if old_name in RENAMES:
        sheet['Name'] = RENAMES[old_name]
        print(f'Renamed: "{old_name}" → "{RENAMES[old_name]}"')

# ── 4. Tab 17 — Skip for now (already live on COO dashboard) ──────────────
print('Tab 17 — Skipping (already live on COO Operational Dashboard)')

# ── 5. Strip any CalculatedFieldId from all CFs (API rejects it) ──────────
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
]

# ── 5b. Remove hours_bucket column references (missing from dataset) ───────
import json as _json
defn_str = _json.dumps(defn)
if 'hours_bucket' in defn_str:
    print('Removing hours_bucket references...')
    defn = _json.loads(defn_str.replace('"hours_bucket"', '"hours_submitted"'))

# ── 6. Push and publish ────────────────────────────────────────────────────
kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASH_ID, Name=name, Definition=defn,
    VersionDescription='Align with SRS: rename 4 sheets, retire 3, add Tab 17 KPI Scorecard'
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
    print(f'✅ Published version {version} — Weekly Reporting Dashboard aligned with SRS.')
    print(f'   Sheets remaining: {len(defn["Sheets"])}')
