#!/usr/bin/env python3
"""Check MC issue types to see if same fix needed."""
import boto3, json

lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('=== MC active projects by issue_type ===')
print(q("""SELECT issue_type, COUNT(*) FROM ps_project_status
           WHERE category = 'MC' AND status_category = 'In Progress'
             AND NOT COALESCE(is_excluded, FALSE)
           GROUP BY issue_type ORDER BY 2 DESC"""))
