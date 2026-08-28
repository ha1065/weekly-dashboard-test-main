#!/usr/bin/env python3
"""Check kpi_snapshots WoW escalation columns and escalations dataset columns."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('=== kpi_snapshots escalation columns ===')
print(q("""SELECT column_name FROM information_schema.columns
           WHERE table_name = 'kpi_weekly_snapshots'
           AND column_name LIKE '%escal%'
           ORDER BY ordinal_position"""))

print('\n=== escalations table columns ===')
print(q("""SELECT column_name FROM information_schema.columns
           WHERE table_name = 'escalations'
           ORDER BY ordinal_position"""))

print('\n=== sample kpi_snapshots escalation data (last 3 weeks) ===')
print(q("""SELECT week_start_date, open_escalations, escalations_prev
           FROM vw_kpi_ytd
           ORDER BY week_start_date DESC LIMIT 3"""))
