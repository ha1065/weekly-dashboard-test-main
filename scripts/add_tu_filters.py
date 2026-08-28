#!/usr/bin/env python3
"""Add POD and Person filter controls to the Time & Utilization sheet
in the COO Operational Analysis dashboard."""

import boto3, json, copy, time

PROFILE    = 'AWSAdministratorAccess-961341524729'
REGION     = 'us-east-1'
ACCOUNT    = '961341524729'
THEME_ARN  = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── 1. Find the COO dashboard ──────────────────────────────────────────────
dashboards = qs.list_dashboards(AwsAccountId=ACCOUNT)['DashboardSummaryList']
coo = next((d for d in dashboards if 'coo' in d['Name'].lower() or 'operational' in d['Name'].lower()), None)
if not coo:
    print('Available dashboards:')
    for d in dashboards:
        print(f"  {d['DashboardId']}  {d['Name']}")
    raise SystemExit('Could not find COO dashboard — check the name above and set DASHBOARD_ID manually.')

DASHBOARD_ID = coo['DashboardId']
print(f'Dashboard: {coo["Name"]} ({DASHBOARD_ID})')

# ── 2. Get current definition ──────────────────────────────────────────────
defn = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Definition']

# Find the time-util sheet
print('Sheets found:')
for s in defn['Sheets']:
    print(f"  {s['SheetId']}  name={s.get('Name','')}  title={s.get('Title','')}")

sheet = next((s for s in defn['Sheets'] if 'time' in s.get('Name','').lower() or 'util' in s.get('Name','').lower() or 'time' in s.get('Title','').lower() or 'util' in s.get('Title','').lower()), None)
if not sheet:
    raise SystemExit('Could not match time-util sheet by name/title. Check output above and set SHEET_ID manually.')

SHEET_ID = sheet['SheetId']
print(f'Sheet: {SHEET_ID}')
print(f'Visuals: {[v.get("BarChartVisual",v.get("LineChartVisual",v.get("TableVisual",v.get("KPIVisual",{})))).get("VisualId","?") for v in sheet.get("Visuals",[])]}')

# Find dataset identifier used by the sheet visuals — search JSON for DataSetIdentifier
import re
sheet_json = json.dumps(sheet)
match = re.search(r'"DataSetIdentifier":\s*"([^"]+)"', sheet_json)
dataset_id = match.group(1) if match else None
print(f'Dataset identifier: {dataset_id}')

# Find available columns in this dataset
ds_identifier = None
for ds_map in defn.get('DataSetIdentifierDeclarations', []):
    if ds_map.get('Identifier') == dataset_id:
        ds_identifier = ds_map['DataSetArn'].split('/')[-1]
        break

if ds_identifier:
    ds_defn = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId=ds_identifier)['DataSet']
    cols = [c['Name'] for c in ds_defn.get('OutputColumns', [])]
    print(f'Columns: {cols}')
    pod_col   = next((c for c in cols if 'pod' in c.lower()), None)
    user_col  = next((c for c in cols if 'user_name' in c.lower() or c == 'name'), None)
    print(f'POD column: {pod_col}  |  User column: {user_col}')
else:
    pod_col  = 'pod_assignment'
    user_col = 'user_name'
    print(f'Using defaults: pod_col={pod_col}, user_col={user_col}')

if not pod_col or not user_col:
    raise SystemExit(f'Required columns not found. Available: {cols}')

# ── 3. Build new filter groups ─────────────────────────────────────────────
existing_fg_ids = {fg['FilterGroupId'] for fg in defn.get('FilterGroups', [])}

pod_filter_id  = 'fg-tu-pod'
user_filter_id = 'fg-tu-person'

# Remove old versions if already applied
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', [])
                        if fg['FilterGroupId'] not in (pod_filter_id, user_filter_id)]

scope = {
    'SelectedSheets': {
        'SheetVisualScopingConfigurations': [{
            'SheetId': SHEET_ID,
            'Scope': 'ALL_VISUALS'
        }]
    }
}

defn['FilterGroups'].append({
    'FilterGroupId': pod_filter_id,
    'Filters': [{
        'CategoryFilter': {
            'FilterId': f'{pod_filter_id}-f',
            'Column': {'DataSetIdentifier': dataset_id, 'ColumnName': pod_col},
            'Configuration': {
                'FilterListConfiguration': {
                    'MatchOperator': 'CONTAINS',
                    'SelectAllOptions': 'FILTER_ALL_VALUES'
                }
            }
        }
    }],
    'ScopeConfiguration': scope,
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})

defn['FilterGroups'].append({
    'FilterGroupId': user_filter_id,
    'Filters': [{
        'CategoryFilter': {
            'FilterId': f'{user_filter_id}-f',
            'Column': {'DataSetIdentifier': dataset_id, 'ColumnName': user_col},
            'Configuration': {
                'FilterListConfiguration': {
                    'MatchOperator': 'EQUALS',
                    'SelectAllOptions': 'FILTER_ALL_VALUES'
                }
            }
        }
    }],
    'ScopeConfiguration': scope,
    'Status': 'ENABLED',
    'CrossDataset': 'SINGLE_DATASET'
})

# ── 4. Add filter controls to the sheet ───────────────────────────────────
sheet_idx = next(i for i, s in enumerate(defn['Sheets']) if s['SheetId'] == SHEET_ID)
existing_ctrl_ids = {c.get('FilterControl',{}).get('FilterControlId','')
                     for c in defn['Sheets'][sheet_idx].get('FilterControls', [])}

for ctrl_id, filter_id, title in [
    ('ctrl-tu-pod',    f'{pod_filter_id}-f',  'POD'),
    ('ctrl-tu-person', f'{user_filter_id}-f', 'Person'),
]:
    if ctrl_id not in existing_ctrl_ids:
        defn['Sheets'][sheet_idx].setdefault('FilterControls', []).append({
            'Dropdown': {
                'FilterControlId': ctrl_id,
                'Title': title,
                'SourceFilterId': filter_id,
                'SelectableValues': {},
                'Type': 'MULTI_SELECT'
            }
        })
        print(f'Added control: {title}')

# ── 5. Push update ─────────────────────────────────────────────────────────
resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=coo['Name'],
    Definition=defn,
    ThemeArn=THEME_ARN,
    VersionDescription='Add POD and Person filters to Time & Utilization sheet'
)
version = resp['VersionArn'].split('/')[-1]
print(f'\nUpdate submitted — version {version}. Waiting for it to be ready...')
time.sleep(5)

# ── 6. Publish ─────────────────────────────────────────────────────────────
qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=int(version))
print(f'✅ Published version {version}. Refresh the dashboard to see the POD and Person filters.')
