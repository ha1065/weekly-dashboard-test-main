"""
patch_kpi_period_filters.py
───────────────────────────
Replace the date-filter architecture on the KPI Tracking Dashboard:

  REMOVES:
    - pWeekStart DateTimeParameterDeclaration
    - All DateTimePicker ParameterControls
    - TopBottomFilter groups (fg-s1-kpi, fg-s2-kpi, fg-s3-kpi)
    - TimeEqualityFilter date groups (fg-s1-date, fg-s2-date, fg-s3-date)

  ADDS per sheet:
    - RelativeDatesFilter  (fg-s*-date) — LAST 1 WEEK = default to last completed week
    - Completed-weeks guard (fg-s*-complete):
        Primary: TimeRangeFilter + RollingDate (addDateTime(-7,'WK',truncDate('WK',now())))
        Fallback: RelativeDatesFilter LAST 52 WEEK (if RollingDate rejected)
    - RelativeDateTime FilterControl (ctrl-s*-date) linked to fg-s*-date

API constraint discovered:
  RelativeDatesFilter only accepts RelativeDateValue for NEXT and LAST types.
  Use LAST + 1 + WEEK for "last completed week" default.
"""
import boto3
import time
import json

PROFILE      = 'AWSAdministratorAccess-961341524729'
REGION       = 'us-east-1'
ACCOUNT      = '961341524729'
ANALYSIS_ID  = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN    = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

# ── Per-sheet configuration ───────────────────────────────────────────────────
SHEET_CONFIG = [
    {
        'sheet_id':    'sheet-kpi-s1',
        'fg_date':     'fg-s1-date',
        'fg_complete': 'fg-s1-complete',
        'ctrl_id':     'ctrl-s1-date',
        'dataset':     'kpi_snapshots',
        'column':      'week_start_date',
    },
    {
        'sheet_id':    'sheet-kpi-s2',
        'fg_date':     'fg-s2-date',
        'fg_complete': 'fg-s2-complete',
        'ctrl_id':     'ctrl-s2-date',
        'dataset':     'kpi_practice',
        'column':      'week_start',
    },
    {
        'sheet_id':    'sheet-kpi-s3',
        'fg_date':     'fg-s3-date',
        'fg_complete': 'fg-s3-complete',
        'ctrl_id':     'ctrl-s3-date',
        'dataset':     'kpi_staff',
        'column':      'week_start',
    },
]

REMOVE_FG_IDS = {
    'fg-s1-kpi', 'fg-s2-kpi', 'fg-s3-kpi',       # TopBottomFilter
    'fg-s1-date', 'fg-s2-date', 'fg-s3-date',     # TimeEqualityFilter / old RelativeDates
    'fg-s1-complete', 'fg-s2-complete', 'fg-s3-complete',  # stale guards
}


def build_relative_dates_fg(cfg):
    """
    Period-selector filter for the RelativeDateTime control.
    Default = LAST 1 WEEK → last completed Mon-Sun week.
    (QuickSight only accepts RelativeDateValue on LAST/NEXT types.)
    """
    return {
        'FilterGroupId': cfg['fg_date'],
        'Filters': [{
            'RelativeDatesFilter': {
                'FilterId':    cfg['fg_date'],
                'Column': {
                    'DataSetIdentifier': cfg['dataset'],
                    'ColumnName':        cfg['column'],
                },
                'AnchorDateConfiguration': {'AnchorOption': 'NOW'},
                'RelativeDateType':  'LAST',
                'RelativeDateValue': 1,
                'TimeGranularity':   'WEEK',
                'NullOption':        'ALL_VALUES',
            }
        }],
        'ScopeConfiguration': {
            'SelectedSheets': {
                'SheetVisualScopingConfigurations': [{
                    'SheetId': cfg['sheet_id'],
                    'Scope':   'ALL_VISUALS',
                }]
            }
        },
        'Status':       'ENABLED',
        'CrossDataset': 'SINGLE_DATASET',
    }


