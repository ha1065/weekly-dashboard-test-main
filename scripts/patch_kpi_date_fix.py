"""
patch_kpi_date_fix.py
---------------------
Fixes KPI Tracking Dashboard showing no data due to an off-by-one error in
the TimeRangeFilter completed-weeks guard.

ROOT CAUSE:
  The fg-s*-complete TimeRangeFilter groups use:
    addDateTime(-7, 'WK', truncDate('WK', now()))
  QuickSight's truncDate('WK', ...) snaps to SUNDAY (US default week start).
  Today = Thursday Jul 9 → truncDate = Sunday Jul 5 → addDateTime(-7 days) = Sunday Jun 28.
  The filter then requires: week_start <= Jun 28 00:00:00 UTC.
  BUT the data uses Monday-based weeks, so the most recent row has week_start = 2026-06-29.
  Jun 29 > Jun 28 → every row FAILS the TimeRangeFilter → zero data on all sheets.

FIX:
  Remove fg-s1-complete, fg-s2-complete, fg-s3-complete.
  The RelativeDatesFilter presets (LAST 1 WEEK, LAST 1 MONTH, etc.) already
  reference only past periods. The current incomplete week cannot bleed in because
  none of the presets include "Today" or "This week".

DATE PICKER LIMIT:
  QuickSight does not support a hard API-enforced upper bound on RelativeDateTime
  controls. The presets ("Last week", "Last month", "Last quarter", "Last year")
  are all past-period references. The control title is updated to say
  "Reporting Period (completed weeks)" to communicate this expectation.
"""

import boto3
import time
import json

PROFILE = 'AWSAdministratorAccess-961341524729'
REGION = 'us-east-1'
ACCOUNT = '961341524729'
ANALYSIS_ID = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

print("=== Fetching analysis definition ===")
defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
name = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']
print(f"Analysis: {name}")
print(f"FilterGroups before: {len(defn.get('FilterGroups', []))}")

# ------------------------------------------------------------------
# Step 1: Remove the completed-weeks TimeRangeFilter groups
# These are off-by-one: truncDate('WK', ...) snaps to Sunday, but
# data week_start values are Mondays — causing a 1-day gap that
# excludes all rows.
# ------------------------------------------------------------------
COMPLETE_GROUP_IDS = {'fg-s1-complete', 'fg-s2-complete', 'fg-s3-complete'}

removed = []
kept = []
for fg in defn.get('FilterGroups', []):
    if fg['FilterGroupId'] in COMPLETE_GROUP_IDS:
        removed.append(fg['FilterGroupId'])
    else:
        kept.append(fg)

defn['FilterGroups'] = kept
print(f"\nRemoved FilterGroups ({len(removed)}): {removed}")
print(f"FilterGroups after: {len(defn['FilterGroups'])}")

# ------------------------------------------------------------------
# Step 2: Update RelativeDateTime control titles to clarify intent
# ------------------------------------------------------------------
controls_updated = 0
for sheet in defn.get('Sheets', []):
    sheet_id = sheet.get('SheetId', '')
    for fc in sheet.get('FilterControls', []):
        if 'RelativeDateTime' in fc:
            rd = fc['RelativeDateTime']
            current_title = rd.get('Title', '')
            if current_title in ('Reporting Period', 'Reporting Week', 'Date Range',
                                 'Week Range', 'Date Filter'):
                rd['Title'] = 'Reporting Period (completed weeks)'
                print(f"  Updated control title on {sheet_id}: '{current_title}' -> '{rd['Title']}'")
                controls_updated += 1

if controls_updated == 0:
    print("  No RelativeDateTime control titles matched known names (titles may already be correct)")

# ------------------------------------------------------------------
# Step 3: Log remaining RelativeDatesFilters for verification
# ------------------------------------------------------------------
print("\n=== Remaining RelativeDatesFilters (these drive the date picker) ===")
for fg in defn.get('FilterGroups', []):
    for f in fg.get('Filters', []):
        if 'RelativeDatesFilter' in f:
            rdf = f['RelativeDatesFilter']
            col = rdf.get('Column', {}).get('ColumnName', '?')
            ds = rdf.get('Column', {}).get('DataSetIdentifier', '?')
            print(f"  {fg['FilterGroupId']}: {rdf.get('RelativeDateType')} "
                  f"{rdf.get('RelativeDateValue')} {rdf.get('TimeGranularity')} "
                  f"col={col} ds={ds}")

# ------------------------------------------------------------------
# Step 4: Apply to analysis
# ------------------------------------------------------------------
print("\n=== Updating analysis ===")
try:
    resp = qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name=name,
        ThemeArn=THEME_ARN,
        Definition=defn
    )
    print(f"update_analysis status: {resp['Status']}")
except Exception as e:
    print(f"ERROR updating analysis: {e}")
    raise

print("\nWaiting for analysis update to complete...")
for i in range(24):
    time.sleep(5)
    status = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Status']
    print(f"  [{i+1}] Analysis status: {status}")
    if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
        print("  ✅ Analysis update successful")
        break
    if 'FAILED' in status:
        errors = qs.describe_analysis_definition(
            AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID
        ).get('Errors', [])
        print(f"  ❌ Analysis update FAILED: {json.dumps(errors, indent=2)}")
        raise RuntimeError(f"Analysis update failed: {errors}")
else:
    raise TimeoutError("Analysis update did not complete in 120s")

# ------------------------------------------------------------------
# Step 5: Republish dashboard
# ------------------------------------------------------------------
print("\n=== Republishing dashboard ===")
defn2 = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']

resp2 = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)',
    Definition=defn2,
    ThemeArn=THEME_ARN
)
new_ver = int(resp2['VersionArn'].split('/')[-1])
print(f"Dashboard update submitted — version {new_ver}")

print(f"\nWaiting for dashboard v{new_ver} to finish...")
for i in range(40):
    time.sleep(4)
    versions = qs.list_dashboard_versions(
        AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID
    )['DashboardVersionSummaryList']
    match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
    if not match:
        print(f"  [{i+1}] v{new_ver} not yet listed...")
        continue
    vstatus = match.get('Status', '')
    print(f"  [{i+1}] v{new_ver} status: {vstatus}")
    if vstatus == 'CREATION_SUCCESSFUL':
        qs.update_dashboard_published_version(
            AwsAccountId=ACCOUNT,
            DashboardId=DASHBOARD_ID,
            VersionNumber=new_ver
        )
        print(f"\n✅ Dashboard v{new_ver} published successfully")
        break
    if 'FAILED' in vstatus:
        errors = match.get('Errors', [])
        print(f"❌ Dashboard publish FAILED: {json.dumps(errors, indent=2)}")
        raise RuntimeError(f"Dashboard publish failed: {errors}")
else:
    raise TimeoutError("Dashboard publish did not complete in 160s")

print("\n=== DONE ===")
print(f"Analysis {ANALYSIS_ID}: updated (removed {len(removed)} TimeRangeFilter guard groups)")
print(f"Dashboard {DASHBOARD_ID}: v{new_ver} published")
print("\nUsers should now see data when the default 'Last 1 Week' filter is applied.")
print("The Jun 29 week_start row will be visible as it passes the RelativeDatesFilter.")
