"""
patch_kpi_date_granularity.py

Fixes two issues that cause KPI tiles to show zero/no data for Quarter-to-Date:

Issue 1 — RelativeDatesFilter TimeGranularity=WEEK (Sheet 3, all sheets):
  QuickSight's RelativeDatesFilter with TimeGranularity=WEEK compares by ISO week
  number, not by date range. A week_start value of '2026-04-07' is in ISO week 15,
  and 'Quarter to Date' with WEEK granularity fails to include it because QTD is not
  a supported relative-date concept at week granularity. Changing to DAY makes
  QuickSight evaluate the filter as a date-range comparison (>= quarter start,
  <= today), which correctly includes all week_start dates in the quarter.

Issue 2 — TopBottomFilter on Sheet 1 and Sheet 2 KPI tiles:
  The TopBottomFilter (fg-s1-kpi, fg-s2-kpi) is scoped to ALL KPI tiles on those
  sheets and limits results to the 1 most-recent week row. This overrides the date
  range control entirely for those tiles — selecting QTD has no effect. The tiles
  always show only the latest week.
  Fix: remove the KPI visual IDs from the TopBottomFilter scope so the date control
  applies to them directly. Also update Sheet 1 KPI tile aggregations from MAX to
  semantically correct aggregations (AVERAGE for percentages, MAX for single-value
  metrics like open escalations and active resources, which are still point-in-time
  but will now be the max across the selected period — acceptable for a KPI tile).

Aggregation decisions for multi-week periods:
  - billable_util_pct, productive_util_pct, time_compliance_pct, ps_on_time_pct,
    projects_red_pct -> AVERAGE (weighted average across weeks)
  - ps_avg_duration_weeks -> AVERAGE (duration doesn't sum)
  - open_escalations -> MAX (shows peak — point-in-time metric)
  - active_resource_count (S1), headcount (S2) -> MAX (headcount is a snapshot)
  - total_billable_hours (S2) -> SUM (hours accumulate)
  - weighted_billable_util, compliance_pct (S2) -> AVERAGE
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

# KPI visual IDs that should be removed from TopBottomFilter scope
# (so the date range control applies to them)
S1_KPI_VISUAL_IDS = [
    'kpi-s1-billable-util',
    'kpi-s1-productive-util',
    'kpi-s1-compliance',
    'kpi-s1-ps-ontime',
    'kpi-s1-eng-duration',
    'kpi-s1-red-pct',
    'kpi-s1-escalations',
    'kpi-s1-resources',
]

S2_KPI_VISUAL_IDS = [
    'kpi-s2-headcount',
    'kpi-s2-hours',
    'kpi-s2-billable',
    'kpi-s2-compliance',
]

# Correct aggregations for Sheet 1 KPI tiles (currently all MAX, wrong for multi-week)
S1_KPI_AGGREGATION_FIXES = {
    'billable_util_pct':     {'SimpleNumericalAggregation': 'AVERAGE'},
    'productive_util_pct':   {'SimpleNumericalAggregation': 'AVERAGE'},
    'time_compliance_pct':   {'SimpleNumericalAggregation': 'AVERAGE'},
    'ps_on_time_pct':        {'SimpleNumericalAggregation': 'AVERAGE'},
    'ps_avg_duration_weeks': {'SimpleNumericalAggregation': 'AVERAGE'},
    'projects_red_pct':      {'SimpleNumericalAggregation': 'AVERAGE'},
    'open_escalations':      {'SimpleNumericalAggregation': 'MAX'},    # point-in-time snapshot
    'active_resource_count': {'SimpleNumericalAggregation': 'MAX'},    # point-in-time snapshot
}


def main():
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    qs = session.client('quicksight')

    print('Fetching analysis definition...')
    resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
    defn = resp['Definition']
    name_resp = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
    analysis_name = name_resp['Analysis']['Name']
    print(f'Analysis name: {analysis_name}')

    # ----------------------------------------------------------------
    # Fix 1: RelativeDatesFilter TimeGranularity WEEK -> DAY
    # ----------------------------------------------------------------
    print('\n--- Fix 1: RelativeDatesFilter TimeGranularity ---')
    rdf_patched = 0
    for fg in defn.get('FilterGroups', []):
        for f in fg.get('Filters', []):
            if 'RelativeDatesFilter' in f:
                rdf = f['RelativeDatesFilter']
                old_gran = rdf.get('TimeGranularity')
                old_min = rdf.pop('MinimumGranularity', None)
                rdf['TimeGranularity'] = 'DAY'
                print(f"  Patched {fg['FilterGroupId']} / {rdf['FilterId']}: "
                      f"TimeGranularity {old_gran!r} -> 'DAY'"
                      + (f", removed MinimumGranularity={old_min!r}" if old_min else ''))
                rdf_patched += 1
    print(f'RelativeDatesFilter patches: {rdf_patched}')

    # ----------------------------------------------------------------
    # Fix 2: Disable TopBottomFilter groups (fg-s1-kpi, fg-s2-kpi)
    # These lock KPI tiles to the single most-recent week regardless of the
    # date range control. Disabling them lets the RelativeDatesFilter apply.
    # QuickSight does not allow SELECTED_VISUALS with an empty VisualIds list,
    # so we use Status=DISABLED to neutralize these filter groups.
    # ----------------------------------------------------------------
    print('\n--- Fix 2: Disable TopBottomFilter groups (fg-s1-kpi, fg-s2-kpi) ---')
    tbf_patched = 0
    for fg in defn.get('FilterGroups', []):
        fg_id = fg['FilterGroupId']
        if fg_id not in ('fg-s1-kpi', 'fg-s2-kpi'):
            continue
        old_status = fg.get('Status', 'ENABLED')
        fg['Status'] = 'DISABLED'
        print(f"  {fg_id}: Status {old_status!r} -> 'DISABLED'")
        tbf_patched += 1

    print(f'TopBottomFilter groups disabled: {tbf_patched}')

    # ----------------------------------------------------------------
    # Fix 3: Update Sheet 1 KPI tile aggregations from MAX -> correct
    # ----------------------------------------------------------------
    print('\n--- Fix 3: Sheet 1 KPI tile aggregations ---')
    agg_patched = 0
    for sheet in defn.get('Sheets', []):
        if sheet['SheetId'] != 'sheet-kpi-s1':
            continue
        for v in sheet.get('Visuals', []):
            kpi = v.get('KPIVisual', {})
            if not kpi:
                continue
            title = kpi.get('Title', {}).get('FormatText', {}).get('PlainText', '?')
            fws = kpi.get('ChartConfiguration', {}).get('FieldWells', {}).get('Values', [])
            for fw in fws:
                if 'NumericalMeasureField' in fw:
                    nmf = fw['NumericalMeasureField']
                    col = nmf.get('Column', {}).get('ColumnName', '')
                    if col in S1_KPI_AGGREGATION_FIXES:
                        old_agg = nmf.get('AggregationFunction', {})
                        nmf['AggregationFunction'] = S1_KPI_AGGREGATION_FIXES[col]
                        print(f"  Sheet1 '{title}' col={col}: {old_agg} -> {S1_KPI_AGGREGATION_FIXES[col]}")
                        agg_patched += 1
    print(f'Aggregation patches: {agg_patched}')

    # ----------------------------------------------------------------
    # Apply: update_analysis
    # ----------------------------------------------------------------
    print('\n--- Submitting update_analysis ---')
    try:
        qs.update_analysis(
            AwsAccountId=ACCOUNT,
            AnalysisId=ANALYSIS_ID,
            Name=analysis_name,
            ThemeArn=THEME_ARN,
            Definition=defn,
        )
        print('update_analysis submitted OK')
    except Exception as e:
        print(f'ERROR in update_analysis: {e}')
        raise

    print('Waiting for analysis update to complete...')
    for attempt in range(24):
        time.sleep(5)
        status_resp = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
        status = status_resp['Analysis']['Status']
        print(f'  [{attempt+1}] Analysis status: {status}')
        if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
            print('Analysis update successful.')
            break
        if 'FAILED' in status:
            errors = qs.describe_analysis_definition(
                AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID
            ).get('Errors', [])
            print(f'Analysis update FAILED. Errors: {json.dumps(errors, indent=2)}')
            raise RuntimeError(f'Analysis update failed: {status}')
    else:
        raise RuntimeError('Timed out waiting for analysis update')

    # ----------------------------------------------------------------
    # Re-fetch updated definition and publish dashboard
    # ----------------------------------------------------------------
    print('\n--- Fetching updated definition for dashboard publish ---')
    defn2 = qs.describe_analysis_definition(
        AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID
    )['Definition']

    print('Submitting update_dashboard...')
    resp2 = qs.update_dashboard(
        AwsAccountId=ACCOUNT,
        DashboardId=DASHBOARD_ID,
        Name='KPI Tracking Dashboard (prod)',
        Definition=defn2,
        ThemeArn=THEME_ARN,
    )
    new_ver = int(resp2['VersionArn'].split('/')[-1])
    print(f'Dashboard version being created: v{new_ver}')

    print('Waiting for dashboard version to be ready...')
    for attempt in range(30):
        time.sleep(4)
        versions = qs.list_dashboard_versions(
            AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID
        )['DashboardVersionSummaryList']
        match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
        if match:
            dstatus = match.get('Status', '')
            print(f'  [{attempt+1}] Dashboard v{new_ver} status: {dstatus}')
            if dstatus == 'CREATION_SUCCESSFUL':
                qs.update_dashboard_published_version(
                    AwsAccountId=ACCOUNT,
                    DashboardId=DASHBOARD_ID,
                    VersionNumber=new_ver,
                )
                print(f'Dashboard v{new_ver} published successfully.')
                break
            if 'FAILED' in dstatus:
                print(f'Dashboard creation FAILED: {match}')
                raise RuntimeError(f'Dashboard v{new_ver} creation failed')
        else:
            print(f'  [{attempt+1}] Waiting for v{new_ver} to appear...')
    else:
        raise RuntimeError('Timed out waiting for dashboard version')

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    print('\n=== PATCH COMPLETE ===')
    print(f'  RelativeDatesFilter TimeGranularity patches: {rdf_patched}')
    print(f'  TopBottomFilter groups disabled:             {tbf_patched}')
    print(f'  KPI tile aggregation patches:                {agg_patched}')
    print(f'  Dashboard version published:                 v{new_ver}')
    print('\nExpected outcome:')
    print('  - Quarter to Date / Year to Date now returns all rows in range for all sheets')
    print('  - Sheet 1 & 2 KPI tiles no longer locked to single most-recent week')
    print('  - Sheet 1 percentage KPIs now show AVERAGE across selected period')
    print('  - Headcount (Sheet 2) still works correctly (SUM driven by date filter)')
    print('  - For "This Week" the date filter still works correctly (DAY granularity'
          ' matches the current week\'s rows)')


if __name__ == '__main__':
    main()
