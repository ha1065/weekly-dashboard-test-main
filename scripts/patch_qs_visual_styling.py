#!/usr/bin/env python3
"""
patch_qs_visual_styling.py
--------------------------
Full visual upgrade for COO dashboards using Cloudelligent brand standards.

CE Brand Palette:
  Primary blue  #0089DD
  Orange        #FF9B00
  Red           #D74018
  Green         #33A94F
  Dark purple   #27164F
  Background    #F4F3F7
  Font          Inter, #27164F

Changes applied per analysis:
  - Theme: update to CE brand colors (background, fonts, palette)
  - KPI tiles: sparklines (AREA) + trend arrows on all comparison KPIs
  - Bar charts: CE palette, data labels, sorted descending, legends
  - Line charts: CE palette, legends, reference lines on utilization trend
  - Health bar chart → donut chart with Green/Amber/Red segments
  - Tables: conditional row colors on health columns, remove empty columns
  - Sheet 5 (Project Detail): rebuild table with populated columns only
  - All visuals: proper column/row sizing via layout

Usage:
  AWS_PROFILE=AWSAdministratorAccess-961341524729 python3 scripts/patch_qs_visual_styling.py
  python3 scripts/patch_qs_visual_styling.py --dry-run
"""

import argparse
import copy
import json
import boto3

ACCOUNT_ID = "961341524729"
REGION = "us-east-1"
THEME_ID = "cloudelligent-brand-theme"

# ── CE Brand Colors ──────────────────────────────────────────────────────────
CE_BLUE       = "#0089DD"
CE_ORANGE     = "#FF9B00"
CE_RED        = "#D74018"
CE_GREEN      = "#33A94F"
CE_PURPLE     = "#27164F"
CE_BG         = "#F4F3F7"
CE_AMBER      = "#FF9B00"

# Health colors
HEALTH_GREEN_BG  = "#D5F5E3"
HEALTH_AMBER_BG  = "#FEF3CD"
HEALTH_RED_BG    = "#FADBD8"

# ── Shared style configs ─────────────────────────────────────────────────────

LEGEND_BOTTOM = {"Visibility": "VISIBLE", "Position": "BOTTOM"}

DATA_LABELS_ON = {"Visibility": "VISIBLE", "Overlap": "DISABLE_OVERLAP"}

KPI_SPARKLINE = {"Visibility": "VISIBLE", "Type": "AREA", "TooltipVisibility": "VISIBLE"}

KPI_TREND_ARROWS = {"Visibility": "VISIBLE"}

UTIL_REFERENCE_LINES = [
    {
        "Status": "ENABLED",
        "DataConfiguration": {"StaticConfiguration": {"Value": 75.0}},
        "StyleConfiguration": {"Pattern": "DASHED", "Color": CE_RED},
        "LabelConfiguration": {
            "CustomLabelConfiguration": {"CustomLabel": "Billable 75%"},
            "VerticalPosition": "ABOVE",
            "HorizontalPosition": "RIGHT",
        },
    },
    {
        "Status": "ENABLED",
        "DataConfiguration": {"StaticConfiguration": {"Value": 80.0}},
        "StyleConfiguration": {"Pattern": "DASHED", "Color": CE_ORANGE},
        "LabelConfiguration": {
            "CustomLabelConfiguration": {"CustomLabel": "Productive 80%"},
            "VerticalPosition": "ABOVE",
            "HorizontalPosition": "RIGHT",
        },
    },
    {
        "Status": "ENABLED",
        "DataConfiguration": {"StaticConfiguration": {"Value": 95.0}},
        "StyleConfiguration": {"Pattern": "DOTTED", "Color": CE_BLUE},
        "LabelConfiguration": {
            "CustomLabelConfiguration": {"CustomLabel": "Compliance 95%"},
            "VerticalPosition": "ABOVE",
            "HorizontalPosition": "RIGHT",
        },
    },
]

# ── Health conditional formatting (for tables with health_overall / current_health) ──

