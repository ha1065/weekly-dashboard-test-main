#!/usr/bin/env python3
"""
patch_kpi_date_preset.py
Replace pWeekStart DateTimePicker + TimeEqualityFilter on the KPI Tracking dashboard
with a RelativeDatesFilter + RelativeDateTimeControl (native QuickSight preset picker).

The RelativeDateTimeControl renders a built-in QS picker that shows:
  This week / This month / This quarter / This year / Year to date / etc.

Sheet mapping:
  sheet-kpi-s1  kpi_snapshots.week_start_date  SELECTED_VISUALS (8 KPI tiles)
  sheet-kpi-s2  kpi_practice.week_start        SELECTED_VISUALS (3 KPI tiles)
  sheet-kpi-s3  kpi_staff.week_start           ALL_VISUALS
"""

import boto3
import copy
import json
import time

ACCOUNT_ID = "961341524729"
ANALYSIS_ID = "kpi-tracking-analysis-prod"
DASHBOARD_ID = "kpi-tracking-dashboard-prod"
THEME_ARN = "arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme"
REGION = "us-east-1"
PROFILE = "AWSAdministratorAccess-961341524729"

# -------------------------------------------------------------------
# New FilterGroups (RelativeDatesFilter, THIS_WEEK default)
# -------------------------------------------------------------------
NEW_FILTER_GROUPS = [
    {
        "FilterGroupId": "fg-s1-date",
        "Filters": [
            {
                "RelativeDatesFilter": {
                    "FilterId": "f-s1-date",
                    "Column": {
                        "DataSetIdentifier": "kpi_snapshots",
                        "ColumnName": "week_start_date",
                    },
                    "AnchorDateConfiguration": {"AnchorOption": "NOW"},
                    "TimeGranularity": "WEEK",
                    "RelativeDateType": "THIS",
                    "NullOption": "ALL_VALUES",
                }
            }
        ],
        "ScopeConfiguration": {
            "SelectedSheets": {
                "SheetVisualScopingConfigurations": [
                    {
                        "SheetId": "sheet-kpi-s1",
                        "Scope": "SELECTED_VISUALS",
                        "VisualIds": [
                            "kpi-s1-billable-util",
                            "kpi-s1-compliance",
                            "kpi-s1-ps-ontime",
                            "kpi-s1-escalations",
                            "kpi-s1-resources",
                            "kpi-s1-eng-duration",
                            "kpi-s1-red-pct",
                            "kpi-s1-mc-ontime",
                        ],
                    }
                ]
            }
        },
        "Status": "ENABLED",
        "CrossDataset": "SINGLE_DATASET",
    },
    {
        "FilterGroupId": "fg-s2-date",
        "Filters": [
            {
                "RelativeDatesFilter": {
                    "FilterId": "f-s2-date",
                    "Column": {
                        "DataSetIdentifier": "kpi_practice",
                        "ColumnName": "week_start",
                    },
                    "AnchorDateConfiguration": {"AnchorOption": "NOW"},
                    "TimeGranularity": "WEEK",
                    "RelativeDateType": "THIS",
                    "NullOption": "ALL_VALUES",
                }
            }
        ],
        "ScopeConfiguration": {
            "SelectedSheets": {
                "SheetVisualScopingConfigurations": [
                    {
                        "SheetId": "sheet-kpi-s2",
                        "Scope": "SELECTED_VISUALS",
                        "VisualIds": [
                            "kpi-s2-headcount",
                            "kpi-s2-billable",
                            "kpi-s2-compliance",
                        ],
                    }
                ]
            }
        },
        "Status": "ENABLED",
        "CrossDataset": "SINGLE_DATASET",
    },
    {
        "FilterGroupId": "fg-s3-date",
        "Filters": [
            {
                "RelativeDatesFilter": {
                    "FilterId": "f-s3-date",
                    "Column": {
                        "DataSetIdentifier": "kpi_staff",
                        "ColumnName": "week_start",
                    },
                    "AnchorDateConfiguration": {"AnchorOption": "NOW"},
                    "TimeGranularity": "WEEK",
                    "RelativeDateType": "THIS",
                    "NullOption": "ALL_VALUES",
                }
            }
        ],
        "ScopeConfiguration": {
            "SelectedSheets": {
                "SheetVisualScopingConfigurations": [
                    {
                        "SheetId": "sheet-kpi-s3",
                        "Scope": "ALL_VISUALS",
                    }
                ]
            }
        },
        "Status": "ENABLED",
        "CrossDataset": "SINGLE_DATASET",
    },
]

# -------------------------------------------------------------------
# IDs for old date artifacts to remove
# -------------------------------------------------------------------
OLD_DATE_FG_IDS = {"fg-s1-week-kpi", "fg-s2-week-kpi", "fg-s3-week"}
OLD_DATE_PARAM_NAMES = {"pWeekStart"}
OLD_PARAM_CTRL_IDS = {"ctrl-week-s1", "ctrl-week-s2", "ctrl-week-s3"}

