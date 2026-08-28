#!/usr/bin/env python3
"""
patch_kpi_cf.py
---------------
Add cell-level conditional formatting to the compliance_status column in the
Staff Detail table (tbl-s3-staff) on Sheet 3 (sheet-kpi-s3) of the KPI
Tracking Dashboard.

Color coding:
  Compliant     → green  #33A94F  (text #FFFFFF)
  Partial       → amber  #FF9B00  (text #27164F)
  Non-Compliant → red    #D74018  (text #FFFFFF)

Field discovery result:
  TableVisual:  tbl-s3-staff  (TableUnaggregatedFieldWells)
  FieldId:      tbl-s3-f9  (compliance_status column, kpi_staff dataset)
"""
import boto3
import time

ACCOUNT      = '961341524729'
ANALYSIS_ID  = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN    = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN  = '#33A94F'
AMBER  = '#FF9B00'
RED    = '#D74018'
WHITE  = '#FFFFFF'
DARK   = '#27164F'

# ── The compliance_status field in tbl-s3-staff ───────────────────────────────
COMPLIANCE_FIELD_ID = 'tbl-s3-f9'


def cell_cf(field_id, expression, bg, text=WHITE):
    """Build a single cell-level CF rule (background + text color)."""
    return {
        'Cell': {
            'FieldId': field_id,
            'TextFormat': {
                'BackgroundColor': {
                    'Solid': {
                        'Expression': expression,
                        'Color': bg,
                    }
                },
                'TextColor': {
                    'Solid': {
                        'Expression': expression,
                        'Color': text,
                    }
                },
            },
        }
    }


# ── Fetch current analysis definition ────────────────────────────────────────
qs = boto3.Session(
    profile_name='AWSAdministratorAccess-961341524729',
    region_name='us-east-1',
).client('quicksight')

print('Fetching analysis definition...')
resp = qs.describe_analysis_definition(
    AwsAccountId=ACCOUNT,
    AnalysisId=ANALYSIS_ID,
)
defn = resp['Definition']
print(f'  ResourceStatus: {resp["ResourceStatus"]}')

# ── Locate tbl-s3-staff on sheet-kpi-s3 ─────────────────────────────────────
s3_sheet = next(
    s for s in defn['Sheets'] if s['SheetId'] == 'sheet-kpi-s3'
)
print(f'  Sheet found: {s3_sheet["SheetId"]} — {s3_sheet.get("Name", "")}')

tbl_visual = None
for visual in s3_sheet['Visuals']:
    tbl = visual.get('TableVisual', {})
    if tbl.get('VisualId') == 'tbl-s3-staff':
        tbl_visual = tbl
        break

if tbl_visual is None:
    raise RuntimeError('Could not find TableVisual tbl-s3-staff on sheet-kpi-s3')

print(f'  TableVisual found: {tbl_visual["VisualId"]}')

# Confirm the compliance_status field is present
wells = (
    tbl_visual.get('ChartConfiguration', {})
    .get('FieldWells', {})
    .get('TableUnaggregatedFieldWells', {})
    .get('Values', [])
)
cf_field = next(
    (f for f in wells if f.get('FieldId') == COMPLIANCE_FIELD_ID), None
)
if cf_field:
    col = cf_field.get('Column', {})
    print(f'  Confirmed: FieldId={COMPLIANCE_FIELD_ID}  column={col.get("ColumnName")}')
else:
    raise RuntimeError(
        f'FieldId {COMPLIANCE_FIELD_ID} not found in tbl-s3-staff wells'
    )

# ── Patch: add/replace ConditionalFormatting ─────────────────────────────────
tbl_visual['ConditionalFormatting'] = {
    'ConditionalFormattingOptions': [
        # Compliant → green background, white text
        cell_cf(
            COMPLIANCE_FIELD_ID,
            "{compliance_status} = 'Compliant'",
            GREEN,
            WHITE,
        ),
        # Partial → amber background, dark text
        cell_cf(
            COMPLIANCE_FIELD_ID,
            "{compliance_status} = 'Partial'",
            AMBER,
            DARK,
        ),
        # Non-Compliant → red background, white text
        cell_cf(
            COMPLIANCE_FIELD_ID,
            "{compliance_status} = 'Non-Compliant'",
            RED,
            WHITE,
        ),
    ]
}
print(
    f'  CF rules written: '
    f'{len(tbl_visual["ConditionalFormatting"]["ConditionalFormattingOptions"])} rules '
    f'(Compliant/Partial/Non-Compliant)'
)

# ── Update analysis ───────────────────────────────────────────────────────────
print('\nCalling update_analysis...')
ua_resp = qs.update_analysis(
    AwsAccountId=ACCOUNT,
    AnalysisId=ANALYSIS_ID,
    Name='KPI Tracking Analysis (prod)',
    ThemeArn=THEME_ARN,
    Definition=defn,
)
print(f'  update_analysis status: {ua_resp["Status"]}')

# Wait for UPDATE_SUCCESSFUL
print('  Waiting for analysis update to complete...')
for attempt in range(40):
    status_resp = qs.describe_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
    )
    status = status_resp['Analysis']['Status']
    if status == 'UPDATE_SUCCESSFUL':
        print(f'  ✓ Analysis status: {status}')
        break
    if 'FAILED' in status or 'ERROR' in status:
        print(f'  ✗ Analysis update failed: {status}')
        exit(1)
    print(f'    [{attempt + 1}] {status} — waiting...')
    time.sleep(3)
else:
    print('  ✗ Timed out waiting for analysis update')
    exit(1)

# ── Republish dashboard ───────────────────────────────────────────────────────
print('\nRepublishing dashboard...')
# Re-fetch definition to get the latest (post-update) version
updated_defn = qs.describe_analysis_definition(
    AwsAccountId=ACCOUNT,
    AnalysisId=ANALYSIS_ID,
)['Definition']

dash_resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)',
    Definition=updated_defn,
    ThemeArn=THEME_ARN,
)
new_ver = int(dash_resp['VersionArn'].split('/')[-1])
print(f'  Dashboard version {new_ver} creating...')

for attempt in range(40):
    versions = qs.list_dashboard_versions(
        AwsAccountId=ACCOUNT,
        DashboardId=DASHBOARD_ID,
    )
    match = next(
        (v for v in versions['DashboardVersionSummaryList']
         if v['VersionNumber'] == new_ver),
        None,
    )
    status = match['Status'] if match else 'PENDING'
    if status == 'CREATION_SUCCESSFUL':
        print(f'  ✓ Dashboard version {new_ver} created successfully')
        break
    if 'FAILED' in status or 'ERROR' in status:
        print(f'  ✗ Dashboard creation failed: {status}')
        exit(1)
    print(f'    [{attempt + 1}] {status} — waiting...')
    time.sleep(3)
else:
    print('  ✗ Timed out waiting for dashboard creation')
    exit(1)

# Publish the new version as the live version
qs.update_dashboard_published_version(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    VersionNumber=new_ver,
)
print(f'\n✅ Dashboard published at version {new_ver}')
print(f'   FieldId used: {COMPLIANCE_FIELD_ID} (compliance_status)')
print('   Rules: Compliant=#33A94F | Partial=#FF9B00 | Non-Compliant=#D74018')
