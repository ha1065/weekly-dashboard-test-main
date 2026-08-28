"""
patch_kpi_sheet2_staff.py

Rebuilds Sheet 2 (Practice Scorecard) of the KPI Tracking Dashboard to use
kpi_staff dataset instead of kpi_practice. All metrics now aggregate correctly
at any filter level (All, LoB, Practice, individual) because kpi_staff has
one row per (user x week), not pre-aggregated per-practice rows.

Before:
  - kpi-s2-headcount: MAX(headcount) from kpi_practice  → wrong when 'All' selected
  - All other metrics: various columns from kpi_practice

After:
  - kpi-s2-headcount: DISTINCT_COUNT(user_name) from kpi_staff  → always correct
  - kpi-s2-billable: AVERAGE(billable_util_pct) from kpi_staff
  - kpi-s2-productive: AVERAGE(productive_util_pct) from kpi_staff
  - kpi-s2-compliance: AVERAGE(compliance_pct_calc) from kpi_staff
  - kpi-s2-hours: SUM(billable_hours) from kpi_staff
  - bar-s2-util: AVERAGE(billable_util_pct) by practice_alignment from kpi_staff
  - bar-s2-compliance: AVERAGE(compliance_pct_calc) by practice_alignment from kpi_staff
  - chart-s2-util-trend: AVERAGE(billable_util_pct) by week_start, color=practice_alignment
  - chart-s2-compliance-trend: AVERAGE(compliance_pct_calc) by week_start, color=line_of_business
  - FilterGroups fg-s2-*: dataset changed from kpi_practice → kpi_staff
"""

import boto3
import json
import copy

ACCOUNT = '961341524729'
ANALYSIS_ID = 'kpi-tracking-analysis-prod'
DASHBOARD_ID = 'kpi-tracking-dashboard-prod'
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'
DATASET = 'kpi_staff'
SHEET_ID = 'sheet-kpi-s2'

qs = boto3.Session(
    profile_name='AWSAdministratorAccess-961341524729',
    region_name='us-east-1'
).client('quicksight')


# ---------------------------------------------------------------------------
# Visual builders
# ---------------------------------------------------------------------------

def make_kpi_headcount():
    """DISTINCT_COUNT(user_name) — correct headcount at any filter level."""
    return {
        'KPIVisual': {
            'VisualId': 'kpi-s2-headcount',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Headcount'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{
                        'CategoricalMeasureField': {
                            'FieldId': 'kpi-s2-hc-v',
                            'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'user_name'},
                            'AggregationFunction': 'DISTINCT_COUNT'
                        }
                    }],
                    'TargetValues': [],
                    'TrendGroups': []
                },
                'SortConfiguration': {},
                'KPIOptions': {
                    'PrimaryValueDisplayType': 'ACTUAL',
                    'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE'}
                }
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }


def make_kpi_hours():
    """SUM(billable_hours) — total billable hours for selected period."""
    return {
        'KPIVisual': {
            'VisualId': 'kpi-s2-hours',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Total Billable Hours'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{
                        'NumericalMeasureField': {
                            'FieldId': 'kpi-s2-bh-v',
                            'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'billable_hours'},
                            'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}
                        }
                    }],
                    'TargetValues': [],
                    'TrendGroups': []
                },
                'SortConfiguration': {},
                'KPIOptions': {
                    'PrimaryValueDisplayType': 'ACTUAL',
                    'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE'}
                }
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }


def make_kpi_billable():
    """AVERAGE(billable_util_pct) — weighted average handled at the row level."""
    return {
        'KPIVisual': {
            'VisualId': 'kpi-s2-billable',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Billable Utilization %'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{
                        'NumericalMeasureField': {
                            'FieldId': 'kpi-s2-bu-v',
                            'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'billable_util_pct'},
                            'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                        }
                    }],
                    'TargetValues': [],
                    'TrendGroups': []
                },
                'SortConfiguration': {},
                'KPIOptions': {
                    'PrimaryValueDisplayType': 'ACTUAL',
                    'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE'}
                }
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }


