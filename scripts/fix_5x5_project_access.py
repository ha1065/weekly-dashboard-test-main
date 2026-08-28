#!/usr/bin/env python3
"""Add specific users to all new 5x5x5 projects."""
import boto3, json, requests

sm = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('secretsmanager')
lambda_client = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
env = lambda_client.get_function_configuration(FunctionName='production-clockify-import')['Environment']['Variables']
secret = json.loads(sm.get_secret_value(SecretId=env['SECRET_NAME'])['SecretString'])

api_key = secret['clockify_api_key']
workspace_id = secret['clockify_workspace_id']
headers = {'X-Api-Key': api_key, 'Content-Type': 'application/json'}
base = f'https://api.clockify.me/api/v1/workspaces/{workspace_id}'

TARGET_NAMES = {
    'afnan naseem', 'andrew peterson', 'chris.xenos', 'hassan siddique',
    'jason mcinerney', 'muhammad waleed', 'muhammad.yahya',
    'nayab.waseem', 'santohsh.bugatha', 'stephen.furlong'
}

# Get workspace users and match by name/email
users_resp = requests.get(f'{base}/users', headers=headers, params={'page-size': 200})
all_users = users_resp.json() if users_resp.ok else []
user_ids = []
for u in (all_users if isinstance(all_users, list) else []):
    name = (u.get('name') or '').lower()
    email = (u.get('email') or '').lower().split('@')[0]
    if name in TARGET_NAMES or email in TARGET_NAMES:
        user_ids.append(u['id'])
        print(f'  Found: {u.get("name")} ({u.get("email")}) id={u["id"]}')

print(f'Matched {len(user_ids)}/10 users')

# Get new 5x5x5 projects
new_projs = requests.get(f'{base}/projects', headers=headers, params={'name': '5x5x5', 'page-size': 50}).json()
new_projects = [(p['id'], p.get('clientName','?')) for p in (new_projs if isinstance(new_projs, list) else []) if p.get('name') == '5x5x5']
print(f'New projects: {len(new_projects)}')

# Add users via project update (PUT) with memberships
for pid, client_name in new_projects:
    # Get current project details first
    proj = requests.get(f'{base}/projects/{pid}', headers=headers).json()
    memberships = [{'userId': uid, 'hourlyRate': None, 'membershipStatus': 'ACTIVE', 'membershipType': 'PROJECT'} for uid in user_ids]
    r = requests.put(
        f'{base}/projects/{pid}',
        headers=headers,
        json={
            'name': proj.get('name', '5x5x5'),
            'clientId': proj.get('clientId'),
            'billable': proj.get('billable', True),
            'isPublic': False,
            'memberships': memberships,
        }
    )
    print(f'  {client_name}: {r.status_code} {r.text[:100] if not r.ok else "OK"}')

print('Done')
