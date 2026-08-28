#!/usr/bin/env python3
"""
fix_coo_table_cf.py
-------------------
Fix conditional formatting on all table visuals in coo-operational-analysis-prod.

Root cause: RowAlternateColorOptions overrides cell-level CF rules.

Fix per table:
  - tbl-ps-projects: cell CF exists but row alternating overrides it → disable row alt,
                     add white text CF rules, set purple alternating via RowAlternateColors
  - tbl-mc:          row-level CF (wrong) → replace with cell-level CF, fix colors to CE brand
  - tbl-esc:         no CF → add cell-level CF for escalation_state
  - tbl-missing:     no CF → add cell-level CF for submission_status

Design standards:
  Red    #D74018  (text #FFFFFF)
  Green  #33A94F  (text #FFFFFF)
  Yellow #FF9B00  (text #FFFFFF)
  Row alternating: #27164F (dark) / #3D2570 (light)
"""
import boto3, time

ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
DASHBOARD_ID = 'coo-operational-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

RED    = '#D74018'
GREEN  = '#33A94F'
YELLOW = '#FF9B00'
WHITE  = '#FFFFFF'
ROW_DARK  = '#27164F'
ROW_LIGHT = '#3D2570'

def cell_cf(field_id, expression, bg, text=WHITE):
    """Build a cell-level CF rule with background + text color."""
    return {'Cell': {'FieldId': field_id, 'TextFormat': {
        'BackgroundColor': {'Solid': {'Expression': expression, 'Color': bg}},
        'TextColor':       {'Solid': {'Expression': expression, 'Color': text}},
    }}}

def row_alt_options():
    # API only accepts a single alternate color; base row color comes from the theme
    return {'Status': 'ENABLED', 'RowAlternateColors': [ROW_LIGHT]}

qs = boto3.Session(
    profile_name='AWSAdministratorAccess-961341524729',
    region_name='us-east-1'
).client('quicksight')

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

updated = []

for sheet in defn['Sheets']:
    for visual in sheet['Visuals']:
        tbl = visual.get('TableVisual', {})
        vid = tbl.get('VisualId', '')
        if not vid:
            continue
        cfg = tbl.setdefault('ChartConfiguration', {})
        opts = cfg.setdefault('TableOptions', {})

        # ── tbl-ps-projects ──────────────────────────────────────────────────
        if vid == 'tbl-ps-projects':
            # Disable row alternating so cell CF wins, then re-enable with purple colors
            opts['RowAlternateColorOptions'] = row_alt_options()
            # Rebuild CF: cell-level with background + white text for all health columns
            tbl['ConditionalFormatting'] = {'ConditionalFormattingOptions': [
                # health (g5)
                cell_cf('tbl-ps-projects-g5', '{health} = "Red"',    RED),
                cell_cf('tbl-ps-projects-g5', '{health} = "Yellow"', YELLOW),
                cell_cf('tbl-ps-projects-g5', '{health} = "Green"',  GREEN),
                # health_budget (g6)
                cell_cf('tbl-ps-projects-g6', '{health_budget} = "Red"',    RED),
                cell_cf('tbl-ps-projects-g6', '{health_budget} = "Yellow"', YELLOW),
                cell_cf('tbl-ps-projects-g6', '{health_budget} = "Green"',  GREEN),
                # health_schedule (g7)
                cell_cf('tbl-ps-projects-g7', '{health_schedule} = "Red"',    RED),
                cell_cf('tbl-ps-projects-g7', '{health_schedule} = "Yellow"', YELLOW),
                cell_cf('tbl-ps-projects-g7', '{health_schedule} = "Green"',  GREEN),
                # escalation (g8) — values are Red/Green
                cell_cf('tbl-ps-projects-g8', '{escalation} = "Red"',   RED),
                cell_cf('tbl-ps-projects-g8', '{escalation} = "Green"', GREEN),
            ]}
            updated.append(vid)
            print(f'✓ {vid}: rebuilt cell CF + purple row alternating')

        # ── tbl-mc ───────────────────────────────────────────────────────────
        elif vid == 'tbl-mc':
            opts['RowAlternateColorOptions'] = row_alt_options()
            # Replace row-level CF with cell-level CF using CE brand colors
            tbl['ConditionalFormatting'] = {'ConditionalFormattingOptions': [
                cell_cf('tbl-mc-g1', '{health_overall} = "Red"',    RED),
                cell_cf('tbl-mc-g1', '{health_overall} = "Yellow"', YELLOW),
                cell_cf('tbl-mc-g1', '{health_overall} = "Green"',  GREEN),
            ]}
            updated.append(vid)
            print(f'✓ {vid}: replaced row CF with cell CF + purple row alternating')

        # ── tbl-esc ──────────────────────────────────────────────────────────
        elif vid == 'tbl-esc':
            opts['RowAlternateColorOptions'] = row_alt_options()
            # escalation_state values: Done, Watching, In Progress, New
            tbl['ConditionalFormatting'] = {'ConditionalFormattingOptions': [
                cell_cf('tbl-esc-g4', '{escalation_state} = "Done"',        GREEN),
                cell_cf('tbl-esc-g4', '{escalation_state} = "Watching"',    YELLOW),
                cell_cf('tbl-esc-g4', '{escalation_state} = "In Progress"', YELLOW),
                cell_cf('tbl-esc-g4', '{escalation_state} = "New"',         RED),
            ]}
            updated.append(vid)
            print(f'✓ {vid}: added cell CF for escalation_state + purple row alternating')

        # ── tbl-missing ──────────────────────────────────────────────────────
        elif vid == 'tbl-missing':
            opts['RowAlternateColorOptions'] = row_alt_options()
            # submission_status values: Complete, Less Than 90%, Less Than 50%, No Time Submitted
            tbl['ConditionalFormatting'] = {'ConditionalFormattingOptions': [
                cell_cf('tbl-missing-g3', '{submission_status} = "Complete"',           GREEN),
                cell_cf('tbl-missing-g3', '{submission_status} = "Less Than 90%"',      YELLOW),
                cell_cf('tbl-missing-g3', '{submission_status} = "Less Than 50%"',      RED),
                cell_cf('tbl-missing-g3', '{submission_status} = "No Time Submitted"',  RED),
            ]}
            updated.append(vid)
            print(f'✓ {vid}: added cell CF for submission_status + purple row alternating')

print(f'\nUpdated {len(updated)} tables: {updated}')

# Update analysis
qs.update_analysis(
    AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn
)
print('✓ Analysis updated')

# Publish dashboard
resp2 = qs.update_dashboard(
    AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
    Name='COO Operational Dashboard (prod)', Definition=defn, ThemeArn=THEME_ARN
)
new_ver = int(resp2['VersionArn'].split('/')[-1])
print(f'  Dashboard version {new_ver} creating...')

for _ in range(30):
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)
    match = next((v for v in versions['DashboardVersionSummaryList']
                  if v['VersionNumber'] == new_ver), None)
    status = match['Status'] if match else 'UNKNOWN'
    if status == 'CREATION_SUCCESSFUL':
        break
    if 'FAILED' in status:
        print(f'  ✗ Dashboard creation failed: {status}')
        exit(1)
    time.sleep(3)

qs.update_dashboard_published_version(
    AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=new_ver
)
print(f'✅ Dashboard published at version {new_ver}')
