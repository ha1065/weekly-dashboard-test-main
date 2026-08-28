import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='kpi-tracking-analysis-prod')['Definition']

# 1. List all ParameterDeclarations with their defaults
print('=== PARAMETERS ===')
for p in defn.get('ParameterDeclarations', []):
    for ptype in ['StringParameterDeclaration','DateTimeParameterDeclaration','IntegerParameterDeclaration']:
        if ptype in p:
            pd = p[ptype]
            print(f"  {pd['Name']}: default={pd.get('DefaultValues',{})}")

# 2. List all FilterGroups — show FilterId, Column, Configuration type, ScopeConfiguration
print('\n=== FILTER GROUPS ===')
for fg in defn.get('FilterGroups', []):
    print(f"  FilterGroupId: {fg['FilterGroupId']}")
    print(f"    Status: {fg.get('Status')}")
    print(f"    CrossDataset: {fg.get('CrossDataset')}")
    scope = fg.get('ScopeConfiguration',{})
    sheets = scope.get('SelectedSheets',{}).get('SheetVisualScopingConfigurations',[])
    for s in sheets:
        print(f"    Scope: sheet={s.get('SheetId')} scope={s.get('Scope')}")
    for f in fg.get('Filters',[]):
        cf = f.get('CategoryFilter',{})
        col = cf.get('Column',{})
        config = cf.get('Configuration',{})
        custom = config.get('CustomFilterConfiguration',{})
        filterlist = config.get('FilterListConfiguration',{})
        print(f"    Filter: column={col.get('ColumnName')} dataset={col.get('DataSetIdentifier')}")
        if custom:
            print(f"      CustomFilter: MatchOperator={custom.get('MatchOperator')} ParameterName={custom.get('ParameterName')} NullOption={custom.get('NullOption')} SelectAllOptions={custom.get('SelectAllOptions')}")
        if filterlist:
            print(f"      FilterList: SelectAllOptions={filterlist.get('SelectAllOptions')} Values={filterlist.get('CategoryValues')} NullOption={filterlist.get('NullOption')}")

# 3. For each sheet: list all FilterControl types and their source parameters
print('\n=== FILTER CONTROLS PER SHEET ===')
for sheet in defn.get('Sheets', []):
    print(f"  Sheet: {sheet.get('SheetId')} — {sheet.get('Name','')}")
    for fc in sheet.get('FilterControls', []):
        for fctype in ['ParameterControl','FilterControl']:
            # Parameter controls
            for pctype in ['ParameterDropDownControl','ParameterTextFieldControl','ParameterListControl','ParameterSliderControl','ParameterDateTimePickerControl']:
                if pctype in fc:
                    pc = fc[pctype]
                    print(f"    ParameterControl({pctype}): SourceParameterName={pc.get('SourceParameterName')} Title={pc.get('Title')}")
        # Direct filter controls  
        for fctype2 in ['DropDownControl','TextFieldControl','ListControl','DateTimePicker','Slider','RelativeDateTimeControl']:
            if fctype2 in fc:
                fcc = fc[fctype2]
                src = fcc.get('SourceFilterId','')
                print(f"    FilterControl({fctype2}): SourceFilterId={src} Title={fcc.get('Title','')}")

# 4. Check headcount — what aggregation is used on headcount KPI tiles
print('\n=== HEADCOUNT KPI TILES ===')
for sheet in defn.get('Sheets', []):
    for v in sheet.get('Visuals', []):
        kpi = v.get('KPIVisual',{})
        if kpi:
            title = kpi.get('Title',{}).get('FormatText',{}).get('PlainText','')
            if 'head' in title.lower() or 'Head' in title:
                fws = kpi.get('ChartConfiguration',{}).get('FieldWells',{}).get('Values',[])
                for fw in fws:
                    for ftype in ['NumericalMeasureField','CategoricalMeasureField']:
                        if ftype in fw:
                            col = fw[ftype].get('Column',{}).get('ColumnName','')
                            agg = fw[ftype].get('AggregationFunction',{})
                            print(f"  Sheet={sheet.get('SheetId')} Title={title} Column={col} Aggregation={agg}")

# 5. List all calculated fields
print('\n=== CALCULATED FIELDS ===')
for cf in defn.get('CalculatedFields', []):
    print(f"  Dataset={cf.get('DataSetIdentifier')} Name={cf.get('Name')} Expression={cf.get('Expression')[:80]}")

# 6. Check what the kpi_practice and kpi_staff datasets actually have
# Check column names
print('\n=== DATASET COLUMNS ===')
for ds_id in ['kpi-practice-weekly-prod', 'kpi-staff-weekly-prod', 'kpi-weekly-snapshots-prod']:
    try:
        cols = qs.describe_data_set(AwsAccountId=ACCOUNT, DataSetId=ds_id)['DataSet']['OutputColumns']
        print(f"  {ds_id}: {[c['Name'] for c in cols]}")
    except Exception as e:
        print(f"  {ds_id}: ERROR {e}")