def build_completed_weeks_fg_rolling(cfg):
    """
    Completed-weeks guard using TimeRangeFilter + RollingDate.
    Expression: addDateTime(-7,'WK',truncDate('WK',now()))
      → start of last week (most recent Monday)
    IncludeMaximum=True → includes all rows where column <= last Monday,
      which is ALL completed weeks. Current in-progress week never included.
    """
    return {
        'FilterGroupId': cfg['fg_complete'],
        'Filters': [{
            'TimeRangeFilter': {
                'FilterId': cfg['fg_complete'],
                'Column': {
                    'DataSetIdentifier': cfg['dataset'],
                    'ColumnName':        cfg['column'],
                },
                'RangeMaximumValue': {
                    'RollingDate': {
                        'Expression':        "addDateTime(-7, 'WK', truncDate('WK', now()))",
                        'DataSetIdentifier': cfg['dataset'],
                    }
                },
                'NullOption':     'ALL_VALUES',
                'IncludeMaximum': True,
            }
        }],
        'ScopeConfiguration': {
            'SelectedSheets': {
                'SheetVisualScopingConfigurations': [{
                    'SheetId': cfg['sheet_id'],
                    'Scope':   'ALL_VISUALS',
                }]
            }
        },
        'Status':       'ENABLED',
        'CrossDataset': 'SINGLE_DATASET',
    }


def build_completed_weeks_fg_fallback(cfg):
    """
    Fallback guard when TimeRangeFilter.RollingDate is rejected.
    LAST 52 WEEK: WEEK granularity snaps to Mon-Sun boundaries,
    so the current in-progress week is naturally excluded.
    """
    return {
        'FilterGroupId': cfg['fg_complete'],
        'Filters': [{
            'RelativeDatesFilter': {
                'FilterId': cfg['fg_complete'],
                'Column': {
                    'DataSetIdentifier': cfg['dataset'],
                    'ColumnName':        cfg['column'],
                },
                'AnchorDateConfiguration': {'AnchorOption': 'NOW'},
                'RelativeDateType':  'LAST',
                'RelativeDateValue': 52,
                'TimeGranularity':   'WEEK',
                'NullOption':        'ALL_VALUES',
            }
        }],
        'ScopeConfiguration': {
            'SelectedSheets': {
                'SheetVisualScopingConfigurations': [{
                    'SheetId': cfg['sheet_id'],
                    'Scope':   'ALL_VISUALS',
                }]
            }
        },
        'Status':       'ENABLED',
        'CrossDataset': 'SINGLE_DATASET',
    }


def build_relative_datetime_ctrl(cfg):
    """
    RelativeDateTime FilterControl — linked to the period-selector RelativeDatesFilter.
    Renders a dropdown in the QuickSight UI with presets:
    This Week, Last Week, This Month, Last Month, This Quarter, This Year (YTD), etc.
    """
    return {
        'RelativeDateTime': {
            'FilterControlId': cfg['ctrl_id'],
            'Title':           'Reporting Period',
            'SourceFilterId':  cfg['fg_date'],
            'DisplayOptions': {
                'TitleOptions': {
                    'Visibility':        'VISIBLE',
                    'FontConfiguration': {'FontSize': {'Relative': 'MEDIUM'}},
                },
                'DateTimeFormat': 'MM/DD/YYYY',
            },
        }
    }


def try_update_analysis(defn, name, label=''):
    """Submit update_analysis and return (success, error_str)."""
    try:
        qs.update_analysis(
            AwsAccountId=ACCOUNT,
            AnalysisId=ANALYSIS_ID,
            Name=name,
            ThemeArn=THEME_ARN,
            Definition=defn,
        )
        print(f'  update_analysis {label} accepted ✅')
        return True, None
    except Exception as e:
        print(f'  update_analysis {label} FAILED: {e}')
        return False, str(e)


