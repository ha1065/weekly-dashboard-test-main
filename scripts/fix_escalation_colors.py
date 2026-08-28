#!/usr/bin/env python3
"""Add conditional formatting to the escalation column in tbl-ps-projects."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

sheet = next(s for s in defn['Sheets'] if s['SheetId'] == 'sheet-ps-delivery')

for v in sheet['Visuals']:
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') != 'tbl-ps-projects':
        continue

    cf = tbl.setdefault('ConditionalFormatting', {})
    opts = cf.setdefault('ConditionalFormattingOptions', [])

    # Remove any existing escalation formatting to avoid duplicates
    opts[:] = [o for o in opts if not (
        o.get('Cell', {}).get('FieldId', '').startswith('tbl-ps-projects-g8')
    )]

    # Yes = Red background (escalation active)
    opts.append({'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {
        'BackgroundColor': {'Solid': {
            'Expression': '{escalation} = "Yes"',
            'Color': '#D74018'
        }},
        'TextColor': {'Solid': {
            'Expression': '{escalation} = "Yes"',
            'Color': '#FFFFFF'
        }}
    }}})

    # No = Green background
    opts.append({'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {
        'BackgroundColor': {'Solid': {
            'Expression': '{escalation} = "No"',
            'Color': '#33A94F'
        }},
        'TextColor': {'Solid': {
            'Expression': '{escalation} = "No"',
            'Color': '#FFFFFF'
        }}
    }}})

    print(f'Added escalation conditional formatting to tbl-ps-projects')
    break

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
