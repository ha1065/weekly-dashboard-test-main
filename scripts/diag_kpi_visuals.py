import boto3, json
qs = boto3.Session(profile_name='AWSAdministratorAccess-961341524729', region_name='us-east-1').client('quicksight')
ACCOUNT = '961341524729'
defn = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId='kpi-tracking-analysis-prod')['Definition']

for sheet in defn.get('Sheets', []):
    print(f'\n=== Sheet: {sheet["SheetId"]} ({sheet.get("Name","")}) ===')
    for v in sheet.get('Visuals', []):
        for vtype in ['KPIVisual','BarChartVisual','TableVisual','LineChartVisual']:
            if vtype in v:
                vid = v[vtype].get('VisualId','?')
                title = v[vtype].get('Title',{}).get('FormatText',{}).get('PlainText','?')
                print(f'  {vtype}: {vid} title="{title}"')
                
                # For KPI tiles - show aggregation
                if vtype == 'KPIVisual':
                    fws = v[vtype].get('ChartConfiguration',{}).get('FieldWells',{}).get('Values',[])
                    for fw in fws:
                        for ft in ['NumericalMeasureField','CategoricalMeasureField']:
                            if ft in fw:
                                col = fw[ft].get('Column',{}).get('ColumnName','?')
                                agg = fw[ft].get('AggregationFunction',{})
                                print(f'    col={col} agg={agg}')
                
                # For bar charts - show colors
                if vtype == 'BarChartVisual':
                    cfg = v[vtype].get('ChartConfiguration',{})
                    palette = cfg.get('VisualPalette',{})
                    color_map = palette.get('ColorMap',[])
                    chart_color = palette.get('ChartColor','')
                    fw = cfg.get('FieldWells',{}).get('BarChartAggregatedFieldWells',{})
                    colors_vals = fw.get('Colors',[])
                    values = fw.get('Values',[])
                    cats = fw.get('Category',[])
                    print(f'    ChartColor={chart_color} ColorMap={json.dumps(color_map)[:200]}')
                    for val in values:
                        for ft in ['NumericalMeasureField','CategoricalMeasureField']:
                            if ft in val:
                                print(f'    value col={val[ft].get("Column",{}).get("ColumnName","?")} fid={val[ft].get("FieldId","?")}')                    
                    for cat in cats:
                        for ft in ['DateDimensionField','CategoricalDimensionField']:
                            if ft in cat:
                                print(f'    category col={cat[ft].get("Column",{}).get("ColumnName","?")} fid={cat[ft].get("FieldId","?")}')                    
                
                # For table visuals - show columns
                if vtype == 'TableVisual':
                    cfg = v[vtype].get('ChartConfiguration',{})
                    # Unaggregated
                    unagg = cfg.get('FieldWells',{}).get('TableUnaggregatedFieldWells',{}).get('Values',[])
                    for f in unagg:
                        if 'UnaggregatedField' in f:
                            col = f['UnaggregatedField'].get('Column',{}).get('ColumnName','?')
                            fid = f['UnaggregatedField'].get('FieldId','?')
                            print(f'    unagg col={col} fid={fid}')
                    # Aggregated
                    agg_gby = cfg.get('FieldWells',{}).get('TableAggregatedFieldWells',{}).get('GroupBy',[])
                    agg_vals = cfg.get('FieldWells',{}).get('TableAggregatedFieldWells',{}).get('Values',[])
                    for f in agg_gby:
                        for ft in ['CategoricalDimensionField','DateDimensionField']:
                            if ft in f:
                                col = f[ft].get('Column',{}).get('ColumnName','?')
                                print(f'    groupby col={col}')
                    for f in agg_vals:
                        for ft in ['NumericalMeasureField','CategoricalMeasureField']:
                            if ft in f:
                                col = f[ft].get('Column',{}).get('ColumnName','?')
                                agg = f[ft].get('AggregationFunction',{})
                                print(f'    value col={col} agg={agg}')
