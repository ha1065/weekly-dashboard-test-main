#!/usr/bin/env python3
"""Full dashboard accuracy audit."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# 1. Import schedule
print('=== Import schedule (EventBridge rules) ===')
eb = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('events')
rules = eb.list_rules(NamePrefix='production')['Rules']
for r in rules:
    print(f"  {r['Name']}: {r.get('ScheduleExpression','N/A')} — {r['State']}")

# 2. Last import timestamps
print('\n=== Last successful imports by category ===')
print(q("""SELECT import_category, MAX(completed_at) AT TIME ZONE 'America/New_York' AS last_run_et
           FROM import_logs WHERE status = 'success'
           GROUP BY import_category ORDER BY last_run_et DESC"""))

# 3. Compliance view data freshness
print('\n=== vw_missing_time_submissions: last_updated_date ===')
print(q("SELECT last_updated_date, last_updated_time, COUNT(*) as non_compliant FROM vw_missing_time_submissions GROUP BY 1,2"))

# 4. Compliance view: current non-compliant count
print('\n=== Current non-compliant staff (zero hours) ===')
print(q("SELECT COUNT(*) as count FROM vw_missing_time_submissions WHERE hours_submitted = 0"))

# 5. Productive utilization view data
print('\n=== vw_productive_utilization: week coverage ===')
print(q("SELECT week_start, COUNT(*) as people FROM vw_productive_utilization GROUP BY week_start ORDER BY week_start DESC LIMIT 3"))

# 6. KPI snapshot freshness
print('\n=== KPI snapshot: latest week and key metrics ===')
print(q("""SELECT week_start_date, snapshot_taken_at AT TIME ZONE 'America/New_York' AS taken_et,
           billable_util_pct, time_compliance_pct, ps_active_projects, open_escalations
           FROM vw_kpi_ytd ORDER BY week_start_date DESC LIMIT 1"""))

# 7. PS project count alignment
print('\n=== PS active projects: KPI vs live view ===')
print(q("""SELECT
    (SELECT ps_active_projects FROM vw_kpi_ytd ORDER BY week_start_date DESC LIMIT 1) AS kpi_snapshot,
    (SELECT COUNT(*) FROM ps_project_status WHERE category='PS' AND status_category='In Progress'
     AND issue_type='Emailed request' AND NOT COALESCE(is_excluded,FALSE)) AS live_view"""))

# 8. SPICE freshness for COO dashboard datasets
print('\n=== SPICE freshness for COO dashboard datasets ===')
coo_datasets = [
    'kpi-weekly-snapshots-prod', 'ps-project-status-view', 'productive-utilization',
    'clockify-missing-time-submissions-prod', 'escalations-detail',
    'ps-stage-trend', 'project-hours-summary-prod', 'mc-ticket-activity',
]
for ds_id in coo_datasets:
    try:
        ing = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId=ds_id)['Ingestions']
        latest = sorted(ing, key=lambda x: x['CreatedTime'], reverse=True)[0]
        status = latest['IngestionStatus']
        created = latest['CreatedTime'].strftime('%Y-%m-%d %H:%M ET')
        rows = latest.get('RowInfo', {}).get('RowsIngested', '?')
        print(f"  {ds_id:<45} {status:<12} {created}  ({rows} rows)")
    except Exception as e:
        print(f"  {ds_id}: ERROR {e}")