def make_kpi_compliance():
    """AVERAGE(compliance_pct_calc) — reuses existing calculated field {is_compliant}*100."""
    return {
        'KPIVisual': {
            'VisualId': 'kpi-s2-compliance',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Timesheet Compliance %'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{
                        'NumericalMeasureField': {
                            'FieldId': 'kpi-s2-comp-v',
                            'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'compliance_pct_calc'},
                            'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                        }
                    }],
                    'TargetValues': [],
                    'TrendGroups': []
                },
                'SortConfiguration': {},
                'KPIOptions': {
                    'PrimaryValueDisplayType': 'ACTUAL',
                    'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE'}
                }
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }


def make_kpi_productive():
    """AVERAGE(productive_util_pct) — productive utilisation."""
    return {
        'KPIVisual': {
            'VisualId': 'kpi-s2-productive-util',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Productive Util %'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{
                        'NumericalMeasureField': {
                            'FieldId': 'kpi-s2-pu-v',
                            'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'productive_util_pct'},
                            'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                        }
                    }],
                    'TargetValues': [],
                    'TrendGroups': []
                },
                'SortConfiguration': {},
                'KPIOptions': {
                    'PrimaryValueDisplayType': 'ACTUAL',
                    'Sparkline': {'Visibility': 'HIDDEN', 'Type': 'LINE'}
                }
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }


def make_bar_util():
    """Horizontal bar: AVERAGE(billable_util_pct) by practice_alignment, 75% reference line."""
    return {
        'BarChartVisual': {
            'VisualId': 'bar-s2-util',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Billable Utilization % by Practice'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{
                            'CategoricalDimensionField': {
                                'FieldId': 'bar-s2-util-cat',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'practice_alignment'}
                            }
                        }],
                        'Values': [{
                            'NumericalMeasureField': {
                                'FieldId': 'bar-s2-util-val',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'billable_util_pct'},
                                'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                            }
                        }],
                        'Colors': []
                    }
                },
                'SortConfiguration': {
                    'CategoryItemsLimit': {'OtherCategories': 'INCLUDE'},
                    'CategorySort': [{
                        'ColumnSort': {
                            'SortBy': {'DataSetIdentifier': DATASET, 'ColumnName': 'billable_util_pct'},
                            'Direction': 'DESC',
                            'AggregationFunction': {
                                'NumericalAggregationFunction': {
                                    'SimpleNumericalAggregation': 'AVERAGE'
                                }
                            }
                        }
                    }]
                },
                'Orientation': 'HORIZONTAL',
                'BarsArrangement': 'CLUSTERED',
                'VisualPalette': {'ChartColor': '#0089DD'},
                'ReferenceLines': [{
                    'Status': 'ENABLED',
                    'DataConfiguration': {
                        'StaticConfiguration': {'Value': 75.0},
                        'AxisBinding': 'PRIMARY_YAXIS',
                        'SeriesType': 'BAR'
                    },
                    'StyleConfiguration': {'Pattern': 'DASHED', 'Color': '#D74018'},
                    'LabelConfiguration': {
                        'CustomLabelConfiguration': {'CustomLabel': 'Target 75%'},
                        'FontConfiguration': {'FontSize': {'Relative': 'MEDIUM'}},
                        'HorizontalPosition': 'RIGHT',
                        'VerticalPosition': 'ABOVE'
                    }
                }],
                'Legend': {'Visibility': 'VISIBLE', 'Position': 'BOTTOM'},
                'DataLabels': {'Visibility': 'VISIBLE', 'Overlap': 'DISABLE_OVERLAP'}
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }


