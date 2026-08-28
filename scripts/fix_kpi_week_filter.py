#!/usr/bin/env python3
"""Fix Time & Utilization KPI visuals: add missing_time_count and other unfiltered
KPIs to the fg-kpi-s5 week filter group so they show the selected week's value."""
import boto3, time

PROFILE   = 'AWSAdministratorAccess-961341524729'
REGION    = 'us-east-1'
ACCOUNT   = '961341524729'
DASH_ID   = 'coo-operational-dashboard-prod'
SHEET_ID  = '73db83d0-0321-49b0-8098-a8f66c46ecc7'
FG_ID     = 'fg-kpi-s5'

# All KPI visuals on the Time & Utilization sheet that use kpi_weekly_snapshots
ALL_KPI_VISUAL_IDS = [
    '640b53c8-26f0-4faf-a65d-7744e7a0340f',  # billable_util_pct
    'c2ad2985-8d94-4674-bf27-3c76840cffda',  # time_compliance_pct
    '15a95ddc-1ed1-470e-9d71-a1c13ffa5438',  # missing_time_count ← was missing
    '81e0c586-99f6-41c7-8fab-97e1ded5dc17',  # presales_hours
    '583a3433-b397-4160-ba41-4a1a8cd43dcf',  # productive_nb_hours
    'e9505484-22a3-4575-936b-f10047f07882',  # nb_nonproductive_hours
]

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')
d         = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Dashboard']
name      = d['Name']
theme_arn = d['Version'].get('ThemeArn')
defn      = qs.describe_dashboard_definition(AwsAccountId=ACCOUNT, DashboardId=DASH_ID)['Definition']

# Update fg-kpi-s5 to include all KPI visuals
updated = False
for fg in defn.get('FilterGroups', []):
    if fg['FilterGroupId'] == FG_ID:
        scope = fg['ScopeConfiguration']['SelectedSheets']['SheetVisualScopingConfigurations']
        for cfg in scope:
            if cfg['SheetId'] == SHEET_ID:
                old_ids = set(cfg.get('VisualIds', []))
                cfg['VisualIds'] = ALL_KPI_VISUAL_IDS
                new_ids = set(ALL_KPI_VISUAL_IDS)
                added = new_ids - old_ids
                print(f'Added {len(added)} visuals to {FG_ID}: {added}')
                updated = True

if not updated:
    print(f'WARNING: {FG_ID} not found or scope not matched')

# Strip CalculatedFieldId
defn['CalculatedFields'] = [
    {k: v for k, v in cf.items() if k != 'CalculatedFieldId'}
    for cf in defn.get('CalculatedFields', [])
]

kwargs = dict(
    AwsAccountId=ACCOUNT, DashboardId=DASH_ID, Name=name, Definition=defn,
    VersionDescription='Fix No Time Submitted KPI: add to week filter group fg-kpi-s5'
)
if theme_arn:
    kwargs['ThemeArn'] = theme_arn

resp    = qs.update_dashboard(**kwargs)
version = int(resp['VersionArn'].split('/')[-1])
print(f'Version {version} created. Polling...')

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
else:
    qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASH_ID, VersionNumber=version)
    print(f'✅ Published version {version}')
