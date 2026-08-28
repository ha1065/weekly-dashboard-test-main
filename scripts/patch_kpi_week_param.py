#!/usr/bin/env python3
"""
Patch script: fix pWeekStart default in kpi-tracking-analysis-prod.

Bug 1: Default was 2026-06-29 (Sunday) — data has only Mondays, so no rows matched.
Bug 2: Default was stale — latest data is week of 2026-07-07.

Fix: Try RollingDate (truncDate('WEEK', now())) for dynamic current-week default.
     Fall back to StaticValues ['2026-07-07T00:00:00Z'] if RollingDate is rejected.
"""

import boto3
import json
import time

PROFILE        = 'AWSAdministratorAccess-961341524729'
REGION         = 'us-east-1'
ACCOUNT        = '961341524729'
ANALYSIS_ID    = 'kpi-tracking-analysis-prod'
DASHBOARD_ID   = 'kpi-tracking-dashboard-prod'
DASHBOARD_NAME = 'KPI Tracking Dashboard (prod)'
THEME_ARN      = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

# Static fallback — Monday 2026-07-07 (week of July 7)
STATIC_FALLBACK = '2026-07-07T00:00:00Z'

# Dataset identifier used for RollingDate expression context
DATASET_IDENTIFIER = 'kpi_practice'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')


def fetch_definition():
    defn = qs.describe_analysis_definition(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
    )['Definition']
    name = qs.describe_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
    )['Analysis']['Name']
    return defn, name


def patch_param_rolling(defn):
    """Patch pWeekStart to use RollingDate (dynamic current-week Monday)."""
    patched = False
    for p in defn.get('ParameterDeclarations', []):
        if 'DateTimeParameterDeclaration' not in p:
            continue
        pd = p['DateTimeParameterDeclaration']
        if pd['Name'] != 'pWeekStart':
            continue
        print(f"  Before: {json.dumps(pd.get('DefaultValues', {}))}")
        pd['DefaultValues'] = {
            'RollingDate': {
                'Expression': "truncDate('WEEK', now())",
                'DataSetIdentifier': DATASET_IDENTIFIER,
            }
        }
        print(f"  After (RollingDate): {json.dumps(pd.get('DefaultValues', {}))}")
        patched = True
        break
    if not patched:
        raise ValueError("pWeekStart DateTimeParameterDeclaration not found in definition")
    return defn


def patch_param_static(defn):
    """Patch pWeekStart to use StaticValues fallback."""
    for p in defn.get('ParameterDeclarations', []):
        if 'DateTimeParameterDeclaration' not in p:
            continue
        pd = p['DateTimeParameterDeclaration']
        if pd['Name'] != 'pWeekStart':
            continue
        pd['DefaultValues'] = {
            'StaticValues': [STATIC_FALLBACK]
        }
        print(f"  After (StaticValues): {json.dumps(pd.get('DefaultValues', {}))}")
        break
    return defn


def update_analysis(defn, name):
    qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name=name,
        ThemeArn=THEME_ARN,
        Definition=defn,
    )
    print('  update_analysis submitted — waiting...')


def wait_analysis():
    for attempt in range(24):  # up to 2 minutes
        time.sleep(5)
        resp = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
        status = resp['Analysis']['Status']
        print(f"  [{attempt+1:02d}] Analysis status: {status}")
        if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
            return True
        if 'FAILED' in status:
            errors = qs.describe_analysis_definition(
                AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
            ).get('Errors', [])
            print(f"  Errors: {json.dumps(errors, indent=2)}")
            return False
    print("  Timed out waiting for analysis update")
    return False


def republish_dashboard():
    defn2 = qs.describe_analysis_definition(
        AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    )['Definition']

    resp = qs.update_dashboard(
        AwsAccountId=ACCOUNT,
        DashboardId=DASHBOARD_ID,
        Name=DASHBOARD_NAME,
        Definition=defn2,
        ThemeArn=THEME_ARN,
    )
    new_ver = int(resp['VersionArn'].split('/')[-1])
    print(f"  Dashboard version {new_ver} creating...")

    for attempt in range(30):
        time.sleep(3)
        versions = qs.list_dashboard_versions(
            AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
        )['DashboardVersionSummaryList']
        match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
        if not match:
            continue
        print(f"  [{attempt+1:02d}] Dashboard status: {match['Status']}")
        if match['Status'] == 'CREATION_SUCCESSFUL':
            qs.update_dashboard_published_version(
                AwsAccountId=ACCOUNT,
                DashboardId=DASHBOARD_ID,
                VersionNumber=new_ver,
            )
            print(f"  ✅ Published dashboard version {new_ver}")
            return new_ver
        if 'FAILED' in match.get('Status', ''):
            print(f"  ❌ Dashboard creation failed: {match}")
            return None

    print("  Timed out waiting for dashboard")
    return None


def main():
    print("=" * 60)
    print("Patching pWeekStart default in kpi-tracking-analysis-prod")
    print("=" * 60)

    # ── Step 1: Fetch current definition ────────────────────────────
    print("\n[1/4] Fetching current analysis definition...")
    defn, name = fetch_definition()
    print(f"  Analysis name: {name}")
    print(f"  Sheets: {len(defn.get('Sheets', []))}")
    print(f"  Parameters: {len(defn.get('ParameterDeclarations', []))}")

    # ── Step 2: Patch with RollingDate ───────────────────────────────
    print("\n[2/4] Patching pWeekStart parameter...")
    used_rolling = False

    try:
        defn = patch_param_rolling(defn)
        update_analysis(defn, name)
        ok = wait_analysis()
        if ok:
            used_rolling = True
            print("  ✅ RollingDate default applied successfully")
        else:
            raise RuntimeError("Analysis update failed after RollingDate patch")
    except Exception as e:
        print(f"  ⚠️  RollingDate approach failed: {e}")
        print("  Falling back to StaticValues...")

        # Re-fetch clean definition and apply static fallback
        defn, name = fetch_definition()
        defn = patch_param_static(defn)
        update_analysis(defn, name)
        ok = wait_analysis()
        if not ok:
            print("  ❌ StaticValues fallback also failed — aborting")
            return
        print(f"  ✅ StaticValues fallback ({STATIC_FALLBACK}) applied successfully")

    # ── Step 3: Republish dashboard ──────────────────────────────────
    print("\n[3/4] Republishing dashboard...")
    new_ver = republish_dashboard()

    # ── Step 4: Summary ──────────────────────────────────────────────
    print("\n[4/4] Summary")
    print(f"  Default type : {'RollingDate (truncDate WEEK, now())' if used_rolling else f'StaticValues ({STATIC_FALLBACK})'}")
    print(f"  Analysis     : UPDATE_SUCCESSFUL")
    print(f"  Dashboard ver: {new_ver if new_ver else 'FAILED'}")
    print()
    if new_ver:
        print("✅ Patch complete — pWeekStart now opens on the correct Monday")
    else:
        print("⚠️  Analysis patched but dashboard republish failed — check QuickSight console")


if __name__ == '__main__':
    main()