def make_bar_compliance():
    """Horizontal bar: AVERAGE(compliance_pct_calc) by practice_alignment, 95% reference line."""
    return {
        'BarChartVisual': {
            'VisualId': 'bar-s2-compliance',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Compliance % by Practice'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{
                            'CategoricalDimensionField': {
                                'FieldId': 'bar-s2-comp-cat',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'practice_alignment'}
                            }
                        }],
                        'Values': [{
                            'NumericalMeasureField': {
                                'FieldId': 'bar-s2-comp-val',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'compliance_pct_calc'},
                                'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                            }
                        }],
                        'Colors': []
                    }
                },
                'SortConfiguration': {
                    'CategoryItemsLimit': {'OtherCategories': 'INCLUDE'},
                    'CategorySort': [{
                        'ColumnSort': {
                            'SortBy': {'DataSetIdentifier': DATASET, 'ColumnName': 'compliance_pct_calc'},
                            'Direction': 'DESC',
                            'AggregationFunction': {
                                'NumericalAggregationFunction': {
                                    'SimpleNumericalAggregation': 'AVERAGE'
                                }
                            }
                        }
                    }]
                },
                'Orientation': 'HORIZONTAL',
                'BarsArrangement': 'CLUSTERED',
                'VisualPalette': {'ChartColor': '#0089DD'},
                'ReferenceLines': [{
                    'Status': 'ENABLED',
                    'DataConfiguration': {
                        'StaticConfiguration': {'Value': 95.0},
                        'AxisBinding': 'PRIMARY_YAXIS',
                        'SeriesType': 'BAR'
                    },
                    'StyleConfiguration': {'Pattern': 'DASHED', 'Color': '#D74018'},
                    'LabelConfiguration': {
                        'CustomLabelConfiguration': {'CustomLabel': 'Target 95%'},
                        'FontConfiguration': {'FontSize': {'Relative': 'MEDIUM'}},
                        'HorizontalPosition': 'RIGHT',
                        'VerticalPosition': 'ABOVE'
                    }
                }],
                'Legend': {'Visibility': 'VISIBLE', 'Position': 'BOTTOM'},
                'DataLabels': {'Visibility': 'VISIBLE', 'Overlap': 'DISABLE_OVERLAP'}
            },
            'Actions': [],
            'ColumnHierarchies': []
        }
    }


def make_line_util():
    """Line chart: AVERAGE(billable_util_pct) over week_start, colored by practice_alignment."""
    return {
        'LineChartVisual': {
            'VisualId': 'chart-s2-util-trend',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Billable Utilization % Trend by Practice'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{
                            'DateDimensionField': {
                                'FieldId': 'chart-s2-ut-x',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'week_start'},
                                'DateGranularity': 'WEEK',
                                'HierarchyId': 'chart-s2-ut-x'
                            }
                        }],
                        'Values': [{
                            'NumericalMeasureField': {
                                'FieldId': 'chart-s2-ut-val',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'billable_util_pct'},
                                'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                            }
                        }],
                        'Colors': [{
                            'CategoricalDimensionField': {
                                'FieldId': 'chart-s2-ut-color',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'practice_alignment'}
                            }
                        }]
                    }
                },
                'SortConfiguration': {},
                'Type': 'LINE',
                'Legend': {'Visibility': 'VISIBLE', 'Position': 'BOTTOM'},
                'ReferenceLines': [{
                    'Status': 'ENABLED',
                    'DataConfiguration': {
                        'StaticConfiguration': {'Value': 75.0},
                        'AxisBinding': 'PRIMARY_YAXIS',
                        'SeriesType': 'LINE'
                    },
                    'StyleConfiguration': {'Pattern': 'DASHED', 'Color': '#666666'},
                    'LabelConfiguration': {
                        'CustomLabelConfiguration': {'CustomLabel': 'Target 75%'},
                        'FontConfiguration': {'FontSize': {'Relative': 'MEDIUM'}},
                        'HorizontalPosition': 'RIGHT',
                        'VerticalPosition': 'ABOVE'
                    }
                }]
            },
            'Actions': [],
            'ColumnHierarchies': [{
                'DateTimeHierarchy': {
                    'HierarchyId': 'chart-s2-ut-x',
                    'DrillDownFilters': []
                }
            }]
        }
    }


