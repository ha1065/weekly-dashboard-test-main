#!/usr/bin/env python3
"""Fix vw_missing_time_submissions: re-apply view definition via Lambda, then refresh SPICE."""
import boto3, json, time

PROFILE  = 'AWSAdministratorAccess-961341524729'
REGION   = 'us-east-1'
ACCOUNT  = '961341524729'
DATASET  = 'clockify-missing-time-submissions'

lc = boto3.Session(profile_name=PROFILE, region_name=REGION).client('lambda')
qs = boto3.Session(profile_name=PROFILE, region_name=REGION).client('quicksight')

def run_sql(sql):
    r = json.loads(lc.invoke(
        FunctionName='production-clockify-import',
        Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode()
    )['Payload'].read())
    if r.get('errorMessage'):
        print(f'  ❌ {r["errorMessage"][:200]}')
        return False
    print(f'  ✅ OK')
    return True

# Step 1: Drop existing view
print('Dropping existing view...')
run_sql('DROP VIEW IF EXISTS vw_missing_time_submissions;')

# Step 2: Recreate with last_updated_date
print('Recreating view...')
create_sql = """
CREATE VIEW vw_missing_time_submissions AS
WITH last_complete_week AS (
    SELECT (DATE_TRUNC('week', CURRENT_DATE)::DATE - 7)::DATE AS week_start_date
),
user_hours_last_week AS (
    SELECT
        te.clockify_user_id,
        SUM(te.duration_hours) AS total_hours,
        COUNT(*) AS entry_count
    FROM clockify_detailed_time_entries te
    WHERE te.week_start = (SELECT week_start_date FROM last_complete_week)
    GROUP BY te.clockify_user_id
),
last_clockify_import AS (
    SELECT
        (completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago')::DATE AS last_updated_date,
        TO_CHAR(completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Chicago', 'HH:MI AM') AS last_updated_time
    FROM import_logs
    WHERE import_category = 'time_entries'
      AND status = 'success'
    ORDER BY completed_at DESC
    LIMIT 1
)
SELECT
    u.clockify_user_id,
    u.name,
    u.email,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.pod_assignment, '{', ''), '}', ''), '"', ''), E'\\\\', '')) AS pod_assignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.practice_alignment, '{', ''), '}', ''), '"', ''), E'\\\\', '')) AS practice_alignment,
    TRIM(REPLACE(REPLACE(REPLACE(REPLACE(u.skill_area, '{', ''), '}', ''), '"', ''), E'\\\\', '')) AS skill_area,
    u.location,
    u.daily_capacity,
    u.daily_capacity * 5 AS weekly_expected_hours,
    COALESCE(h.total_hours, 0) AS hours_submitted,
    COALESCE(h.entry_count, 0) AS entries_submitted,
    CASE WHEN COALESCE(h.total_hours, 0) = 0 THEN 'No Time Submitted' ELSE 'Complete' END AS submission_status,
    CASE
        WHEN COALESCE(h.total_hours, 0) = 0 THEN '0 Hours'
        WHEN COALESCE(h.total_hours, 0) < 20 THEN '1-19 Hours'
        WHEN COALESCE(h.total_hours, 0) < 30 THEN '20-29 Hours'
        ELSE '30+ Hours'
    END AS hours_bucket,
    (SELECT week_start_date FROM last_complete_week) AS week_start_date,
    (SELECT last_updated_date FROM last_clockify_import) AS last_updated_date,
    (SELECT last_updated_time FROM last_clockify_import) AS last_updated_time
FROM clockify_users u
LEFT JOIN user_hours_last_week h ON u.clockify_user_id = h.clockify_user_id
WHERE u.status = 'active'
  AND u.daily_capacity > 0
  AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
  AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
  AND NOT COALESCE(u.reporting_excluded, FALSE)
  AND u.created_at::DATE <= (SELECT week_start_date FROM last_complete_week) + INTERVAL '6 days'
  AND COALESCE(h.total_hours, 0) = 0
ORDER BY u.pod_assignment, u.name
"""

if not run_sql(create_sql.strip()):
    raise SystemExit('View creation failed — not triggering SPICE refresh')

# Step 3: Verify column exists
print('Verifying last_updated_date column...')
ok = run_sql("SELECT last_updated_date FROM vw_missing_time_submissions LIMIT 1;")
if not ok:
    raise SystemExit('Column still missing after view recreation')

# Step 4: Trigger SPICE refresh
print('Triggering SPICE refresh...')
iid = f'fix-view-{int(time.time())}'
qs.create_ingestion(AwsAccountId=ACCOUNT, DataSetId=DATASET, IngestionId=iid)

deadline = time.time() + 120
while time.time() < deadline:
    time.sleep(10)
    s = qs.describe_ingestion(AwsAccountId=ACCOUNT, DataSetId=DATASET, IngestionId=iid)['Ingestion']
    status = s['IngestionStatus']
    if status in ('COMPLETED', 'FAILED', 'CANCELLED'):
        rows = s.get('RowInfo', {}).get('RowsIngested', 0)
        err  = s.get('ErrorInfo', {})
        print(f'{"✅" if status=="COMPLETED" else "❌"} {status}  rows={rows}  {err}')
        break
