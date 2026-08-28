#!/usr/bin/env python3
"""Pre-Monday verification: checks everything needed for Monday 9am CT import to succeed."""
import json
import sys
from datetime import datetime, timezone, timedelta

import boto3

PROFILE = 'AWSAdministratorAccess-961341524729'
REGION = 'us-east-1'
ACCOUNT_ID = '961341524729'
LAMBDA_NAME = 'production-clockify-import'
RULE_9AM = 'production-weekly-import-9am-ct'
RULE_NOON = 'production-weekly-import-noon-ct'
COMPLIANCE_RULES = [
    'production-compliance-email-930am-ct',
    'production-compliance-email-1230pm-ct',
    'production-compliance-email-230pm-ct',
]
DATASET_IDS = [
    'kpi-weekly-snapshots-prod', 'ps-project-status-view', 'productive-utilization',
    'clockify-missing-time-submissions-prod', 'clockify-missing-time-submissions',
    'escalations-detail', 'ps-stage-trend', 'project-hours-summary-prod',
    'project-hours-current-week-prod', 'mc-ticket-activity', 'mc-projects-at-risk',
    'ps-projects-at-risk', 'time-compliance-current-week', 'missing-time-history',
]

session = boto3.Session(profile_name=PROFILE, region_name=REGION)
lam = session.client('lambda')
eb = session.client('events')
iam = session.client('iam')
qs = session.client('quicksight')

criticals = []
warnings = []
fixes_needed = {}  # rule_name -> payload dict that needs fixing

def ok(msg): print(f'[PASS] {msg}')
def fail(msg, critical=True):
    print(f'[FAIL] {msg}' + (' ← CRITICAL' if critical else ' ← WARNING'))
    if critical:
        criticals.append(msg)
    else:
        warnings.append(msg)
def warn(msg):
    print(f'[WARN] {msg}')
    warnings.append(msg)


# ── CHECK 1: Lambda last deployed ────────────────────────────────────────────
print('\n--- CHECK 1: Lambda last deployed ---')
try:
    cfg = lam.get_function_configuration(FunctionName=LAMBDA_NAME)
    last_modified = cfg['LastModified']  # ISO string like "2026-06-25T14:23:00.000+0000"
    # Parse — boto3 returns a string here, not a datetime
    dt = datetime.fromisoformat(last_modified.replace('+0000', '+00:00'))
    age = datetime.now(timezone.utc) - dt
    ts = dt.strftime('%Y-%m-%d %H:%M UTC')
    if age > timedelta(days=7):
        fail(f'CHECK 1: Lambda last deployed {ts} ({age.days} days ago — may not have latest code)')
    else:
        ok(f'CHECK 1: Lambda last deployed {ts} ({age.days} days ago)')
except Exception as e:
    fail(f'CHECK 1: Could not get Lambda config: {e}')


# ── CHECK 2 & 3: EventBridge rule payloads ────────────────────────────────────
def check_rule_payload(rule_name, check_num, required_keys):
    """Check an EventBridge rule target payload. required_keys: list of (key, expected_value_or_callable)."""
    print(f'\n--- CHECK {check_num}: EventBridge {rule_name} payload ---')
    try:
        targets = eb.list_targets_by_rule(Rule=rule_name)['Targets']
        if not targets:
            fail(f'CHECK {check_num}: {rule_name} has no targets')
            return
        payload = json.loads(targets[0].get('Input', '{}'))
        issues = []
        for key, expected in required_keys:
            val = payload.get(key)
            if callable(expected):
                if not expected(val):
                    issues.append(f'{key}={val!r}')
            elif val != expected:
                issues.append(f'{key}={val!r} (expected {expected!r})')
        if issues:
            fail(f'CHECK {check_num}: {rule_name} payload issues: {", ".join(issues)}')
            fixes_needed[rule_name] = payload
        else:
            ds_count = len(payload.get('quicksight_dataset_ids', []))
            ok(f'CHECK {check_num}: {rule_name} payload complete ({ds_count} datasets)')
    except eb.exceptions.ResourceNotFoundException:
        fail(f'CHECK {check_num}: Rule {rule_name} not found')
    except Exception as e:
        fail(f'CHECK {check_num}: Error checking {rule_name}: {e}')

check_rule_payload(RULE_9AM, 2, [
    ('mode', lambda v: v is not None),
    ('refresh_quicksight', True),
    ('quicksight_dataset_ids', lambda v: isinstance(v, list) and len(v) >= 10),
])
check_rule_payload(RULE_NOON, 3, [
    ('snapshot_kpis', True),
    ('refresh_quicksight', True),
    ('quicksight_dataset_ids', lambda v: isinstance(v, list) and len(v) >= 10),
])


# ── CHECK 4: 9am rule ENABLED ────────────────────────────────────────────────
print(f'\n--- CHECK 4: {RULE_9AM} is ENABLED ---')
try:
    rule = eb.describe_rule(Name=RULE_9AM)
    state = rule.get('State', 'UNKNOWN')
    if state == 'ENABLED':
        ok(f'CHECK 4: {RULE_9AM} is ENABLED')
    else:
        fail(f'CHECK 4: {RULE_9AM} is {state} — Monday import will NOT run')
except eb.exceptions.ResourceNotFoundException:
    fail(f'CHECK 4: Rule {RULE_9AM} not found')
except Exception as e:
    fail(f'CHECK 4: Error: {e}')