def make_line_compliance():
    """Line chart: AVERAGE(compliance_pct_calc) over week_start, colored by line_of_business."""
    return {
        'LineChartVisual': {
            'VisualId': 'chart-s2-compliance-trend',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Compliance % Trend by Line of Business'}},
            'Subtitle': {'Visibility': 'HIDDEN'},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{
                            'DateDimensionField': {
                                'FieldId': 'chart-s2-ct-x',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'week_start'},
                                'DateGranularity': 'WEEK',
                                'HierarchyId': 'chart-s2-ct-x'
                            }
                        }],
                        'Values': [{
                            'NumericalMeasureField': {
                                'FieldId': 'chart-s2-ct-val',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'compliance_pct_calc'},
                                'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}
                            }
                        }],
                        'Colors': [{
                            'CategoricalDimensionField': {
                                'FieldId': 'chart-s2-ct-color',
                                'Column': {'DataSetIdentifier': DATASET, 'ColumnName': 'line_of_business'}
                            }
                        }]
                    }
                },
                'SortConfiguration': {},
                'Type': 'LINE',
                'Legend': {'Visibility': 'VISIBLE', 'Position': 'BOTTOM'},
                'ReferenceLines': [{
                    'Status': 'ENABLED',
                    'DataConfiguration': {
                        'StaticConfiguration': {'Value': 95.0},
                        'AxisBinding': 'PRIMARY_YAXIS',
                        'SeriesType': 'LINE'
                    },
                    'StyleConfiguration': {'Pattern': 'DOTTED', 'Color': '#0089DD'},
                    'LabelConfiguration': {
                        'CustomLabelConfiguration': {'CustomLabel': 'Target 95%'},
                        'FontConfiguration': {'FontSize': {'Relative': 'MEDIUM'}},
                        'HorizontalPosition': 'RIGHT',
                        'VerticalPosition': 'ABOVE'
                    }
                }]
            },
            'Actions': [],
            'ColumnHierarchies': [{
                'DateTimeHierarchy': {
                    'HierarchyId': 'chart-s2-ct-x',
                    'DrillDownFilters': []
                }
            }]
        }
    }


# ---------------------------------------------------------------------------
# Main patch logic
# ---------------------------------------------------------------------------

