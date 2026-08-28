#!/usr/bin/env python3
"""Check EventBridge rule targets to see what each import triggers.

Checks all 6 managed rules before a CloudFormation deploy:
  - 3 import rules (9am CT, noon CT, daily Jira)
  - 3 compliance email rules (9:30am CT, 12:30pm CT, 2:30pm CT)

Run this before any `cloudformation deploy` to verify live payloads
match the template. See the WARNING comment in template.yaml for the
safe deploy sequence if payloads diverge.
"""
import boto3

eb = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('events')

rules = [
    # Import rules
    'production-weekly-import-9am-ct',
    'production-weekly-import-noon-ct',
    'production-jira-daily-refresh',
    # Compliance email rules
    'production-compliance-email-930am-ct',
    'production-compliance-email-1230pm-ct',
    'production-compliance-email-230pm-ct',
]

for rule in rules:
    try:
        targets = eb.list_targets_by_rule(Rule=rule)['Targets']
        print(f'\n=== {rule} ===')
        for t in targets:
            print(f'  Target: {t["Arn"].split(":")[-1]}')
            if 'Input' in t:
                print(f'  Payload: {t["Input"]}')
    except Exception as e:
        print(f'{rule}: {e}')
