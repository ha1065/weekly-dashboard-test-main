#!/usr/bin/env python3
"""
sync_coo_dashboard_iac.py
--------------------------
Pulls the live COO Operational Analysis definition from QuickSight and
writes it into cloudformation/coo-dashboards.yaml as the authoritative IaC.

This replaces the stale CloudFormation template with the exact live state,
ensuring a redeploy never loses patched sheets.

Usage:
    python3 scripts/sync_coo_dashboard_iac.py [--dry-run]

The script:
  1. Reads coo-analysis-live.json (already exported) OR fetches live from QS
  2. Extracts the Definition block
  3. Rewrites coo-dashboards.yaml with the live definition embedded
  4. Preserves all CloudFormation parameters, outputs, and permissions

After running, commit coo-dashboards.yaml to git.
"""

import argparse
import json
import sys
from pathlib import Path

import boto3
import yaml

ACCOUNT_ID = "961341524729"
REGION = "us-east-1"
ANALYSIS_ID = "coo-operational-analysis-prod"
THEME_ARN = f"arn:aws:quicksight:{REGION}:{ACCOUNT_ID}:theme/cloudelligent-brand-theme"

PROJECT_ROOT = Path(__file__).parent.parent
LIVE_JSON = PROJECT_ROOT / "coo-analysis-live.json"
OUTPUT_CF = PROJECT_ROOT / "cloudformation" / "coo-dashboards.yaml"


def fetch_live_definition(use_cache: bool = True) -> dict:
    """Return the live analysis Definition dict."""
    if use_cache and LIVE_JSON.exists():
        print(f"Using cached definition: {LIVE_JSON}")
        with open(LIVE_JSON) as f:
            data = json.load(f)
        return data["Definition"]

    print("Fetching live definition from QuickSight...")
    qs = boto3.Session(
        profile_name="AWSAdministratorAccess-961341524729",
        region_name=REGION,
    ).client("quicksight")
    resp = qs.describe_analysis_definition(
        AwsAccountId=ACCOUNT_ID,
        AnalysisId=ANALYSIS_ID,
    )
    defn = resp["Definition"]
    # Cache it
    with open(LIVE_JSON, "w") as f:
        json.dump({"Definition": defn}, f, indent=2, default=str)
    print(f"Cached to {LIVE_JSON}")
    return defn


def build_cloudformation(defn: dict) -> dict:
    """Build the CloudFormation template dict from the live definition."""

    # Dataset ARN lookup from the live definition
    dataset_arns = {
        d["Identifier"]: d["DataSetArn"]
        for d in defn.get("DataSetIdentifierDeclarations", [])
    }

    cf = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": (
            "COO Dashboards — Cloudelligent Operations. "
            "Synced from live QuickSight analysis. "
            "DO NOT EDIT MANUALLY — regenerate with scripts/sync_coo_dashboard_iac.py"
        ),
        "Parameters": {
            "Environment": {
                "Type": "String",
                "Default": "prod",
                "AllowedValues": ["dev", "staging", "prod"],
            },
            "QuickSightUsername": {
                "Type": "String",
                "Description": "QuickSight email-based username (for ARN)",
            },
            "QuickSightOwnerArn": {
                "Type": "String",
                "Description": "Full QuickSight user ARN for owner permissions",
            },
            "AwsAccountId": {
                "Type": "String",
                "Description": "AWS Account ID",
            },
        },
        "Resources": {
            "CooOperationalAnalysis": {
                "Type": "AWS::QuickSight::Analysis",
                "Properties": {
                    "AwsAccountId": {"Ref": "AwsAccountId"},
                    "AnalysisId": {"Fn::Sub": f"coo-operational-analysis-${{Environment}}"},
                    "Name": {"Fn::Sub": f"COO Operational Analysis (${{Environment}})"},
                    "ThemeArn": {"Fn::ImportValue": "CloudelligentQuickSightThemeArn"},
                    "Definition": defn,
                    "Permissions": [
                        {
                            "Principal": {"Ref": "QuickSightOwnerArn"},
                            "Actions": [
                                "quicksight:RestoreAnalysis",
                                "quicksight:UpdateAnalysisPermissions",
                                "quicksight:DeleteAnalysis",
                                "quicksight:DescribeAnalysisPermissions",
                                "quicksight:QueryAnalysis",
                                "quicksight:DescribeAnalysis",
                                "quicksight:UpdateAnalysis",
                            ],
                        }
                    ],
                },
            }
        },
        "Outputs": {
            "CooOperationalAnalysisId": {
                "Description": "COO Operational Analysis ID",
                "Value": {"Fn::Sub": f"coo-operational-analysis-${{Environment}}"},
            }
        },
    }

    return cf


