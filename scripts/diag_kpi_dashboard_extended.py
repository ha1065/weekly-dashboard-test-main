import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='kpi-tracking-analysis-prod')['Definition']

# Dump raw sheet structure to understand where filter controls actually live
print('=== RAW SHEET KEYS ===')
for sheet in defn.get('Sheets', []):
    print(f"\n  Sheet: {sheet.get('SheetId')} — {sheet.get('Name','')}")
    print(f"    Top-level keys: {list(sheet.keys())}")
    print(f"    FilterControls count: {len(sheet.get('FilterControls', []))}")
    print(f"    Visuals count: {len(sheet.get('Visuals', []))}")
    print(f"    Layouts count: {len(sheet.get('Layouts', []))}")
    print(f"    SheetControlLayouts count: {len(sheet.get('SheetControlLayouts', []))}")
    # Dump raw FilterControls if any
    for i, fc in enumerate(sheet.get('FilterControls', [])):
        print(f"    FilterControl[{i}] keys: {list(fc.keys())}")
        print(f"      raw: {json.dumps(fc)[:300]}")

# Dump all parameter controls anywhere they might be — check inside Visuals too
print('\n=== CHECKING FOR PARAMETER CONTROLS IN VISUALS ===')
for sheet in defn.get('Sheets', []):
    for v in sheet.get('Visuals', []):
        vkeys = list(v.keys())
        if any('param' in k.lower() or 'control' in k.lower() for k in vkeys):
            print(f"  Sheet={sheet.get('SheetId')} visual keys: {vkeys}")

# Check ParameterControls directly on sheet level (alternate path)
print('\n=== CHECKING ParameterControls KEY ===')
for sheet in defn.get('Sheets', []):
    pcs = sheet.get('ParameterControls', [])
    if pcs:
        print(f"  Sheet {sheet.get('SheetId')} has {len(pcs)} ParameterControls")
        for pc in pcs:
            print(f"    {json.dumps(pc)[:300]}")

# Dump all KPI visuals in full (title + field wells) — not just headcount
print('\n=== ALL KPI VISUALS (ALL SHEETS) ===')
for sheet in defn.get('Sheets', []):
    for v in sheet.get('Visuals', []):
        kpi = v.get('KPIVisual', {})
        if kpi:
            title = kpi.get('Title', {}).get('FormatText', {}).get('PlainText', '')
            vis_id = kpi.get('VisualId', '')
            fws = kpi.get('ChartConfiguration', {}).get('FieldWells', {}).get('Values', [])
            print(f"  Sheet={sheet.get('SheetId')} VisualId={vis_id} Title='{title}'")
            for fw in fws:
                for ftype in ['NumericalMeasureField', 'CategoricalMeasureField', 'DateMeasureField']:
                    if ftype in fw:
                        col = fw[ftype].get('Column', {})
                        agg = fw[ftype].get('AggregationFunction', {})
                        print(f"    {ftype}: dataset={col.get('DataSetIdentifier')} column={col.get('ColumnName')} agg={agg}")

# Check for "headcount" column presence in kpi_snapshots dataset
print('\n=== SNAPSHOTS DATASET — HEADCOUNT-RELATED COLUMNS ===')
try:
    cols = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId='kpi-weekly-snapshots-prod')['DataSet']['OutputColumns']
    hc_cols = [c['Name'] for c in cols if 'head' in c['Name'].lower() or 'count' in c['Name'].lower() or 'staff' in c['Name'].lower()]
    print(f"  Headcount/count/staff columns: {hc_cols}")
except Exception as e:
    print(f"  ERROR: {e}")

# Check the compliance_pct_calc calculated field fully
print('\n=== FULL CALCULATED FIELDS ===')
for cf in defn.get('CalculatedFields', []):
    print(f"  Dataset={cf.get('DataSetIdentifier')} Name={cf.get('Name')}")
    print(f"    Expression: {cf.get('Expression')}")

# Check what aggregation the S1 snapshot KPI tiles use
print('\n=== S1 SNAPSHOT SHEET KPI TILES ===')
for sheet in defn.get('Sheets', []):
    if sheet.get('SheetId') == 'sheet-kpi-s1':
        for v in sheet.get('Visuals', []):
            kpi = v.get('KPIVisual', {})
            if kpi:
                title = kpi.get('Title', {}).get('FormatText', {}).get('PlainText', '')
                fws = kpi.get('ChartConfiguration', {}).get('FieldWells', {}).get('Values', [])
                comparison = kpi.get('ChartConfiguration', {}).get('KPIOptions', {}).get('Comparison', {})
                print(f"  Title='{title}'")
                for fw in fws:
                    for ftype in ['NumericalMeasureField', 'CategoricalMeasureField']:
                        if ftype in fw:
                            col = fw[ftype].get('Column', {})
                            agg = fw[ftype].get('AggregationFunction', {})
                            field_id = fw[ftype].get('FieldId', '')
                            print(f"    {ftype}: dataset={col.get('DataSetIdentifier')} column={col.get('ColumnName')} agg={agg} fieldId={field_id}")
                if comparison:
                    print(f"    Comparison: {json.dumps(comparison)[:200]}")
