#!/usr/bin/env python3
"""Diagnose compliance view issues."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('=== Nayab user record ===')
print(q("""SELECT name, status, daily_capacity, time_submission, pod_assignment, created_at
           FROM clockify_users WHERE name ILIKE '%nayab%'"""))

print('\n=== Last complete week ===')
print(q("SELECT (DATE_TRUNC('week', CURRENT_DATE)::DATE - 7)::DATE AS week_start"))

print('\n=== Users on compliance report with hours > 0 ===')
print(q("""
WITH last_week AS (
    SELECT (DATE_TRUNC('week', CURRENT_DATE)::DATE - 7)::DATE AS ws
),
user_hours AS (
    SELECT clockify_user_id, SUM(duration_hours) AS total_hours
    FROM clockify_detailed_time_entries
    WHERE week_start = (SELECT ws FROM last_week)
    GROUP BY clockify_user_id
)
SELECT u.name, u.daily_capacity, u.daily_capacity * 5 AS expected,
       COALESCE(h.total_hours, 0) AS submitted,
       u.time_submission, u.pod_assignment
FROM clockify_users u
LEFT JOIN user_hours h ON u.clockify_user_id = h.clockify_user_id
WHERE u.status = 'active'
  AND u.daily_capacity > 0
  AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
  AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
  AND COALESCE(h.total_hours, 0) < u.daily_capacity * 5 * 0.9
  AND COALESCE(h.total_hours, 0) > 0
ORDER BY submitted DESC
LIMIT 15
"""))
