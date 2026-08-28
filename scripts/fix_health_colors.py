#!/usr/bin/env python3
"""
fix_health_colors.py
Remove Amber/Yellow health color entries from coo-operational-analysis-prod.
The CST board only uses Green and Red — Amber/Yellow entries never match.
"""
import boto3, json

qs = boto3.Session(
    profile_name='AWSAdministratorAccess-961341524729',
    region_name='us-east-1'
).client('quicksight')

ACCOUNT = '961341524729'
ANALYSIS_ID = 'coo-operational-analysis-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
defn = resp['Definition']

fixes = 0
for sheet in defn['Sheets']:
    for v in sheet['Visuals']:
        for vtype, vdata in v.items():
            cfg = vdata.get('ChartConfiguration', {})

            # Remove Amber/Yellow from donut/pie ColorMap
            palette = cfg.get('VisualPalette', {})
            if 'ColorMap' in palette:
                before = len(palette['ColorMap'])
                palette['ColorMap'] = [
                    e for e in palette['ColorMap']
                    if e.get('Element', {}).get('FieldValue') not in ('Amber', 'Yellow')
                ]
                removed = before - len(palette['ColorMap'])
                if removed:
                    print(f'  {vdata.get("VisualId")}: removed {removed} ColorMap entries')
                    fixes += removed

            # Remove Amber/Yellow from table ConditionalFormatting
            cf = vdata.get('ConditionalFormatting', {})
            opts = cf.get('ConditionalFormattingOptions', [])
            if opts:
                before = len(opts)
                cf['ConditionalFormattingOptions'] = [
                    o for o in opts
                    if not any(
                        word in json.dumps(o.get('Row', {}).get('BackgroundColor', {}).get('Solid', {}).get('Expression', ''))
                        for word in ('Amber', 'Yellow')
                    )
                ]
                removed = before - len(cf['ConditionalFormattingOptions'])
                if removed:
                    print(f'  {vdata.get("VisualId")}: removed {removed} conditional formatting rules')
                    fixes += removed

print(f'Total fixes: {fixes}')

resp2 = qs.update_analysis(
    AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID,
    Name='COO Operational Analysis (prod)', ThemeArn=THEME_ARN, Definition=defn
)
print(f'Status: {resp2["Status"]}')
