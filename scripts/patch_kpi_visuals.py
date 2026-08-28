import boto3, time, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
name = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']

# ── Fix 1: Headcount KPI tile – AVERAGE → MAX on sheet-kpi-s2 ─────────────────
fix1_applied = False
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] != 'sheet-kpi-s2':
        continue
    for v in sheet.get('Visuals', []):
        kpi = v.get('KPIVisual', {})
        if kpi.get('VisualId') != 'kpi-s2-headcount':
            continue
        fws = kpi.get('ChartConfiguration', {}).get('FieldWells', {}).get('Values', [])
        for fw in fws:
            for ft in ['NumericalMeasureField', 'CategoricalMeasureField']:
                if ft in fw and fw[ft].get('Column', {}).get('ColumnName') == 'headcount':
                    old_agg = fw[ft].get('AggregationFunction', {})
                    fw[ft]['AggregationFunction'] = {'SimpleNumericalAggregation': 'MAX'}
                    print(f'Fix 1 ✓ headcount: {old_agg} → MAX')
                    fix1_applied = True

if not fix1_applied:
    print('Fix 1 WARN: kpi-s2-headcount / headcount field not found')

# ── Fix 2: Project Portfolio Health bar chart RAG colors on sheet-kpi-s1 ──────
# Diagnostic showed VisualId = "bar-s1-health" (not "bar-s1-project-health")
# FieldIds from diagnostic: green=ks-hg, amber=ks-ha, red=ks-hr
fix2_applied = False
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] != 'sheet-kpi-s1':
        continue
    for v in sheet.get('Visuals', []):
        bar = v.get('BarChartVisual', {})
        if bar.get('VisualId') != 'bar-s1-health':
            continue
        cfg = bar.get('ChartConfiguration', {})
        fw = cfg.get('FieldWells', {}).get('BarChartAggregatedFieldWells', {})
        color_map = []
        for val in fw.get('Values', []):
            if 'NumericalMeasureField' in val:
                col = val['NumericalMeasureField'].get('Column', {}).get('ColumnName', '')
                fid = val['NumericalMeasureField'].get('FieldId', '')
                if 'green' in col.lower():
                    color_map.append({'Element': {'FieldId': fid}, 'Color': '#33A94F'})
                elif 'amber' in col.lower():
                    color_map.append({'Element': {'FieldId': fid}, 'Color': '#FF9B00'})
                elif 'red' in col.lower():
                    color_map.append({'Element': {'FieldId': fid}, 'Color': '#D74018'})
        if color_map:
            cfg['VisualPalette'] = {'ColorMap': color_map}
            for entry in color_map:
                print(f'Fix 2 ✓ bar-s1-health: FieldId={entry["Element"]["FieldId"]} → {entry["Color"]}')
            fix2_applied = True
        else:
            print('Fix 2 WARN: no green/amber/red columns found in bar-s1-health values')

if not fix2_applied:
    print('Fix 2 WARN: bar-s1-health not found or no color mappings built')

