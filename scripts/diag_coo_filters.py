import boto3, json

qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'

defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='coo-operational-analysis-prod')['Definition']

# 1. All parameters and their defaults
print('=== PARAMETERS ===')
for p in defn.get('ParameterDeclarations', []):
    for ptype in ['StringParameterDeclaration','DateTimeParameterDeclaration','IntegerParameterDeclaration','DecimalParameterDeclaration']:
        if ptype in p:
            pd = p[ptype]
            print(f"  {ptype}: Name={pd['Name']} Default={pd.get('DefaultValues',{})} AllowedValues={pd.get('ValueWhenUnset',{})}")

# 2. ALL FilterGroups — full detail
print('\n=== ALL FILTER GROUPS (FULL DETAIL) ===')
for fg in defn.get('FilterGroups', []):
    print(f"\n  FilterGroupId: {fg['FilterGroupId']}")
    print(f"  Status: {fg.get('Status')} CrossDataset: {fg.get('CrossDataset')}")
    scope = fg.get('ScopeConfiguration',{})
    if 'AllSheets' in scope:
        print(f"  Scope: ALL_SHEETS")
    else:
        for s in scope.get('SelectedSheets',{}).get('SheetVisualScopingConfigurations',[]):
            print(f"  Scope: sheet={s.get('SheetId')} scope={s.get('Scope')} visuals={s.get('VisualIds',[])}")
    for f in fg.get('Filters',[]):
        # TimeEqualityFilter
        tf = f.get('TimeEqualityFilter',{})
        if tf:
            print(f"  Filter type: TimeEqualityFilter")
            print(f"    Column: {tf.get('Column',{}).get('ColumnName')} dataset={tf.get('Column',{}).get('DataSetIdentifier')}")
            print(f"    ParameterName: {tf.get('ParameterName')} TimeGranularity: {tf.get('TimeGranularity')}")
        # CategoryFilter
        cf = f.get('CategoryFilter',{})
        if cf:
            print(f"  Filter type: CategoryFilter")
            print(f"    Column: {cf.get('Column',{}).get('ColumnName')} dataset={cf.get('Column',{}).get('DataSetIdentifier')}")
            config = cf.get('Configuration',{})
            custom = config.get('CustomFilterConfiguration',{})
            filterlist = config.get('FilterListConfiguration',{})
            customlist = config.get('CustomFilterListConfiguration',{})
            if custom:
                print(f"    CustomFilterConfiguration: MatchOperator={custom.get('MatchOperator')} ParameterName={custom.get('ParameterName')} NullOption={custom.get('NullOption')} SelectAllOptions={custom.get('SelectAllOptions')}")
            if filterlist:
                print(f"    FilterListConfiguration: SelectAllOptions={filterlist.get('SelectAllOptions')} Values={filterlist.get('CategoryValues')} NullOption={filterlist.get('NullOption')}")
            if customlist:
                print(f"    CustomFilterListConfiguration: MatchOperator={customlist.get('MatchOperator')} NullOption={customlist.get('NullOption')} Values={customlist.get('CategoryValues')}")
        # NumericRangeFilter
        nf = f.get('NumericRangeFilter',{})
        if nf:
            print(f"  Filter type: NumericRangeFilter col={nf.get('Column',{}).get('ColumnName')}")
        # RelativeDatesFilter
        rf = f.get('RelativeDatesFilter',{})
        if rf:
            print(f"  Filter type: RelativeDatesFilter col={rf.get('Column',{}).get('ColumnName')} AnchorDateType={rf.get('AnchorDateConfiguration',{}).get('AnchorDateType')} RelativeDateType={rf.get('RelativeDateType')} TimeGranularity={rf.get('TimeGranularity')}")

# 3. ParameterControls on each sheet
print('\n=== PARAMETER CONTROLS PER SHEET ===')
for sheet in defn.get('Sheets', []):
    pcs = sheet.get('ParameterControls', [])
    fcs = sheet.get('FilterControls', [])
    if pcs or fcs:
        print(f"\n  Sheet: {sheet.get('SheetId')} — {sheet.get('Name','')}")
        for pc in pcs:
            for pctype in ['Dropdown','TextField','List','Slider','DateTimePicker']:
                if pctype in pc:
                    p = pc[pctype]
                    opts = p.get('SelectableValues',{})
                    print(f"    ParameterControl.{pctype}: Id={p.get('ParameterControlId')} Title={p.get('Title')} Source={p.get('SourceParameterName')} Values={opts}")
        for fc in fcs:
            for fctype in ['Dropdown','TextField','List','DateTimePicker','Slider','RelativeDateTimeControl']:
                if fctype in fc:
                    f = fc[fctype]
                    print(f"    FilterControl.{fctype}: Id={f.get('FilterControlId')} Title={f.get('Title')} SourceFilterId={f.get('SourceFilterId')}")

# 4. SheetControlLayouts
print('\n=== SHEET CONTROL LAYOUTS ===')
for sheet in defn.get('Sheets', []):
    scl = sheet.get('SheetControlLayouts', [])
    if scl:
        print(f"  Sheet {sheet.get('SheetId')}: SheetControlLayouts={json.dumps(scl, indent=4)[:500]}")
    else:
        print(f"  Sheet {sheet.get('SheetId')}: NO SheetControlLayouts")