def main():
    parser = argparse.ArgumentParser(description="Sync live QS analysis to CloudFormation IaC")
    parser.add_argument("--dry-run", action="store_true", help="Print output without writing")
    parser.add_argument("--fetch", action="store_true", help="Force fetch from QS (ignore cache)")
    args = parser.parse_args()

    defn = fetch_live_definition(use_cache=not args.fetch)

    # Summarise what we found
    sheets = defn.get("Sheets", [])
    datasets = defn.get("DataSetIdentifierDeclarations", [])
    print(f"\nLive analysis contains:")
    print(f"  Sheets ({len(sheets)}): {[s['Name'] for s in sheets]}")
    print(f"  Datasets ({len(datasets)}): {[d['Identifier'] for d in datasets]}")
    print(f"  FilterGroups: {len(defn.get('FilterGroups', []))}")
    print(f"  Parameters: {len(defn.get('ParameterDeclarations', []))}")
    print(f"  CalculatedFields: {len(defn.get('CalculatedFields', []))}")

    cf = build_cloudformation(defn)

    # Use json→yaml via safe_dump for clean output
    output = yaml.dump(cf, default_flow_style=False, allow_unicode=True, sort_keys=False)

    if args.dry_run:
        print("\n--- DRY RUN: CloudFormation output (first 100 lines) ---")
        for line in output.splitlines()[:100]:
            print(line)
        print("...")
        return

    OUTPUT_CF.write_text(output)
    print(f"\n✅ Written to {OUTPUT_CF}")
    print("Next steps:")
    print("  1. Review the file: git diff cloudformation/coo-dashboards.yaml")
    print("  2. Commit: git add cloudformation/coo-dashboards.yaml && git commit -m 'sync: coo-dashboards IaC from live analysis'")
    print("  3. To redeploy the analysis:")
    print("     aws cloudformation deploy --template-file cloudformation/coo-dashboards.yaml \\")
    print("       --stack-name coo-dashboards-prod \\")
    print("       --parameter-overrides Environment=prod AwsAccountId=961341524729 \\")
    print("         QuickSightUsername=chris.xenos@cloudelligent.com \\")
    print("         QuickSightOwnerArn=arn:aws:quicksight:us-east-1:961341524729:user/default/AWSReservedSSO_AWSAdministratorAccess_ed420cc098d02bac/chris.xenos \\")
    print("       --capabilities CAPABILITY_IAM --profile AWSAdministratorAccess-961341524729 --region us-east-1")
    print("")
    print("  ⚠️  IMPORTANT: The CFN deploy updates the ANALYSIS only — NOT the dashboard.")
    print("  The dashboard (coo-operational-dashboard-prod) is NOT in CloudFormation.")
    print("  After deploying, republish the dashboard with the CE theme:")
    print("     python3 scripts/publish_coo_dashboard.py")
    print("")
    print("  Skipping publish_coo_dashboard.py leaves the public dashboard on the old")
    print("  analysis version. Skipping ThemeArn in any update_dashboard call strips")
    print("  the CE theme — always pass ThemeArn=cloudelligent-brand-theme.")


if __name__ == "__main__":
    main()