# ── CHECK 5: Compliance email rules exist and are ENABLED ────────────────────
print('\n--- CHECK 5: Compliance email rules ---')
for rule_name in COMPLIANCE_RULES:
    try:
        rule = eb.describe_rule(Name=rule_name)
        state = rule.get('State', 'UNKNOWN')
        if state == 'ENABLED':
            ok(f'CHECK 5: {rule_name} is ENABLED')
        else:
            fail(f'CHECK 5: {rule_name} is {state}', critical=False)
    except eb.exceptions.ResourceNotFoundException:
        fail(f'CHECK 5: {rule_name} not found', critical=False)
    except Exception as e:
        fail(f'CHECK 5: Error checking {rule_name}: {e}', critical=False)


# ── CHECK 6: Lambda IAM role has sesv2:SendEmail ─────────────────────────────
print('\n--- CHECK 6: Lambda IAM role has sesv2:SendEmail ---')
try:
    cfg = lam.get_function_configuration(FunctionName=LAMBDA_NAME)
    role_arn = cfg['Role']
    sim = iam.simulate_principal_policy(
        PolicySourceArn=role_arn,
        ActionNames=['sesv2:SendEmail'],
        ResourceArns=['*'],
    )
    decision = sim['EvaluationResults'][0]['EvalDecision']
    if decision == 'allowed':
        ok(f'CHECK 6: Lambda role has sesv2:SendEmail (role: {role_arn.split("/")[-1]})')
    else:
        warn(f'CHECK 6: Lambda role does NOT have sesv2:SendEmail — compliance emails will fail')
except Exception as e:
    warn(f'CHECK 6: Could not simulate IAM policy: {e}')


# ── CHECK 7: SPICE dataset health ────────────────────────────────────────────
print('\n--- CHECK 7: SPICE dataset health (14 datasets) ---')
cutoff = datetime.now(timezone.utc) - timedelta(days=8)
spice_failures = []
for ds_id in DATASET_IDS:
    try:
        ingestions = qs.list_ingestions(DataSetId=ds_id, AwsAccountId=ACCOUNT_ID)['Ingestions']
        if not ingestions:
            fail(f'CHECK 7: {ds_id} — no ingestions found', critical=False)
            spice_failures.append(ds_id)
            continue
        latest = max(ingestions, key=lambda x: x.get('CreatedTime', datetime.min.replace(tzinfo=timezone.utc)))
        status = latest.get('IngestionStatus', 'UNKNOWN')
        created = latest.get('CreatedTime', datetime.min.replace(tzinfo=timezone.utc))
        age_days = (datetime.now(timezone.utc) - created).days
        if status == 'COMPLETED' and created >= cutoff:
            ok(f'CHECK 7: {ds_id} — {status} ({age_days}d ago)')
        elif status == 'FAILED':
            fail(f'CHECK 7: {ds_id} — FAILED (last attempt {age_days}d ago)', critical=False)
            spice_failures.append(ds_id)
        else:
            warn(f'CHECK 7: {ds_id} — {status} ({age_days}d ago, >8 days stale)')
            spice_failures.append(ds_id)
    except qs.exceptions.ResourceNotFoundException:
        fail(f'CHECK 7: {ds_id} — dataset not found in QuickSight', critical=False)
        spice_failures.append(ds_id)
    except Exception as e:
        warn(f'CHECK 7: {ds_id} — error: {e}')


# ── SUMMARY ──────────────────────────────────────────────────────────────────
print('\n' + '=' * 40)
print('RESULT SUMMARY')
print('=' * 40)
if criticals:
    print(f'\n❌ {len(criticals)} CRITICAL failure(s) — Monday import WILL FAIL without fixes:')
    for c in criticals:
        print(f'   • {c}')
if warnings:
    print(f'\n⚠️  {len(warnings)} warning(s):')
    for w in warnings:
        print(f'   • {w}')
if not criticals and not warnings:
    print('\n✅ All checks passed — Monday import is ready.')
elif not criticals:
    print('\n✅ No CRITICAL failures — Monday import should succeed (review warnings above).')

# ── FIX COMMANDS ─────────────────────────────────────────────────────────────
if fixes_needed:
    print('\n' + '=' * 40)
    print('FIX COMMANDS')
    print('=' * 40)
    for rule_name, current_payload in fixes_needed.items():
        # Suggest the corrected payload
        fixed = dict(current_payload)
        if rule_name == RULE_9AM:
            if 'mode' not in fixed:
                fixed['mode'] = 'weekly'
            fixed['refresh_quicksight'] = True
            if not isinstance(fixed.get('quicksight_dataset_ids'), list) or len(fixed.get('quicksight_dataset_ids', [])) < 10:
                fixed['quicksight_dataset_ids'] = DATASET_IDS
        elif rule_name == RULE_NOON:
            fixed['snapshot_kpis'] = True
            fixed['refresh_quicksight'] = True
            if not isinstance(fixed.get('quicksight_dataset_ids'), list) or len(fixed.get('quicksight_dataset_ids', [])) < 10:
                fixed['quicksight_dataset_ids'] = DATASET_IDS

        # Get current target ID
        try:
            targets = eb.list_targets_by_rule(Rule=rule_name)['Targets']
            target_id = targets[0]['Id'] if targets else 'UNKNOWN'
            target_arn = targets[0]['Arn'] if targets else 'UNKNOWN'
        except Exception:
            target_id = 'UNKNOWN'
            target_arn = 'UNKNOWN'

        payload_str = json.dumps(fixed)
        print(f'\n# Fix {rule_name}:')
        print(f'aws events put-targets --profile {PROFILE} --region {REGION} \\')
        print(f'  --rule "{rule_name}" \\')
        print(f'  --targets \'[{{"Id":"{target_id}","Arn":"{target_arn}","Input":{json.dumps(payload_str)}}}]\'')

print('\n' + '=' * 40)
sys.exit(1 if criticals else 0)
