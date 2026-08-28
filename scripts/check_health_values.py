#!/usr/bin/env python3
"""Check actual escalation and health column values via Lambda query."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('=== Distinct escalation values ===')
print(q("SELECT DISTINCT escalation FROM vw_ps_project_status WHERE status_category != 'Done' LIMIT 20"))

print('\n=== Distinct health values ===')
print(q("SELECT DISTINCT health FROM vw_ps_project_status WHERE status_category != 'Done' LIMIT 20"))
