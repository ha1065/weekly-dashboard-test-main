import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

# 1. Check the PUBLISHED DASHBOARD version definition (not the analysis)
print('=== PUBLISHED DASHBOARD VERSION 4 DEFINITION ===')
try:
    db_defn = qs.describe_dashboard_definition(
        AwsAccountId=ACCOUNT,
        DashboardId='kpi-tracking-dashboard-prod',
        VersionNumber=4
    )['Definition']
    for sheet in db_defn.get('Sheets', []):
        fcs = sheet.get('FilterControls', [])
        pcs = sheet.get('ParameterControls', [])
        print(f"Sheet {sheet.get('SheetId')} ({sheet.get('Name','')})")
        print(f"  FilterControls ({len(fcs)}):")
        for fc in fcs:
            for t in ['Dropdown','RelativeDateTime','DateTimePicker','List']:
                if t in fc:
                    f = fc[t]
                    print(f"    FilterControl.{t}: id={f.get('FilterControlId')} title={f.get('Title')} src={f.get('SourceFilterId','')}")
        print(f"  ParameterControls ({len(pcs)}):")
        for pc in pcs:
            for t in ['DateTimePicker','Dropdown','TextField']:
                if t in pc:
                    p = pc[t]
                    print(f"    ParameterControl.{t}: id={p.get('ParameterControlId')} title={p.get('Title')} src={p.get('SourceParameterName','')}")
except Exception as e:
    print(f'describe_dashboard_definition error: {e}')

# 2. Compare against the ANALYSIS definition
print('\n=== ANALYSIS DEFINITION ===')
analysis_defn = qs.describe_analysis_definition(
    AwsAccountId=ACCOUNT,
    AnalysisId='kpi-tracking-analysis-prod'
)['Definition']
for sheet in analysis_defn.get('Sheets', []):
    fcs = sheet.get('FilterControls', [])
    pcs = sheet.get('ParameterControls', [])
    print(f"Sheet {sheet.get('SheetId')} ({sheet.get('Name','')})")
    print(f"  FilterControls ({len(fcs)}):")
    for fc in fcs:
        for t in ['Dropdown','RelativeDateTime','DateTimePicker','List']:
            if t in fc:
                f = fc[t]
                print(f"    FilterControl.{t}: id={f.get('FilterControlId')} title={f.get('Title')} src={f.get('SourceFilterId','')}")
    print(f"  ParameterControls ({len(pcs)}):")
    for pc in pcs:
        for t in ['DateTimePicker','Dropdown','TextField']:
            if t in pc:
                p = pc[t]
                print(f"    ParameterControl.{t}: id={p.get('ParameterControlId')} title={p.get('Title')} src={p.get('SourceParameterName','')}")

# 3. Check all dashboard versions and which is published
print('\n=== DASHBOARD VERSIONS ===')
db = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId='kpi-tracking-dashboard-prod')
print(f"Published version: {db['Dashboard']['Version']['VersionNumber']}")
versions = qs.list_dashboard_versions(AwsAccountId=ACCOUNT, DashboardId='kpi-tracking-dashboard-prod')['DashboardVersionSummaryList']
for v in sorted(versions, key=lambda x: x['VersionNumber'], reverse=True)[:5]:
    print(f"  v{v['VersionNumber']}: {v['Status']} {v['CreatedTime']}")
