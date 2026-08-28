#!/usr/bin/env python3
"""
Update noon import EventBridge rule to:
1. Run incremental import (9am already did weekly)
2. Take KPI snapshot after import
3. Refresh only COO dashboard datasets
"""
import boto3, json

eb = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('events')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')

RULE = 'production-weekly-import-noon-ct'

# COO dashboard datasets only
COO_DATASETS = [
    'kpi-weekly-snapshots-prod',
    'ps-project-status-view',
    'productive-utilization',
    'clockify-missing-time-submissions-prod',
    'clockify-missing-time-submissions',
    'escalations-detail',
    'ps-stage-trend',
    'project-hours-summary-prod',
    'project-hours-current-week-prod',
    'mc-ticket-activity',
    'mc-projects-at-risk',
    'ps-projects-at-risk',
    'time-compliance-current-week',
    'missing-time-history',
]

new_payload = {
    "mode": "incremental",
    "snapshot_kpis": True,          # take KPI snapshot after import
    "notify": True,
    "refresh_quicksight": True,
    "quicksight_dataset_ids": COO_DATASETS
}

# Get current targets
targets = eb.list_targets_by_rule(Rule=RULE)['Targets']
print(f'Current targets: {len(targets)}')
print(f'Current payload: {targets[0].get("Input")}')

# Update target payload
targets[0]['Input'] = json.dumps(new_payload)
eb.put_targets(Rule=RULE, Targets=targets)
print(f'\n✅ Updated noon import payload:')
print(json.dumps(new_payload, indent=2))
