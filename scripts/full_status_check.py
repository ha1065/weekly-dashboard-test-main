#!/usr/bin/env python3
"""Full status check: analysis health, dashboard version, and key CF state."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
ACCOUNT = '961341524729'

# 1. Analysis status
resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='coo-operational-analysis-prod')
print(f'Analysis status: {resp["ResourceStatus"]}')
print(f'Errors: {resp.get("Errors", "none")}')
sheets = resp.get('Definition', {}).get('Sheets', [])
print(f'Sheets in analysis: {[s["Name"] for s in sheets]}')

# 2. Dashboard published version
dash = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId='coo-operational-dashboard-prod')['Dashboard']
print(f'\nDashboard published version: {dash["Version"]["VersionNumber"]}')
print(f'Dashboard status: {dash["Version"]["Status"]}')

# 3. Check tbl-ps-projects CF
ps_sheet = next((s for s in sheets if s['SheetId'] == 'sheet-ps-delivery'), None)
if ps_sheet:
    for v in ps_sheet['Visuals']:
        tbl = v.get('TableVisual', {})
        if tbl.get('VisualId') == 'tbl-ps-projects':
            cf = tbl.get('ConditionalFormatting', {}).get('ConditionalFormattingOptions', [])
            esc_rules = [r for r in cf if r.get('Cell', {}).get('FieldId') == 'tbl-ps-projects-g8']
            row_alt = tbl['ChartConfiguration']['TableOptions'].get('RowAlternateColorOptions', {})
            print(f'\ntbl-ps-projects row alternate: {row_alt}')
            print(f'Escalation CF rules: {len(esc_rules)} rules')
            for r in esc_rules:
                expr = r['Cell']['TextFormat']['BackgroundColor']['Solid']['Expression']
                color = r['Cell']['TextFormat']['BackgroundColor']['Solid']['Color']
                print(f'  {expr} → {color}')

# 4. Check compliance view threshold
def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('\n=== Compliance view — current non-compliant count and sample ===')
print(q("""SELECT name, hours_submitted, submission_status
           FROM vw_missing_time_submissions LIMIT 10"""))

# 5. Check SPICE ingestion status for compliance dataset
ingestions = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId='clockify-missing-time-submissions-prod')['Ingestions']
latest = sorted(ingestions, key=lambda x: x['CreatedTime'], reverse=True)[0]
print(f'\nCompliance SPICE last ingestion: {latest["IngestionStatus"]} at {latest["CreatedTime"]}')