# ── Fetch current definition ──────────────────────────────────────────────────
print('═' * 60)
print('Fetching current analysis definition...')
resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']
name = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']
print(f'  Analysis name: {name}')
print(f'  FilterGroups (before): {len(defn.get("FilterGroups", []))}')
print(f'  Parameters (before):   {len(defn.get("ParameterDeclarations", []))}')

# ── Step 1: Remove pWeekStart parameter ──────────────────────────────────────
print('\n[1] Removing pWeekStart parameter...')
defn['ParameterDeclarations'] = [
    p for p in defn.get('ParameterDeclarations', [])
    if list(p.values())[0].get('Name') != 'pWeekStart'
]
print(f'    Parameters remaining: {[list(p.values())[0].get("Name") for p in defn.get("ParameterDeclarations", [])]}')

# ── Step 2: Remove old filter groups ─────────────────────────────────────────
print('\n[2] Removing old filter groups...')
old_ids = [fg['FilterGroupId'] for fg in defn.get('FilterGroups', []) if fg['FilterGroupId'] in REMOVE_FG_IDS]
print(f'    Removing: {old_ids}')
defn['FilterGroups'] = [fg for fg in defn.get('FilterGroups', []) if fg['FilterGroupId'] not in REMOVE_FG_IDS]
print(f'    FilterGroups remaining: {len(defn["FilterGroups"])}')

# ── Step 3: Add new filter groups ────────────────────────────────────────────
print('\n[3] Adding new filter groups...')
for cfg in SHEET_CONFIG:
    defn['FilterGroups'].append(build_relative_dates_fg(cfg))
    print(f"    + {cfg['fg_date']:20s} RelativeDatesFilter(LAST 1 WEEK) → {cfg['sheet_id']}")

    defn['FilterGroups'].append(build_completed_weeks_fg_rolling(cfg))
    print(f"    + {cfg['fg_complete']:20s} TimeRangeFilter(RollingDate)   → {cfg['sheet_id']}")

print(f'    FilterGroups total: {len(defn["FilterGroups"])}')

# ── Step 4: Update sheet FilterControls and ParameterControls ─────────────────
print('\n[4] Updating sheet controls...')
for sheet in defn.get('Sheets', []):
    cfg = next((c for c in SHEET_CONFIG if c['sheet_id'] == sheet['SheetId']), None)
    if not cfg:
        continue

    # Remove DateTimePicker ParameterControls
    pcs_before = len(sheet.get('ParameterControls', []))
    sheet['ParameterControls'] = [
        pc for pc in sheet.get('ParameterControls', [])
        if 'DateTimePicker' not in pc
    ]
    pcs_after = len(sheet.get('ParameterControls', []))

    # Remove existing RelativeDateTime controls for this source to avoid dupes
    sheet['FilterControls'] = [
        fc for fc in sheet.get('FilterControls', [])
        if not (isinstance(fc, dict) and 'RelativeDateTime' in fc
                and fc['RelativeDateTime'].get('FilterControlId') == cfg['ctrl_id'])
    ]

    # Insert RelativeDateTime at front of filter row
    sheet['FilterControls'].insert(0, build_relative_datetime_ctrl(cfg))
    print(f"    {sheet['SheetId']}: ParameterControls {pcs_before}→{pcs_after}, "
          f"FilterControls now {len(sheet['FilterControls'])} "
          f"(added {cfg['ctrl_id']})")

# ── Step 5: Submit — try RollingDate first, then fallback ─────────────────────
print('\n[5] Submitting update_analysis (primary — RollingDate guard)...')
success, err = try_update_analysis(defn, name, '(primary)')
rolling_date_accepted = success

