#!/usr/bin/env python3
"""Diagnose PS active project count discrepancy."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('=== KPI snapshot ps_active_projects (latest week) ===')
print(q("SELECT week_start_date, ps_active_projects FROM vw_kpi_ytd ORDER BY week_start_date DESC LIMIT 1"))

print('\n=== vw_ps_project_status: PS active count by issue_type ===')
print(q("""SELECT issue_type, COUNT(*) as cnt
           FROM vw_ps_project_status
           WHERE category = 'PS' AND status_category != 'Done'
           GROUP BY issue_type ORDER BY cnt DESC"""))

print('\n=== vw_ps_project_status: PS active count by health ===')
print(q("""SELECT health, COUNT(*) as cnt
           FROM vw_ps_project_status
           WHERE category = 'PS' AND status_category != 'Done'
           GROUP BY health ORDER BY cnt DESC"""))

print('\n=== vw_ps_project_status: PS active with Emailed request only ===')
print(q("""SELECT health, COUNT(*) as cnt
           FROM vw_ps_project_status
           WHERE category = 'PS' AND status_category != 'Done'
             AND issue_type = 'Emailed request'
           GROUP BY health ORDER BY cnt DESC"""))

print('\n=== kpi_snapshot.py active project logic ===')
print(q("""SELECT COUNT(*) FROM ps_project_status
           WHERE category = 'PS' AND status_category != 'Done'
             AND NOT COALESCE(is_excluded, FALSE)"""))
