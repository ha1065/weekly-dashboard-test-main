#!/usr/bin/env python3
"""Fix trailing space in ps_project_status.escalation column."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# Fix the data
result = q("UPDATE ps_project_status SET escalation = TRIM(escalation) WHERE escalation != TRIM(escalation)")
print('Update result:', result)

# Verify
result2 = q("SELECT DISTINCT escalation, length(escalation) FROM ps_project_status WHERE escalation IS NOT NULL")
print('Distinct values after fix:', result2)
