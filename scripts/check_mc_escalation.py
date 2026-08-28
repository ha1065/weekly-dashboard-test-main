#!/usr/bin/env python3
"""Check mc_at_risk dataset customer name columns."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('=== mc_at_risk dataset (mc_ticket_activity_snapshot) sample ===')
print(q("""SELECT week_start, customer_name, health_overall, clockify_hours, open_escalations
           FROM mc_ticket_activity_snapshot
           ORDER BY week_start DESC LIMIT 5"""))

print('\n=== vw_kpi_ytd columns with escalation ===')
print(q("""SELECT column_name FROM information_schema.columns
           WHERE table_name = 'vw_kpi_ytd'
           AND column_name LIKE '%escal%'"""))

print('\n=== vw_kpi_ytd last 3 weeks escalation data ===')
print(q("""SELECT week_start_date, open_escalations
           FROM vw_kpi_ytd ORDER BY week_start_date DESC LIMIT 3"""))