def main():
    print('Fetching analysis definition...')
    resp = qs.describe_analysis_definition(AwsAccountId=ACCOUNT, AnalysisId=ANALYSIS_ID)
    defn = resp['Definition']

    # -----------------------------------------------------------------------
    # 1. Verify kpi_staff is in DataSetIdentifierDeclarations
    # -----------------------------------------------------------------------
    ds_ids = [d['Identifier'] for d in defn.get('DataSetIdentifierDeclarations', [])]
    if DATASET not in ds_ids:
        raise RuntimeError(f"'{DATASET}' not found in DataSetIdentifierDeclarations: {ds_ids}")
    print(f'✓ {DATASET} confirmed in DataSetIdentifierDeclarations')

    # -----------------------------------------------------------------------
    # 2. Verify compliance_pct_calc exists on kpi_staff
    # -----------------------------------------------------------------------
    calc_fields = defn.get('CalculatedFields', [])
    has_compliance_calc = any(
        cf['DataSetIdentifier'] == DATASET and cf['Name'] == 'compliance_pct_calc'
        for cf in calc_fields
    )
    if not has_compliance_calc:
        print('  compliance_pct_calc not found — adding it to kpi_staff...')
        calc_fields.append({
            'DataSetIdentifier': DATASET,
            'Name': 'compliance_pct_calc',
            'Expression': '{is_compliant} * 100'
        })
        defn['CalculatedFields'] = calc_fields
        print('  ✓ compliance_pct_calc added')
    else:
        print('✓ compliance_pct_calc already exists on kpi_staff — reusing')

    # -----------------------------------------------------------------------
    # 3. Replace Sheet 2 visuals
    # -----------------------------------------------------------------------
    new_visuals = [
        make_kpi_headcount(),
        make_kpi_hours(),
        make_kpi_billable(),
        make_kpi_compliance(),
        make_kpi_productive(),
        make_bar_util(),
        make_bar_compliance(),
        make_line_util(),
        make_line_compliance(),
    ]

    sheet_found = False
    for sheet in defn.get('Sheets', []):
        if sheet['SheetId'] == SHEET_ID:
            sheet_found = True
            old_count = len(sheet.get('Visuals', []))
            sheet['Visuals'] = new_visuals
            print(f'✓ Replaced {old_count} Sheet 2 visuals with {len(new_visuals)} new visuals using {DATASET}')
            break

    if not sheet_found:
        raise RuntimeError(f"Sheet '{SHEET_ID}' not found in analysis")

    # -----------------------------------------------------------------------
    # 4. Update FilterGroups — change kpi_practice → kpi_staff on Sheet 2 filters
    # -----------------------------------------------------------------------
    updated_fgs = []
    for fg in defn.get('FilterGroups', []):
        scope = fg.get('ScopeConfiguration', {}).get(
            'SelectedSheets', {}
        ).get('SheetVisualScopingConfigurations', [])
        for s in scope:
            if s.get('SheetId') == SHEET_ID:
                for f in fg.get('Filters', []):
                    for ftype in ['CategoryFilter', 'RelativeDatesFilter',
                                  'TimeEqualityFilter', 'TimeRangeFilter']:
                        if ftype in f:
                            col_obj = f[ftype].get('Column', {})
                            if col_obj.get('DataSetIdentifier') == 'kpi_practice':
                                col_obj['DataSetIdentifier'] = DATASET
                                updated_fgs.append(fg['FilterGroupId'])
                                print(f'  ✓ Updated {fg["FilterGroupId"]} ({ftype}.{col_obj["ColumnName"]}) kpi_practice → {DATASET}')

    if not updated_fgs:
        print('  No FilterGroup dataset changes needed (already on kpi_staff)')
    else:
        print(f'✓ Updated {len(updated_fgs)} FilterGroup filter(s)')

    # -----------------------------------------------------------------------
    # 5. Preserve layout — verify all new VisualIds are in the GridLayout
    # -----------------------------------------------------------------------
    expected_ids = {v[list(v.keys())[0]]['VisualId'] for v in new_visuals}
    for sheet in defn.get('Sheets', []):
        if sheet['SheetId'] == SHEET_ID:
            for layout in sheet.get('Layouts', []):
                cfg = layout.get('Configuration', {})
                if 'GridLayout' in cfg:
                    layout_ids = {e['ElementId'] for e in cfg['GridLayout'].get('Elements', [])}
                    missing = expected_ids - layout_ids
                    extra = layout_ids - expected_ids
                    if missing:
                        print(f'  ⚠ Layout missing ElementIds: {missing}')
                    if extra:
                        print(f'  ⚠ Layout has extra ElementIds not in new visuals: {extra}')
                    if not missing and not extra:
                        print(f'✓ GridLayout ElementIds match new visual IDs perfectly')

    # -----------------------------------------------------------------------
    # 6. Update analysis
    # -----------------------------------------------------------------------
    print('\nApplying update to analysis...')
    update_resp = qs.update_analysis(
        AwsAccountId=ACCOUNT,
        AnalysisId=ANALYSIS_ID,
        Name='KPI Tracking Dashboard',
        Definition=defn,
        ThemeArn=THEME_ARN
    )
    status = update_resp.get('Status')
    arn = update_resp.get('Arn', '')
    print(f'✓ update_analysis status={status}  arn={arn}')

    if status not in (200, 202):
        # status is HTTP code — anything 2xx is fine
        pass

    # -----------------------------------------------------------------------
    # 7. Publish dashboard using Definition (same approach as analysis)
    # -----------------------------------------------------------------------
    print('\nPublishing dashboard...')
    # Wait a moment for analysis update to propagate
    import time
    time.sleep(3)

    # Fetch the latest dashboard definition and apply the same Sheet 2 changes
    dash_resp_def = qs.describe_dashboard_definition(
        AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID
    )
    dash_defn = dash_resp_def['Definition']

    # Apply the same visual replacements to the dashboard definition
    for sheet in dash_defn.get('Sheets', []):
        if sheet['SheetId'] == SHEET_ID:
            sheet['Visuals'] = new_visuals
            print(f'  ✓ Replaced Sheet 2 visuals in dashboard definition')
            break

    # Apply same filter group dataset changes
    for fg in dash_defn.get('FilterGroups', []):
        scope = fg.get('ScopeConfiguration', {}).get(
            'SelectedSheets', {}
        ).get('SheetVisualScopingConfigurations', [])
        for s in scope:
            if s.get('SheetId') == SHEET_ID:
                for f in fg.get('Filters', []):
                    for ftype in ['CategoryFilter', 'RelativeDatesFilter',
                                  'TimeEqualityFilter', 'TimeRangeFilter']:
                        if ftype in f:
                            col_obj = f[ftype].get('Column', {})
                            if col_obj.get('DataSetIdentifier') == 'kpi_practice':
                                col_obj['DataSetIdentifier'] = DATASET

    # Ensure compliance_pct_calc is in dashboard calculated fields
    dash_calc_fields = dash_defn.get('CalculatedFields', [])
    has_dash_compliance = any(
        cf['DataSetIdentifier'] == DATASET and cf['Name'] == 'compliance_pct_calc'
        for cf in dash_calc_fields
    )
    if not has_dash_compliance:
        dash_calc_fields.append({
            'DataSetIdentifier': DATASET,
            'Name': 'compliance_pct_calc',
            'Expression': '{is_compliant} * 100'
        })
        dash_defn['CalculatedFields'] = dash_calc_fields
        print('  ✓ Added compliance_pct_calc to dashboard calculated fields')

    dash_update_resp = qs.update_dashboard(
        AwsAccountId=ACCOUNT,
        DashboardId=DASHBOARD_ID,
        Name='KPI Tracking Dashboard (prod)',
        Definition=dash_defn,
        ThemeArn=THEME_ARN
    )
    dash_version_arn = dash_update_resp.get('VersionArn', '')
    dash_status = dash_update_resp.get('Status')
    print(f'✓ update_dashboard status={dash_status}  versionArn={dash_version_arn}')

    # Publish the new version as the latest
    time.sleep(3)
    version_number = int(dash_version_arn.split('/')[-1]) if dash_version_arn else None
    if version_number:
        try:
            pub_resp = qs.update_dashboard_published_version(
                AwsAccountId=ACCOUNT,
                DashboardId=DASHBOARD_ID,
                VersionNumber=version_number
            )
            print(f'✓ Published dashboard version {version_number}')
        except Exception as e:
            print(f'  Note: update_dashboard_published_version: {e}')
    else:
        print('  Warning: Could not extract version number from VersionArn')

    print('\n=== Patch complete ===')
    print(f'Analysis: {ANALYSIS_ID}')
    print(f'Dashboard: {DASHBOARD_ID}')
    print(f'Sheet 2 now uses: {DATASET}')
    print('\nNew visuals summary:')
    for v in new_visuals:
        vtype = list(v.keys())[0]
        vid = v[vtype]['VisualId']
        title = v[vtype]['Title']['FormatText']['PlainText']
        print(f'  {vtype}: {vid} — {title}')


if __name__ == '__main__':
    main()
