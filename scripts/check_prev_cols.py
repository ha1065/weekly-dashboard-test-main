#!/usr/bin/env python3
"""Find all _prev column references in the analysis."""
import boto3, json, re

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='coo-operational-analysis-prod')
defn_str = json.dumps(resp['Definition'], default=str)

# Find all _prev column references
prev_cols = set(re.findall(r'"ColumnName":\s*"([^"]*_prev[^"]*)"', defn_str))
wow_cols = set(re.findall(r'"ColumnName":\s*"([^"]*_wow[^"]*)"', defn_str))
print('_prev columns referenced in analysis:')
for c in sorted(prev_cols): print(f'  {c}')
print('\n_wow columns referenced in analysis:')
for c in sorted(wow_cols): print(f'  {c}')

# Also check calculated fields
calc = resp['Definition'].get('CalculatedFields', [])
print(f'\nCalculated fields: {[c["Name"] for c in calc]}')
