#!/usr/bin/env python3
"""Migrate 5x5x5 time entries from Project 5X5X5 to per-customer projects."""
import boto3, json, requests
from datetime import datetime

sm = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('secretsmanager')
lambda_client = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
env = lambda_client.get_function_configuration(FunctionName='production-clockify-import')['Environment']['Variables']
secret = json.loads(sm.get_secret_value(SecretId=env['SECRET_NAME'])['SecretString'])

api_key = secret['clockify_api_key']
workspace_id = secret['clockify_workspace_id']
headers = {'X-Api-Key': api_key, 'Content-Type': 'application/json'}
base = f'https://api.clockify.me/api/v1/workspaces/{workspace_id}'

def q(sql):
    r = lambda_client.invoke(FunctionName='production-clockify-import',
        Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

# 1. Rename Athlete HR -> Athlete AI in Clockify
clients = requests.get(f'{base}/clients', headers=headers, params={'page-size': 200}).json()
client_map = {c['name']: c['id'] for c in (clients if isinstance(clients, list) else [])}
if 'Athlete HR' in client_map:
    r = requests.put(f'{base}/clients/{client_map["Athlete HR"]}', headers=headers, json={'name': 'Athlete AI'})
    print(f'Renamed Athlete HR -> Athlete AI: {r.status_code}')
    client_map['Athlete AI'] = client_map.pop('Athlete HR')
else:
    print(f'Athlete HR not found. Clients: {[k for k in client_map if "athlete" in k.lower() or "aspire" in k.lower()]}')

# 2. Fix mapping table
result = q("UPDATE ps_project_mapping SET ps_client_name='Athlete AI', clockify_client_name='Athlete AI' WHERE ps_client_name='Athlete HR'")
print(f'Updated mapping Athlete HR -> Athlete AI')

# 3. Get old project ID
projects = requests.get(f'{base}/projects', headers=headers, params={'name': '5X5X5', 'page-size': 20}).json()
old_proj = next((p for p in (projects if isinstance(projects, list) else []) if p.get('name') == 'Project 5X5X5'), None)
if not old_proj:
    print('ERROR: Project 5X5X5 not found'); exit(1)
old_proj_id = old_proj['id']
print(f'Old project: Project 5X5X5 id={old_proj_id}')

# 4. Build new project map: client_name.lower() -> project_id
new_projs = requests.get(f'{base}/projects', headers=headers, params={'name': '5x5x5', 'page-size': 50}).json()
new_proj_map = {}
for p in (new_projs if isinstance(new_projs, list) else []):
    if p.get('name') == '5x5x5' and p.get('clientName'):
        new_proj_map[p['clientName'].lower()] = p['id']
print(f'New projects: {list(new_proj_map.keys())}')

# 5. Get all time entries via reports API
report = requests.post(
    f'https://reports.api.clockify.me/v1/workspaces/{workspace_id}/reports/detailed',
    headers=headers,
    json={
        'dateRangeStart': '2026-01-01T00:00:00Z',
        'dateRangeEnd': datetime.utcnow().strftime('%Y-%m-%dT23:59:59Z'),
        'detailedFilter': {'page': 1, 'pageSize': 1000},
        'projects': {'ids': [old_proj_id], 'contains': 'CONTAINS'},
    }
).json()
entries = report.get('timeentries', [])
print(f'Total entries in Project 5X5X5: {len(entries)}')

# 6. Move entries with task names to new projects

# 6. Move entries with task names to new projects
moved = failed = skipped = 0
for e in entries:
    task_name = e.get('taskName')
    if not task_name:
        skipped += 1
        continue
    new_pid = new_proj_map.get(task_name.lower())
    if not new_pid:
        # Alias: Athlete HR -> Athlete AI
        alias_map = {'athlete hr': 'athlete ai'}
        aliased = alias_map.get(task_name.lower())
        if aliased:
            new_pid = new_proj_map.get(aliased)
    if not new_pid:
        for k, v in new_proj_map.items():
            if k in task_name.lower() or task_name.lower() in k:
                new_pid = v; break
    if not new_pid:
        print(f'  No match for task: {task_name}')
        failed += 1; continue

    r = requests.put(
        f'{base}/time-entries/{e.get("_id") or e.get("id")}',
        headers=headers,
        json={
            'projectId': new_pid,
            'taskId': None,
            'start': e['timeInterval']['start'],
            'end': e['timeInterval']['end'],
            'description': e.get('description', ''),
            'billable': e.get('billable', True),
        }
    )
    if r.ok:
        moved += 1
        print(f'  Moved: {task_name} entry {(e.get("_id") or e.get("id","?"))[:8]}...')
    else:
        print(f'  Failed {e.get("_id") or e.get("id")}: {r.status_code} {r.text[:80]}')
        failed += 1

print(f'\nDone. Moved: {moved}, Failed: {failed}, No task (left in Project 5X5X5): {skipped}')