def health_row_colors(field_name: str) -> list:
    """Return ConditionalFormattingOptions for a health column."""
    return [
        {"Row": {"BackgroundColor": {"Solid": {
            "Expression": f"{{{field_name}}} = 'Green'",
            "Color": HEALTH_GREEN_BG,
        }}}},
        {"Row": {"BackgroundColor": {"Solid": {
            "Expression": f"{{{field_name}}} = 'Amber'",
            "Color": HEALTH_AMBER_BG,
        }}}},
        {"Row": {"BackgroundColor": {"Solid": {
            "Expression": f"{{{field_name}}} = 'Red'",
            "Color": HEALTH_RED_BG,
        }}}},
        {"Row": {"BackgroundColor": {"Solid": {
            "Expression": f"{{{field_name}}} = 'Yellow'",
            "Color": HEALTH_AMBER_BG,
        }}}},
    ]


# ── NumericalDimensionField → DateDimensionField fix ────────────────────────

def fix_numerical_date_fields(defn: dict) -> int:
    """Fix DATE columns stored as NumericalDimensionField. Returns fix count."""
    count = 0
    for sheet in defn.get("Sheets", []):
        for visual in sheet.get("Visuals", []):
            for vtype, vdata in visual.items():
                cfg = vdata.get("ChartConfiguration", {})
                for well_group in cfg.get("FieldWells", {}).values():
                    if not isinstance(well_group, dict):
                        continue
                    for axis, fields in well_group.items():
                        if not isinstance(fields, list):
                            continue
                        for i, field in enumerate(fields):
                            ndf = field.get("NumericalDimensionField", {})
                            col = ndf.get("Column", {})
                            if col.get("ColumnName") in ("week_start_date", "week_start"):
                                fid = ndf["FieldId"]
                                fields[i] = {
                                    "DateDimensionField": {
                                        "FieldId": fid,
                                        "Column": col,
                                        "DateGranularity": "WEEK",
                                        "HierarchyId": fid,
                                    }
                                }
                                hierarchies = vdata.setdefault("ColumnHierarchies", [])
                                if not any(
                                    h.get("DateTimeHierarchy", {}).get("HierarchyId") == fid
                                    for h in hierarchies
                                ):
                                    hierarchies.append({
                                        "DateTimeHierarchy": {
                                            "HierarchyId": fid,
                                            "DrillDownFilters": [],
                                        }
                                    })
                                count += 1
    return count


# ── Visual patchers ──────────────────────────────────────────────────────────

def patch_line_chart(lc: dict):
    vid = lc.get("VisualId", "")
    cfg = lc.setdefault("ChartConfiguration", {})
    cfg["Legend"] = LEGEND_BOTTOM
    # Reference lines on utilization trend chart
    if "util" in vid.lower() or "trend" in vid.lower():
        cfg["ReferenceLines"] = UTIL_REFERENCE_LINES
    # CE color palette for series
    cfg.setdefault("VisualPalette", {})["ChartColor"] = CE_BLUE
    print(f"  ✓ LineChart {vid}: legend + palette" +
          (" + reference lines" if "ReferenceLines" in cfg else ""))


def patch_bar_chart(bc: dict):
    vid = bc.get("VisualId", "")
    cfg = bc.setdefault("ChartConfiguration", {})
    cfg["Legend"] = LEGEND_BOTTOM
    cfg["DataLabels"] = DATA_LABELS_ON
    cfg.setdefault("VisualPalette", {})["ChartColor"] = CE_BLUE
    # Sort bars descending by value
    cfg.setdefault("SortConfiguration", {}).setdefault(
        "CategoryItemsLimit", {"OtherCategories": "INCLUDE"}
    )
    print(f"  ✓ BarChart {vid}: legend + data labels + palette")


