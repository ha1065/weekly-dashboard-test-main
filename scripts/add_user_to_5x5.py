#!/usr/bin/env python3
import boto3, json, requests

sm = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('secretsmanager')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
env = lc.get_function_configuration(FunctionName='production-clockify-import')['Environment']['Variables']
secret = json.loads(sm.get_secret_value(SecretId=env['SECRET_NAME'])['SecretString'])

api_key, workspace_id = secret['clockify_api_key'], secret['clockify_workspace_id']
headers = {'X-Api-Key': api_key, 'Content-Type': 'application/json'}
base = f'https://api.clockify.me/api/v1/workspaces/{workspace_id}'

users = requests.get(f'{base}/users', headers=headers, params={'page-size': 200}).json()
jason = next((u for u in users if 'stamman' in (u.get('name') or '').lower() or 'stamman' in (u.get('email') or '').lower()), None)
if not jason:
    print('Not found'); exit(1)
print(f'Found: {jason["name"]} ({jason["email"]})')

projs = requests.get(f'{base}/projects', headers=headers, params={'name': '5x5x5', 'page-size': 50}).json()
for p in projs:
    if p.get('name') == '5x5x5':
        pid = p['id']
        detail = requests.get(f'{base}/projects/{pid}', headers=headers).json()
        existing = detail.get('memberships', [])
        # Add Jason if not already present
        if not any(m.get('userId') == jason['id'] for m in existing):
            existing.append({'userId': jason['id'], 'hourlyRate': None, 'membershipType': 'PROJECT', 'membershipStatus': 'ACTIVE'})
        r = requests.put(f'{base}/projects/{pid}', headers=headers, json={
            'name': detail.get('name', '5x5x5'),
            'clientId': detail.get('clientId'),
            'billable': detail.get('billable', True),
            'isPublic': False,
            'memberships': existing,
        })
        print(f'  {p.get("clientName")}: {r.status_code} ({len(existing)} members)')