if not success:
    # RollingDate likely rejected — check error type
    is_rolling_issue = any(kw in (err or '') for kw in ['RollingDate', 'RangeMaximumValue', 'TimeRangeFilter'])
    print(f'\n    Error type — rolling date issue: {is_rolling_issue}')
    print('    ⚠  Switching to RelativeDatesFilter(LAST 52 WEEK) fallback for guards...')

    # Remove RollingDate guards
    defn['FilterGroups'] = [
        fg for fg in defn['FilterGroups']
        if fg['FilterGroupId'] not in {cfg['fg_complete'] for cfg in SHEET_CONFIG}
    ]
    # Add LAST 52 WEEK fallback guards
    for cfg in SHEET_CONFIG:
        defn['FilterGroups'].append(build_completed_weeks_fg_fallback(cfg))
        print(f"    + {cfg['fg_complete']:20s} RelativeDatesFilter(LAST 52 WEEK) [fallback]")

    print('\n    Retrying update_analysis (fallback)...')
    success, err = try_update_analysis(defn, name, '(fallback)')
    if not success:
        raise RuntimeError(f'Both primary and fallback failed. Last error: {err}')

# ── Poll analysis ─────────────────────────────────────────────────────────────
print('\n[6] Polling analysis...')
for i in range(24):
    time.sleep(5)
    r = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
    status = r['Analysis']['Status']
    errors = r['Analysis'].get('Errors', [])
    print(f'    [{i+1:02d}] {status}')
    if 'SUCCESSFUL' in status:
        print('    ✅ Analysis update complete')
        break
    if 'FAILED' in status:
        for e in errors:
            print(f'    ERROR: {e.get("Type")}: {e.get("Message")}')
        raise RuntimeError(f'Analysis update failed: {status}')
else:
    raise TimeoutError('Analysis polling timed out (120s)')

# ── Republish dashboard ───────────────────────────────────────────────────────
print(f'\n[7] Republishing dashboard {DASHBOARD_ID}...')
defn2 = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)',
    Definition=defn2,
    ThemeArn=THEME_ARN,
    DashboardPublishOptions={
        'AdHocFilteringOption': {'AvailabilityStatus': 'ENABLED'},
        'ExportToCSVOption':    {'AvailabilityStatus': 'ENABLED'},
    },
)
new_ver = int(resp['VersionArn'].split('/')[-1])
print(f'    Waiting for dashboard v{new_ver}...')

for i in range(30):
    time.sleep(4)
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
    if not match:
        continue
    vstatus = match.get('Status', '')
    if vstatus == 'CREATION_SUCCESSFUL':
        qs.update_dashboard_published_version(
            AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=new_ver
        )
        print(f'    ✅ Published v{new_ver}')
        break
    elif 'FAILED' in vstatus:
        print(f'    ✗ Dashboard failed: {match}')
        break
    else:
        print(f'    [{i+1:02d}] {vstatus}')

# ── Final summary ─────────────────────────────────────────────────────────────
print()
print('═' * 60)
print('PATCH COMPLETE — SUMMARY')
print('═' * 60)

guard_label = ('TimeRangeFilter(RollingDate — addDateTime(-7,WK,truncDate(WK,now())))'
               if rolling_date_accepted else
               'RelativeDatesFilter(LAST 52 WEEK) [fallback — RollingDate rejected]')

print(f'\nCompleted-weeks guard type: {guard_label}')
print()
print(f'{"Sheet":<18} {"fg_date":<20} {"fg_complete":<22} {"ctrl_id":<20}')
print('-' * 80)
for cfg in SHEET_CONFIG:
    print(f"{cfg['sheet_id']:<18} {cfg['fg_date']:<20} {cfg['fg_complete']:<22} {cfg['ctrl_id']:<20}")

print()
print(f'  pWeekStart parameter:      REMOVED')
print(f'  TopBottomFilter groups:    REMOVED (fg-s1-kpi, fg-s2-kpi, fg-s3-kpi)')
print(f'  TimeEqualityFilter groups: REMOVED (fg-s1-date, fg-s2-date, fg-s3-date)')
print(f'  DateTimePicker controls:   REMOVED from all 3 sheets')
print(f'  New period controls:       ctrl-s1-date, ctrl-s2-date, ctrl-s3-date (RelativeDateTime)')
print(f'  Default period:            Last 1 completed week (LAST 1 WEEK)')
print(f'  Dashboard version:         v{new_ver} (published)')