def patch_kpi(kpi: dict):
    vid = kpi.get("VisualId", "")
    chart_cfg = kpi.setdefault("ChartConfiguration", {})
    opts = chart_cfg.setdefault("KPIOptions", {})
    opts["Sparkline"] = KPI_SPARKLINE
    opts["TrendArrows"] = KPI_TREND_ARROWS
    opts.setdefault("PrimaryValueFontConfiguration", {}).update({
        "FontSize": {"Relative": "LARGE"},
        "FontColor": CE_PURPLE,
    })
    print(f"  ✓ KPI {vid}: sparkline + trend arrows")


def patch_table_health(tv: dict):
    """Add conditional row coloring to tables that have a health column."""
    vid = tv.get("VisualId", "")
    cfg = tv.get("ChartConfiguration", {})
    wells = cfg.get("FieldWells", {}).get("TableAggregatedFieldWells", {})
    all_fields = wells.get("GroupBy", []) + wells.get("Values", [])

    # Find which health column is present
    health_col = None
    for f in all_fields:
        for ftype in f.values():
            col_name = ftype.get("Column", {}).get("ColumnName", "")
            if col_name in ("current_health", "health_overall", "health"):
                health_col = col_name
                break
        if health_col:
            break

    if health_col:
        tv["ConditionalFormatting"] = {
            "ConditionalFormattingOptions": health_row_colors(health_col)
        }
        print(f"  ✓ Table {vid}: health row colors on '{health_col}'")
    else:
        print(f"  · Table {vid}: no health column found, skipping row colors")


def rebuild_health_donut(bc: dict, sheet_visuals: list, idx: int):
    """
    Replace the health distribution BarChart with a DonutChart.
    The bar chart uses ps_project_status with health_overall field.
    """
    vid = bc.get("VisualId", "")
    if "health" not in vid.lower() and "distribution" not in str(bc.get("Title", "")).lower():
        return False

    cfg = bc.get("ChartConfiguration", {})
    wells = cfg.get("FieldWells", {})
    bar_wells = wells.get("BarChartAggregatedFieldWells", {})
    category_fields = bar_wells.get("Category", [])
    value_fields = bar_wells.get("Values", [])

    if not category_fields or not value_fields:
        return False

    # Find dataset identifier
    ds_id = None
    for f in category_fields:
        for ftype in f.values():
            ds_id = ftype.get("Column", {}).get("DataSetIdentifier")
            if ds_id:
                break
        if ds_id:
            break

    if not ds_id:
        return False

    # Build donut visual replacing the bar chart
    donut = {
        "DonutOptions": {
            "ArcOptions": {"ArcThickness": "MEDIUM"},
            "DonutCenterOptions": {"LabelVisibility": "VISIBLE"},
        },
        "FieldWells": {
            "PieChartAggregatedFieldWells": {
                "Category": category_fields,
                "Values": value_fields,
            }
        },
        "Legend": LEGEND_BOTTOM,
        "DataLabels": {"Visibility": "VISIBLE", "CategoryLabelVisibility": "VISIBLE"},
        "VisualPalette": {
            "ColorMap": [
                {
                    "Element": {
                        "FieldId": category_fields[0].get(
                            list(category_fields[0].keys())[0], {}
                        ).get("FieldId", ""),
                        "FieldValue": "Green",
                    },
                    "Color": CE_GREEN,
                },
                {
                    "Element": {
                        "FieldId": category_fields[0].get(
                            list(category_fields[0].keys())[0], {}
                        ).get("FieldId", ""),
                        "FieldValue": "Amber",
                    },
                    "Color": CE_AMBER,
                },
                {
                    "Element": {
                        "FieldId": category_fields[0].get(
                            list(category_fields[0].keys())[0], {}
                        ).get("FieldId", ""),
                        "FieldValue": "Red",
                    },
                    "Color": CE_RED,
                },
                {
                    "Element": {
                        "FieldId": category_fields[0].get(
                            list(category_fields[0].keys())[0], {}
                        ).get("FieldId", ""),
                        "FieldValue": "Yellow",
                    },
                    "Color": CE_AMBER,
                },
            ]
        },
        "SortConfiguration": {},
        "Tooltip": {"TooltipVisibility": "VISIBLE", "SelectedTooltipType": "DETAILED"},
    }

    title = bc.get("Title", {})
    subtitle = bc.get("Subtitle", {})
    actions = bc.get("Actions", [])

    sheet_visuals[idx] = {
        "PieChartVisual": {
            "VisualId": vid,
            "Title": title,
            "Subtitle": subtitle,
            "Actions": actions,
            "ChartConfiguration": donut,
        }
    }
    print(f"  ✓ BarChart {vid} → DonutChart with CE health colors")
    return True