# ── Fix 3: Add compliance_pct_calc and productive_util_pct to Staff Detail table ─
fix3_notes = []
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] != 'sheet-kpi-s3':
        continue
    for v in sheet.get('Visuals', []):
        tbl = v.get('TableVisual', {})
        if tbl.get('VisualId') != 'tbl-s3-staff':
            continue
        cfg = tbl.get('ChartConfiguration', {})

        # Ensure the unagg structure exists
        if 'FieldWells' not in cfg:
            cfg['FieldWells'] = {}
        if 'TableUnaggregatedFieldWells' not in cfg['FieldWells']:
            cfg['FieldWells']['TableUnaggregatedFieldWells'] = {'Values': []}
        unagg = cfg['FieldWells']['TableUnaggregatedFieldWells']['Values']

        # TableUnaggregatedFieldWells items are FLAT: {FieldId, Column, FormatConfiguration}
        # NOT nested under 'UnaggregatedField' — that wrapper is only in aggregated wells
        existing_cols = [f.get('Column', {}).get('ColumnName', '') for f in unagg]
        print(f'Fix 3: existing table cols: {existing_cols}')

        # Replace is_compliant → compliance_pct_calc if present
        for f in unagg:
            if f.get('Column', {}).get('ColumnName') == 'is_compliant':
                f['Column']['ColumnName'] = 'compliance_pct_calc'
                f['FieldId'] = 'tbl-s3-compliance-pct'
                fix3_notes.append('replaced is_compliant → compliance_pct_calc')

        # Refresh existing cols after potential replacement
        existing_cols_now = [f.get('Column', {}).get('ColumnName', '') for f in unagg]

        # Add compliance_pct_calc if still absent
        if 'compliance_pct_calc' not in existing_cols_now:
            unagg.append({
                'FieldId': 'tbl-s3-compliance-pct',
                'Column': {
                    'DataSetIdentifier': 'kpi_staff',
                    'ColumnName': 'compliance_pct_calc'
                }
            })
            fix3_notes.append('added compliance_pct_calc')

        # Add productive_util_pct if absent
        if 'productive_util_pct' not in existing_cols_now:
            unagg.append({
                'FieldId': 'tbl-s3-productive-util-col',
                'Column': {
                    'DataSetIdentifier': 'kpi_staff',
                    'ColumnName': 'productive_util_pct'
                }
            })
            fix3_notes.append('added productive_util_pct')

        # Update FieldOptions labels
        if 'FieldOptions' not in cfg:
            cfg['FieldOptions'] = {}
        fo = cfg['FieldOptions'].get('SelectedFieldOptions', [])
        existing_fids = {f.get('FieldId') for f in fo}
        if 'tbl-s3-compliance-pct' not in existing_fids:
            fo.append({
                'FieldId': 'tbl-s3-compliance-pct',
                'CustomLabel': 'Compliance %',
                'Visibility': 'VISIBLE'
            })
            fix3_notes.append('label: Compliance % → tbl-s3-compliance-pct')
        if 'tbl-s3-productive-util-col' not in existing_fids:
            fo.append({
                'FieldId': 'tbl-s3-productive-util-col',
                'CustomLabel': 'Productive Util %',
                'Visibility': 'VISIBLE'
            })
            fix3_notes.append('label: Productive Util % → tbl-s3-productive-util-col')
        cfg['FieldOptions']['SelectedFieldOptions'] = fo

for note in fix3_notes:
    print(f'Fix 3 ✓ {note}')
if not fix3_notes:
    print('Fix 3: no changes needed (columns already present)')

# ── Update analysis ────────────────────────────────────────────────────────────
print('\nSubmitting update_analysis...')
try:
    qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name=name,
        ThemeArn=THEME_ARN,
        Definition=defn
    )
    print('update_analysis: submitted')
except Exception as e:
    print(f'ERROR update_analysis: {e}')
    raise

for i in range(24):
    time.sleep(5)
    status = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Status']
    print(f'  [{i+1}] Analysis status: {status}')
    if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'):
        print('Analysis update SUCCEEDED')
        break
    if 'FAILED' in status:
        errs = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID).get('Errors', [])
        print(f'Analysis update FAILED: {errs}')
        raise SystemExit(1)

# ── Republish dashboard ────────────────────────────────────────────────────────
print('\nPublishing dashboard...')
defn2 = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name='KPI Tracking Dashboard (prod)',
    Definition=defn2,
    ThemeArn=THEME_ARN
)
new_ver = int(resp['VersionArn'].split('/')[-1])
print(f'Dashboard version {new_ver} creating...')

for i in range(30):
    time.sleep(4)
    versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
    match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
    if match:
        st = match.get('Status', '')
        print(f'  [{i+1}] Dashboard v{new_ver}: {st}')
        if st == 'CREATION_SUCCESSFUL':
            qs.update_dashboard_published_version(
                AwsAccountId=ACCOUNT,
                DashboardId=DASHBOARD_ID,
                VersionNumber=new_ver
            )
            print(f'\n✅ Dashboard v{new_ver} published successfully')
            break
        if 'FAILED' in st:
            print(f'Dashboard publish FAILED: {match}')
            raise SystemExit(1)
    else:
        print(f'  [{i+1}] waiting for v{new_ver}...')
