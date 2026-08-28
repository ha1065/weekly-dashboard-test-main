import boto3, time

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
name = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Name']

patched = 0
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] != 'sheet-kpi-s2':
        continue
    for v in sheet.get('Visuals', []):
        kpi = v.get('KPIVisual', {})
        if not kpi:
            continue
        title = kpi.get('Title', {}).get('FormatText', {}).get('PlainText', '')
        fws = kpi.get('ChartConfiguration', {}).get('FieldWells', {}).get('Values', [])
        for fw in fws:
            for ft in ['NumericalMeasureField', 'CategoricalMeasureField']:
                if ft in fw:
                    col = fw[ft].get('Column', {}).get('ColumnName', '')
                    if col == 'headcount':
                        old_agg = fw[ft].get('AggregationFunction', {})
                        fw[ft]['AggregationFunction'] = {'SimpleNumericalAggregation': 'AVERAGE'}
                        print(f"Patched headcount tile '{title}': SUM -> AVERAGE (was {old_agg})")
                        patched += 1

# Also fix headcount on Sheet 3 if it exists
for sheet in defn.get('Sheets', []):
    if sheet['SheetId'] != 'sheet-kpi-s3':
        continue
    for v in sheet.get('Visuals', []):
        kpi = v.get('KPIVisual', {})
        if not kpi:
            continue
        title = kpi.get('Title', {}).get('FormatText', {}).get('PlainText', '')
        fws = kpi.get('ChartConfiguration', {}).get('FieldWells', {}).get('Values', [])
        for fw in fws:
            for ft in ['NumericalMeasureField', 'CategoricalMeasureField']:
                if ft in fw:
                    col = fw[ft].get('Column', {}).get('ColumnName', '')
                    # Sheet 3 uses DISTINCT_COUNT on user_name which is already correct for unique staff
                    # Only fix if it's headcount column using SUM
                    if col == 'headcount' and fw[ft].get('AggregationFunction', {}).get('SimpleNumericalAggregation') == 'SUM':
                        fw[ft]['AggregationFunction'] = {'SimpleNumericalAggregation': 'AVERAGE'}
                        print(f"Patched S3 headcount tile '{title}': SUM -> AVERAGE")
                        patched += 1

print(f"Total patched: {patched}")

if patched > 0:
    qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID, Name=name, ThemeArn=THEME_ARN, Definition=defn)
    print('update_analysis submitted')
    for _ in range(20):
        time.sleep(5)
        status = qs.describe_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Analysis']['Status']
        print(f'Analysis: {status}')
        if status in ('UPDATE_SUCCESSFUL', 'CREATION_SUCCESSFUL'): break
        if 'FAILED' in status:
            print(qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID).get('Errors', []))
            break

    # Republish
    defn2 = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)['Definition']
    resp = qs.update_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID,
        Name='KPI Tracking Dashboard (prod)', Definition=defn2, ThemeArn=THEME_ARN)
    new_ver = int(resp['VersionArn'].split('/')[-1])
    print(f'Creating v{new_ver}...')
    for _ in range(30):
        time.sleep(4)
        versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['DashboardVersionSummaryList']
        match = next((v for v in versions if v['VersionNumber'] == new_ver), None)
        if match and match['Status'] == 'CREATION_SUCCESSFUL':
            qs.update_dashboard_published_version(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, VersionNumber=new_ver)
            print(f'Published v{new_ver}')
            break
        elif match and 'FAILED' in match.get('Status',''):
            print(f'FAILED: {match}')
            break
        elif match:
            print(f'  {match["Status"]}')
else:
    print("No headcount KPI tiles found using SUM — nothing to patch.")