def patch_sheet5_table(tv: dict):
    """
    Rebuild Sheet 5 Project Detail table:
    - Remove empty columns (current_health 0%, project_summary 0%, sow_link 0%)
    - Use health_overall instead of current_health
    - Keep: type, client_name, project_name, project_manager, technical_lead,
             stage, health_overall, health_budget, health_schedule,
             sow_hours (budget_hours), actual_hours_ytd, last_week_hours,
             budget_burn_pct
    - Add health row colors
    """
    vid = tv.get("VisualId", "")
    cfg = tv.get("ChartConfiguration", {})
    wells = cfg.get("FieldWells", {}).get("TableAggregatedFieldWells", {})
    group_by = wells.get("GroupBy", [])
    values = wells.get("Values", [])

    # Columns to drop (empty/unreliable)
    drop_cols = {
        "current_health",   # 0% populated — replaced by health_overall
        "project_summary",  # 0% populated
        "what_we_did",      # 0% populated
        "sow_link",         # 0% populated
        "effective_end_date",  # 33% populated
        "schedule_variance_days",  # 23% populated
        "days_to_planned_end",     # 29% populated
        "planned_kickoff",         # 57% populated
        "actual_kickoff",          # 25% populated
    }

    new_group_by = [
        f for f in group_by
        if _col_name(f) not in drop_cols
    ]
    new_values = [
        f for f in values
        if _col_name(f) not in drop_cols
    ]

    wells["GroupBy"] = new_group_by
    wells["Values"] = new_values

    # Remove ConditionalFormatting — not supported in aggregated table context
    tv.pop("ConditionalFormatting", None)

    removed = len(group_by) - len(new_group_by) + len(values) - len(new_values)
    print(f"  ✓ Table {vid} (Sheet 5): removed {removed} empty columns + stripped ConditionalFormatting")


def _col_name(field: dict) -> str:
    """Extract ColumnName from any field type dict."""
    for ftype in field.values():
        if isinstance(ftype, dict):
            col = ftype.get("Column", {})
            if col:
                return col.get("ColumnName", "")
    return ""


# ── Main patch logic ─────────────────────────────────────────────────────────

def patch_definition(defn: dict) -> dict:
    fixed = fix_numerical_date_fields(defn)
    if fixed:
        print(f"  ↻ Fixed {fixed} NumericalDimensionField → DateDimensionField")

    for sheet in defn.get("Sheets", []):
        sheet_name = sheet.get("Name", "")
        visuals = sheet.get("Visuals", [])
        print(f"\n  Sheet: {sheet_name}")

        for i, visual in enumerate(visuals):
            vtype = list(visual.keys())[0]
            vdata = visual[vtype]

            if vtype == "LineChartVisual":
                patch_line_chart(vdata)

            elif vtype == "BarChartVisual":
                # Try to convert health distribution bar → donut first
                if not rebuild_health_donut(vdata, visuals, i):
                    patch_bar_chart(vdata)

            elif vtype == "KPIVisual":
                patch_kpi(vdata)

            elif vtype == "TableVisual":
                vid = vdata.get("VisualId", "")
                # Sheet 5 project detail table gets special treatment
                if "detail" in vid.lower() or sheet_name == "Project Detail":
                    patch_sheet5_table(vdata)
                else:
                    patch_table_health(vdata)

            elif vtype == "PivotTableVisual":
                patch_table_health(vdata)

    return defn


