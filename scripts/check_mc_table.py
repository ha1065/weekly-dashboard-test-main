#!/usr/bin/env python3
"""Check tbl-mc fields and mc_at_risk dataset columns."""
import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
lc = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('lambda')
ACCOUNT = '961341524729'

cached = json.loads(open('/Users/cdx/weekly-reporting/weekly-reporting/coo-analysis-live.json').read())['Definition']
sheet = next(s for s in cached['Sheets'] if s['SheetId'] == 'sheet-mc-delivery')
for v in sheet['Visuals']:
    tbl = v.get('TableVisual', {})
    if tbl.get('VisualId') == 'tbl-mc':
        print('=== GroupBy fields ===')
        for f in tbl['ChartConfiguration']['FieldWells']['TableAggregatedFieldWells']['GroupBy']:
            cdf = f.get('CategoricalDimensionField', {})
            print(f"  {cdf.get('FieldId')} → {cdf.get('Column', {}).get('ColumnName')} (ds: {cdf.get('Column', {}).get('DataSetIdentifier')})")
        print('\n=== Values fields ===')
        for f in tbl['ChartConfiguration']['FieldWells']['TableAggregatedFieldWells']['Values']:
            nmf = f.get('NumericalMeasureField', {})
            print(f"  {nmf.get('FieldId')} → {nmf.get('Column', {}).get('ColumnName')}")
        print('\n=== Current CF ===')
        print(json.dumps(tbl.get('ConditionalFormatting', 'NONE'), indent=2))
        break

# Check mc_at_risk dataset columns
def q(sql):
    r = lc.invoke(FunctionName='production-clockify-import',
                  Payload=json.dumps({'mode': 'run_query', 'sql': sql}).encode())
    return json.loads(r['Payload'].read())

print('\n=== mc_at_risk columns (vw_mc_projects_at_risk or similar) ===')
print(q("SELECT column_name FROM information_schema.columns WHERE table_name LIKE '%mc%risk%' OR table_name LIKE '%mc_at%' ORDER BY table_name, ordinal_position LIMIT 30"))

print('\n=== Distinct health_overall + customer_name sample ===')
print(q("SELECT DISTINCT health_overall, length(health_overall) FROM mc_ticket_activity_snapshot WHERE health_overall IS NOT NULL LIMIT 10"))
