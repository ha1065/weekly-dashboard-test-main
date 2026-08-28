#!/usr/bin/env python3
"""
Diagnose and fix escalation column conditional formatting.
Prints current CF state, then applies fix using correct expression syntax.
"""
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

    # Print current state
    print('=== Current TableOptions ===')
    print(json.dumps(tbl['ChartConfiguration'].get('TableOptions', {}), indent=2))
    print('\n=== Current ConditionalFormatting ===')
    print(json.dumps(tbl.get('ConditionalFormatting', {}), indent=2))

    # Fix 1: Ensure row alternate colors disabled
    tbl['ChartConfiguration']['TableOptions']['RowAlternateColorOptions'] = {'Status': 'DISABLED'}

    # Fix 2: Rebuild all conditional formatting with correct syntax
    # For aggregated tables, use the field's column name directly (no braces needed in some cases)
    # Try both row-level and cell-level formatting
    tbl['ConditionalFormatting'] = {
        'ConditionalFormattingOptions': [
            # Health overall — row color
            {'Row': {'BackgroundColor': {'Solid': {
                'Expression': "locate({health}, 'Red') > 0",
                'Color': '#FADBD8'
            }}}},
            {'Row': {'BackgroundColor': {'Solid': {
                'Expression': "locate({health}, 'Green') > 0",
                'Color': '#D5F5E3'
            }}}},
            {'Row': {'BackgroundColor': {'Solid': {
                'Expression': "locate({health}, 'Yellow') > 0",
                'Color': '#FEF3CD'
            }}}},
            # Budget health cell
            {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_budget} = 'Red'", 'Color': '#D74018'
            }}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_budget} = 'Yellow'", 'Color': '#FF9B00'
            }}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g6', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_budget} = 'Green'", 'Color': '#33A94F'
            }}}}},
            # Schedule health cell
            {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_schedule} = 'Red'", 'Color': '#D74018'
            }}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_schedule} = 'Yellow'", 'Color': '#FF9B00'
            }}}}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g7', 'TextFormat': {'BackgroundColor': {'Solid': {
                'Expression': "{health_schedule} = 'Green'", 'Color': '#33A94F'
            }}}}},
            # Escalation cell
            {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {
                'BackgroundColor': {'Solid': {
                    'Expression': "{escalation} = 'Yes'", 'Color': '#D74018'
                }},
                'TextColor': {'Solid': {
                    'Expression': "{escalation} = 'Yes'", 'Color': '#FFFFFF'
                }}
            }}},
            {'Cell': {'FieldId': 'tbl-ps-projects-g8', 'TextFormat': {
                'BackgroundColor': {'Solid': {
                    'Expression': "{escalation} = 'No'", 'Color': '#33A94F'
                }},
                'TextColor': {'Solid': {
                    'Expression': "{escalation} = 'No'", 'Color': '#FFFFFF'
                }}
            }}},
        ]
    }
    print('\n✅ Rebuilt all conditional formatting')
    break

resp2 = qs.update_analysis(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn)
print(f'Status: {resp2["Status"]}')