# New FilterControl per sheet (RelativeDateTimeControl)
NEW_FILTER_CONTROLS = {
    "sheet-kpi-s1": {
        "RelativeDateTime": {
            "FilterControlId": "ctrl-s1-date",
            "Title": "Date Range",
            "SourceFilterId": "f-s1-date",
            "DisplayOptions": {
                "DateTimeFormat": "YYYY/MM/DD",
                "TitleOptions": {"Visibility": "VISIBLE"},
            },
        }
    },
    "sheet-kpi-s2": {
        "RelativeDateTime": {
            "FilterControlId": "ctrl-s2-date",
            "Title": "Date Range",
            "SourceFilterId": "f-s2-date",
            "DisplayOptions": {
                "DateTimeFormat": "YYYY/MM/DD",
                "TitleOptions": {"Visibility": "VISIBLE"},
            },
        }
    },
    "sheet-kpi-s3": {
        "RelativeDateTime": {
            "FilterControlId": "ctrl-s3-date",
            "Title": "Date Range",
            "SourceFilterId": "f-s3-date",
            "DisplayOptions": {
                "DateTimeFormat": "YYYY/MM/DD",
                "TitleOptions": {"Visibility": "VISIBLE"},
            },
        }
    },
}


def main():
    import boto3

    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    qs = session.client("quicksight")

    # ------------------------------------------------------------------
    # 1. Fetch current definition
    # ------------------------------------------------------------------
    print("Fetching current analysis definition...")
    resp = qs.describe_analysis_definition(
        AwsAccountId=ACCOUNT_ID, AnalysisId=ANALYSIS_ID
    )
    defn = copy.deepcopy(resp["Definition"])
    print(f"  Status: {resp['ResourceStatus']}")

    # ------------------------------------------------------------------
    # 2. Remove pWeekStart parameter
    # ------------------------------------------------------------------
    original_params = defn.get("ParameterDeclarations", [])
    defn["ParameterDeclarations"] = [
        p
        for p in original_params
        if not (
            "DateTimeParameterDeclaration" in p
            and p["DateTimeParameterDeclaration"]["Name"] in OLD_DATE_PARAM_NAMES
        )
    ]
    removed_params = len(original_params) - len(defn["ParameterDeclarations"])
    print(f"  Removed {removed_params} parameter(s): {OLD_DATE_PARAM_NAMES}")

    # ------------------------------------------------------------------
    # 3. Remove old TimeEqualityFilter FilterGroups, add new ones
    # ------------------------------------------------------------------
    original_fgs = defn.get("FilterGroups", [])
    kept_fgs = [fg for fg in original_fgs if fg["FilterGroupId"] not in OLD_DATE_FG_IDS]
    removed_fgs = len(original_fgs) - len(kept_fgs)
    print(f"  Removed {removed_fgs} TimeEqualityFilter FilterGroup(s)")

    defn["FilterGroups"] = kept_fgs + NEW_FILTER_GROUPS
    print(f"  Added {len(NEW_FILTER_GROUPS)} RelativeDatesFilter FilterGroup(s)")

    # ------------------------------------------------------------------
    # 4. Per-sheet: remove DateTimePicker ParameterControls,
    #               add RelativeDateTime FilterControls,
    #               update layout elements
    # ------------------------------------------------------------------
    # Map old layout element ID → new layout element details
    LAYOUT_REPLACEMENTS = {
        "ctrl-week-s1": {"new_id": "ctrl-s1-date", "new_type": "FILTER_CONTROL"},
        "ctrl-week-s2": {"new_id": "ctrl-s2-date", "new_type": "FILTER_CONTROL"},
        "ctrl-week-s3": {"new_id": "ctrl-s3-date", "new_type": "FILTER_CONTROL"},
    }

    for sheet in defn.get("Sheets", []):
        sid = sheet["SheetId"]

        # Remove old DateTimePicker parameter controls
        original_pcs = sheet.get("ParameterControls", [])
        sheet["ParameterControls"] = [
            pc
            for pc in original_pcs
            if not (
                "DateTimePicker" in pc
                and pc["DateTimePicker"]["ParameterControlId"] in OLD_PARAM_CTRL_IDS
            )
        ]
        removed = len(original_pcs) - len(sheet["ParameterControls"])
        if removed:
            print(f"  Sheet {sid}: removed {removed} DateTimePicker control(s)")

        # Add RelativeDateTime as a FilterControl
        if sid in NEW_FILTER_CONTROLS:
            fcs = sheet.get("FilterControls", [])
            # Idempotency: remove existing control with same ID
            new_ctrl_id = NEW_FILTER_CONTROLS[sid]["RelativeDateTime"]["FilterControlId"]
            fcs = [
                fc
                for fc in fcs
                if fc.get("RelativeDateTime", {}).get("FilterControlId") != new_ctrl_id
            ]
            fcs.insert(0, NEW_FILTER_CONTROLS[sid])  # put Date Range first
            sheet["FilterControls"] = fcs
            print(f"  Sheet {sid}: added RelativeDateTime FilterControl '{new_ctrl_id}'")

        # Update layout: replace old PARAMETER_CONTROL element with FILTER_CONTROL
        for layout in sheet.get("Layouts", []):
            config = layout.get("Configuration", {})
            for ltype, lcontent in config.items():
                if ltype in ("GridLayout", "FreeFormLayout"):
                    elements = lcontent.get("Elements", [])
                    for elem in elements:
                        old_id = elem.get("ElementId", "")
                        if old_id in LAYOUT_REPLACEMENTS:
                            rep = LAYOUT_REPLACEMENTS[old_id]
                            print(f"  Sheet {sid}: layout element {old_id} ({elem['ElementType']}) → {rep['new_id']} ({rep['new_type']})")
                            elem["ElementId"] = rep["new_id"]
                            elem["ElementType"] = rep["new_type"]

    # ------------------------------------------------------------------
    # 5. Call update_analysis
    # ------------------------------------------------------------------
    print("\nCalling update_analysis...")
    update_resp = qs.update_analysis(
        AwsAccountId=ACCOUNT_ID,
        AnalysisId=ANALYSIS_ID,
        Name="KPI Tracking Analysis (prod)",
        Definition=defn,
        ThemeArn=THEME_ARN,
    )
    print(f"  HTTP status: {update_resp['ResponseMetadata']['HTTPStatusCode']}")

    # ------------------------------------------------------------------
    # 6. Poll for UPDATE_SUCCESSFUL
    # ------------------------------------------------------------------
    print("Waiting for UPDATE_SUCCESSFUL...")
    for i in range(30):
        time.sleep(5)
        status_resp = qs.describe_analysis(
            AwsAccountId=ACCOUNT_ID, AnalysisId=ANALYSIS_ID
        )
        status = status_resp["Analysis"]["Status"]
        print(f"  [{i+1}] {status}")
        if status == "UPDATE_SUCCESSFUL":
            print("  Analysis updated successfully.")
            break
        elif "FAILED" in status or "ERROR" in status:
            errors = status_resp["Analysis"].get("Errors", [])
            print(f"  FAILED: {json.dumps(errors, indent=2)}")
            return False
    else:
        print("  Timed out waiting for UPDATE_SUCCESSFUL")
        return False

    # ------------------------------------------------------------------
    # 7. Republish dashboard
    # ------------------------------------------------------------------
    print("\nRepublishing dashboard...")
    dash_resp = qs.describe_dashboard_definition(
        AwsAccountId=ACCOUNT_ID, DashboardId=DASHBOARD_ID
    )
    dash_defn = dash_resp["Definition"]
    dash_name = dash_resp.get("Name", "KPI Tracking Dashboard (prod)")

    pub_resp = qs.update_dashboard(
        AwsAccountId=ACCOUNT_ID,
        DashboardId=DASHBOARD_ID,
        Name=dash_name,
        Definition=dash_defn,
        ThemeArn=THEME_ARN,
        VersionDescription="Add RelativeDates preset date control (Week/Month/Quarter/YTD)",
    )
    new_version_arn = pub_resp.get("VersionArn", "unknown")
    # Extract version number from ARN (…/version/N)
    expected_version = int(new_version_arn.split("/version/")[-1]) if "/version/" in new_version_arn else None
    print(f"  Dashboard update submitted. VersionArn: {new_version_arn} (expecting version {expected_version})")

    # Wait for dashboard publish — poll for the specific new version
    print("Waiting for dashboard CREATION_SUCCESSFUL...")
    for i in range(30):
        time.sleep(5)
        dash_status_resp = qs.describe_dashboard(
            AwsAccountId=ACCOUNT_ID,
            DashboardId=DASHBOARD_ID,
            **({"VersionNumber": expected_version} if expected_version else {}),
        )
        dash_status = dash_status_resp["Dashboard"]["Version"]["Status"]
        dash_ver = dash_status_resp["Dashboard"]["Version"]["VersionNumber"]
        print(f"  [{i+1}] version={dash_ver} status={dash_status}")
        if dash_status == "CREATION_SUCCESSFUL":
            print(f"  Dashboard v{dash_ver} published successfully.")
            return True
        elif "FAILED" in dash_status or "ERROR" in dash_status:
            errors = dash_status_resp["Dashboard"]["Version"].get("Errors", [])
            print(f"  Dashboard publish FAILED: {json.dumps(errors, indent=2)}")
            return False

    print("  Timed out waiting for dashboard CREATION_SUCCESSFUL")
    return False


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