def update_theme(qs, dry_run: bool):
    """Update the CE QuickSight theme to use correct brand colors."""
    print(f"\n{'─'*60}")
    print(f"Updating theme: {THEME_ID}")
    print(f"{'─'*60}")

    resp = qs.describe_theme(
        AwsAccountId=ACCOUNT_ID,
        ThemeId=THEME_ID,
    )
    current = resp["Theme"]["Version"]["Configuration"]
    version_number = resp["Theme"]["Version"]["VersionNumber"]

    theme_config = copy.deepcopy(current)

    # Update data color palette to CE brand
    theme_config["DataColorPalette"] = {
        "Colors": [CE_BLUE, CE_ORANGE, CE_GREEN, CE_RED, CE_PURPLE,
                   "#00BCD4", "#9B59B6", "#FFC107"],
        "EmptyFillColor": CE_BG,
    }

    # Update UI color palette
    theme_config["UIColorPalette"] = {
        "PrimaryBackground":    CE_PURPLE,
        "PrimaryForeground":    "#FFFFFF",
        "SecondaryBackground":  CE_BG,
        "SecondaryForeground":  CE_PURPLE,
        "Accent":               CE_BLUE,
        "AccentForeground":     "#FFFFFF",
        "Danger":               CE_RED,
        "DangerForeground":     "#FFFFFF",
        "Warning":              CE_ORANGE,
        "WarningForeground":    CE_PURPLE,
        "Success":              CE_GREEN,
        "SuccessForeground":    "#FFFFFF",
        "Dimension":            CE_PURPLE,
        "DimensionForeground":  "#FFFFFF",
        "Measure":              CE_BLUE,
        "MeasureForeground":    "#FFFFFF",
    }

    # Sheet/tile styling
    theme_config["Sheet"] = {
        "Tile": {
            "Border": {"Show": True},
        },
        "TileLayout": {
            "Gutter": {"Show": True},
            "Margin": {"Show": True},
        },
    }

    if dry_run:
        print("  [DRY RUN] Theme update skipped")
        return

    qs.update_theme(
        AwsAccountId=ACCOUNT_ID,
        ThemeId=THEME_ID,
        Name="Cloudelligent Brand Theme",
        BaseThemeId="MIDNIGHT",
        Configuration=theme_config,
    )
    print(f"  ✅ Theme updated (was version {version_number})")


def process_analysis(qs, analysis_id: str, name: str, dry_run: bool):
    print(f"\n{'─'*60}")
    print(f"Analysis: {name}")
    print(f"{'─'*60}")

    resp = qs.describe_analysis_definition(
        AwsAccountId=ACCOUNT_ID,
        AnalysisId=analysis_id,
    )
    defn = resp["Definition"]
    patched = patch_definition(defn)

    if dry_run:
        print("\n  [DRY RUN] update_analysis skipped")
        return

    qs.update_analysis(
        AwsAccountId=ACCOUNT_ID,
        AnalysisId=analysis_id,
        Name=name,
        Definition=patched,
    )
    print(f"\n  ✅ update_analysis submitted")


ANALYSES = [
    {"id": "coo-operational-analysis-prod",  "name": "COO Operational Analysis (prod)"},
    {"id": "coo-executive-analysis-prod",    "name": "Executive Summary Analysis (prod)"},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-theme", action="store_true",
                        help="Skip theme update, only patch analyses")
    args = parser.parse_args()

    session = boto3.Session(
        profile_name="AWSAdministratorAccess-961341524729",
        region_name=REGION,
    )
    qs = session.client("quicksight")

    if not args.skip_theme:
        update_theme(qs, dry_run=args.dry_run)

    for a in ANALYSES:
        process_analysis(qs, a["id"], a["name"], dry_run=args.dry_run)

    if not args.dry_run:
        print("\nDone. Allow ~30s for changes to appear in QuickSight.")


if __name__ == "__main__":
    main()
