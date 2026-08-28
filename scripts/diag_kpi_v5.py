import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='kpi-tracking-analysis-prod')['Definition']

# ── 1. ALL FILTER GROUPS (full detail) ─────────────────────────────────────
print('=== ALL FILTER GROUPS ===')
for fg in defn.get('FilterGroups', []):
    print(f"\nFilterGroupId: {fg['FilterGroupId']}  Status={fg.get('Status')}  Cross={fg.get('CrossDataset')}")
    scope = fg.get('ScopeConfiguration', {})
    if 'AllSheets' in scope:
        print(f"  Scope: ALL_SHEETS")
    else:
        for s in scope.get('SelectedSheets', {}).get('SheetVisualScopingConfigurations', []):
            print(f"  Scope: sheet={s['SheetId']}  scope={s['Scope']}  visuals={s.get('VisualIds', [])}")
    for f in fg.get('Filters', []):
        for ftype in ['RelativeDatesFilter', 'TimeEqualityFilter', 'TimeRangeFilter', 'CategoryFilter', 'NumericEqualityFilter']:
            if ftype in f:
                fd = f[ftype]
                col = fd.get('Column', {})
                print(f"  Filter type : {ftype}")
                print(f"    FilterId  : {fd.get('FilterId')}")
                print(f"    Column    : {col.get('ColumnName')}  dataset={col.get('DataSetIdentifier')}")
                if ftype == 'RelativeDatesFilter':
                    print(f"    AnchorDateConfiguration : {fd.get('AnchorDateConfiguration', {})}")
                    print(f"    RelativeDateType        : {fd.get('RelativeDateType')}")
                    print(f"    RelativeDateValue       : {fd.get('RelativeDateValue')}")
                    print(f"    TimeGranularity         : {fd.get('TimeGranularity')}")
                    print(f"    MinimumGranularity      : {fd.get('MinimumGranularity')}")
                    print(f"    NullOption              : {fd.get('NullOption')}")
                    print(f"    ExcludePeriodConfiguration: {fd.get('ExcludePeriodConfiguration')}")
                if ftype == 'TimeRangeFilter':
                    print(f"    RangeMinimumValue : {fd.get('RangeMinimumValue')}")
                    print(f"    RangeMaximumValue : {fd.get('RangeMaximumValue')}")
                    print(f"    NullOption        : {fd.get('NullOption')}")
                if ftype == 'CategoryFilter':
                    config = fd.get('Configuration', {})
                    fl = config.get('FilterListConfiguration', {})
                    print(f"    SelectAllOptions : {fl.get('SelectAllOptions')}  MatchOperator : {fl.get('MatchOperator')}")
                    print(f"    CategoryValues   : {fl.get('CategoryValues')}")

# ── 2. ALL VISUAL IDs PER SHEET ───────────────────────────────────────────
print('\n=== ALL VISUAL IDs PER SHEET ===')
all_visual_ids = {}  # sheet_id -> list of visual_ids
for sheet in defn.get('Sheets', []):
    sheet_id = sheet.get('SheetId')
    sheet_name = sheet.get('Name', '')
    print(f"\nSheet: {sheet_id}  ({sheet_name})")
    ids = []
    for v in sheet.get('Visuals', []):
        for vtype in ['KPIVisual', 'LineChartVisual', 'BarChartVisual', 'TableVisual',
                      'PieChartVisual', 'ComboChartVisual', 'ScatterPlotVisual',
                      'InsightVisual', 'GaugeChartVisual', 'FilledMapVisual']:
            if vtype in v:
                vdata = v[vtype]
                vid = vdata.get('VisualId', '?')
                title_obj = vdata.get('Title', {})
                title = (title_obj.get('FormatText', {}) or {}).get('PlainText', '') or \
                        (title_obj.get('FormatText', {}) or {}).get('RichText', '') or '(no title)'
                print(f"  {vtype:22s}  {vid:50s}  — {title}")
                ids.append(vid)
    all_visual_ids[sheet_id] = ids

# ── 3. FILTER-SCOPE CROSS-REFERENCE ───────────────────────────────────────
print('\n=== FILTER SCOPE vs VISUAL MEMBERSHIP ===')
for fg in defn.get('FilterGroups', []):
    fgid = fg['FilterGroupId']
    scope = fg.get('ScopeConfiguration', {})
    if 'AllSheets' in scope:
        print(f"\nFilterGroup {fgid}: ALL_SHEETS (every visual is in scope)")
        continue
    for s in scope.get('SelectedSheets', {}).get('SheetVisualScopingConfigurations', []):
        sid = s['SheetId']
        sc  = s['Scope']
        scoped_ids = s.get('VisualIds', [])
        all_ids    = all_visual_ids.get(sid, [])
        excluded   = [v for v in all_ids if v not in scoped_ids] if sc == 'SELECTED_VISUALS' else []
        print(f"\nFilterGroup {fgid}  sheet={sid}  scope={sc}")
        if sc == 'SELECTED_VISUALS':
            print(f"  IN  scope ({len(scoped_ids)}): {scoped_ids}")
            print(f"  OUT scope ({len(excluded)}): {excluded}")
        else:
            print(f"  (ALL_VISUALS on this sheet)")

# ── 4. DATASET COLUMN TYPES ───────────────────────────────────────────────
print('\n=== DATASET COLUMN TYPES (week_start) ===')
for ds in defn.get('DataSetIdentifierDeclarations', []):
    dsid  = ds.get('Identifier')
    dsarn = ds.get('DataSetArn', '')
    # extract dataset id from arn: arn:aws:quicksight:...:dataset/<id>
    dsid_real = dsarn.split('/')[-1] if '/' in dsarn else ''
    print(f"\nDataset identifier: {dsid}  arn={dsarn}")
    if dsid_real:
        try:
            ds_detail = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId=dsid_real)
            for name, col in ds_detail['DataSet'].get('OutputColumns', {}).items() if hasattr(ds_detail['DataSet'].get('OutputColumns', {}), 'items') else []:
                pass
            # OutputColumns is a list
            for col in ds_detail['DataSet'].get('OutputColumns', []):
                if 'week' in col.get('Name', '').lower() or 'date' in col.get('Name', '').lower():
                    print(f"  Column: {col['Name']:30s}  Type: {col.get('Type')}  SubType: {col.get('SubType', '')}")
        except Exception as e:
            print(f"  (could not describe dataset: {e})")

# ── 5. SPICE last refresh ─────────────────────────────────────────────────
print('\n=== SPICE LAST REFRESH ===')
for ds in defn.get('DataSetIdentifierDeclarations', []):
    dsarn = ds.get('DataSetArn', '')
    dsid_real = dsarn.split('/')[-1] if '/' in dsarn else ''
    if dsid_real:
        try:
            ing = qs.list_ingestions(AwsAccountId=ACCOUNT, DataSetId=dsid_real)
            ingestions = ing.get('Ingestions', [])
            if ingestions:
                latest = sorted(ingestions, key=lambda x: x.get('CreatedTime', ''), reverse=True)[0]
                print(f"  Dataset {ds.get('Identifier'):20s}: last={latest.get('CreatedTime')}  status={latest.get('IngestionStatus')}  rows={latest.get('RowInfo', {}).get('RowsIngested', '?')}")
        except Exception as e:
            print(f"  Dataset {ds.get('Identifier')}: (error: {e})")

print('\n=== DONE ===')
