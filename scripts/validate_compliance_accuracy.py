#!/usr/bin/env python3
"""
validate_compliance_accuracy.py

Cross-checks the weekly-reporting RDS non-compliant staff list against the
live Clockify API to identify false positives (users who actually have time
entries in Clockify but whose entries haven't been imported into RDS yet).

Usage:
    python3 scripts/validate_compliance_accuracy.py \
        --profile AWSAdministratorAccess-961341524729 \
        --region us-east-1 \
        [--week-start 2026-06-23]

The script:
  1. Invokes the production-clockify-import Lambda in run_query mode to fetch
     the current non-compliant list from vw_missing_time_submissions.
  2. Retrieves Clockify credentials from AWS Secrets Manager
     (production/weekly-reporting/secrets).
  3. Queries the Clockify API for each user to check whether they have any
     time entries for the reporting week.
  4. Classifies each user as:
       CONFIRMED        — 0 hours in both RDS and Clockify
       FALSE POSITIVE   — 0 hours in RDS, but entries exist in Clockify
       DATA INTEGRITY   — hours in RDS but no entries in Clockify (shouldn't happen)
  5. Writes a Markdown findings report to docs/compliance-validation-{date}.md.
"""

import argparse
import json
import subprocess
import time
import sys
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_aws(args: list[str]) -> dict:
    """Run an AWS CLI command and return parsed JSON output."""
    result = subprocess.run(
        ["aws"] + args,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"AWS CLI error: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def invoke_lambda(function_name: str, payload: dict, profile: str, region: str) -> dict:
    """Invoke a Lambda function and return the parsed response body."""
    payload_str = json.dumps(payload)
    tmp_out = "/tmp/lambda_response.json"
    result = subprocess.run(
        [
            "aws", "lambda", "invoke",
            "--function-name", function_name,
            "--profile", profile,
            "--region", region,
            "--cli-binary-format", "raw-in-base64-out",
            "--payload", payload_str,
            tmp_out
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Lambda invoke failed: {result.stderr.strip()}\n{result.stdout}")

    with open(tmp_out) as f:
        raw = json.load(f)

    # Lambda returns {"statusCode": 200, "body": "<json string>"}
    if isinstance(raw.get("body"), str):
        return json.loads(raw["body"])
    return raw


def get_secret(secret_name: str, profile: str, region: str) -> dict:
    """Retrieve a Secrets Manager secret and return its parsed JSON value."""
    result = subprocess.run(
        [
            "aws", "secretsmanager", "get-secret-value",
            "--secret-id", secret_name,
            "--profile", profile,
            "--region", region,
            "--query", "SecretString",
            "--output", "text"
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Secrets Manager error: {result.stderr.strip()}")
    return json.loads(result.stdout.strip())


def clockify_get(path: str, api_key: str) -> list | dict:
    """Make a GET request to the Clockify API and return the parsed JSON."""
    url = f"https://api.clockify.me/api/v1{path}"
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Clockify HTTP {e.code} for {url}: {body}")


def week_start_for_date(d: date) -> date:
    """Return the Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Validate compliance accuracy against Clockify")
    parser.add_argument("--profile", default="AWSAdministratorAccess-961341524729")
    parser.add_argument("--region",  default="us-east-1")
    parser.add_argument(
        "--week-start",
        default=None,
        help="ISO date of Monday for reporting week (default: prior complete week)"
    )
    args = parser.parse_args()

    # Determine reporting week
    if args.week_start:
        week_start = date.fromisoformat(args.week_start)
    else:
        today = date.today()
        # Prior complete Monday–Sunday week
        week_start = week_start_for_date(today) - timedelta(weeks=1)

    week_end = week_start + timedelta(days=6)
    print(f"\n{'='*60}")
    print(f"Compliance Validation — Week {week_start} to {week_end}")
    print(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Step 1: Get non-compliant list from RDS
    # ------------------------------------------------------------------
    print("Step 1: Fetching non-compliant list from RDS via Lambda…")
    sql = (
        "SELECT clockify_user_id, name, email, "
        "pod_assignment, practice_alignment, hours_submitted "
        "FROM vw_missing_time_submissions ORDER BY name"
    )
    db_result = invoke_lambda(
        "production-clockify-import",
        {"mode": "run_query", "sql": sql},
        args.profile, args.region
    )

    columns = db_result.get("columns", [])
    rows    = db_result.get("rows", [])
    print(f"  → {len(rows)} non-compliant user(s) found in RDS")

    if not rows:
        print("\nNo non-compliant users found — nothing to validate.")
        return

    # Build list of dicts
    staff = [dict(zip(columns, row)) for row in rows]

    # ------------------------------------------------------------------
    # Step 2: Retrieve Clockify credentials
    # ------------------------------------------------------------------
    print("\nStep 2: Retrieving Clockify credentials from Secrets Manager…")
    secrets = get_secret("production/weekly-reporting/secrets", args.profile, args.region)
    api_key      = secrets["clockify_api_key"]
    workspace_id = secrets["clockify_workspace_id"]
    print(f"  → Workspace ID: {workspace_id}")
    print(f"  → API key retrieved (length {len(api_key)})")

    # ------------------------------------------------------------------
    # Step 3: Query Clockify for each user
    # ------------------------------------------------------------------
    print(f"\nStep 3: Querying Clockify API for {len(staff)} user(s)…")
    print(f"  Week: {week_start}T00:00:00Z → {week_end}T23:59:59Z\n")

    clockify_start = f"{week_start}T00:00:00Z"
    clockify_end   = f"{week_end}T23:59:59Z"

    findings = []

    for i, user in enumerate(staff):
        user_id  = user["clockify_user_id"]
        name     = user["name"]
        email    = user["email"]
        pod      = user.get("pod_assignment") or "—"
        practice = user.get("practice_alignment") or "—"
        db_hours = float(user.get("hours_submitted", 0))

        path = (
            f"/workspaces/{workspace_id}/user/{user_id}/time-entries"
            f"?start={clockify_start}&end={clockify_end}&page-size=5"
        )

        try:
            entries = clockify_get(path, api_key)
            entry_count = len(entries) if isinstance(entries, list) else 0
        except RuntimeError as e:
            print(f"  [{i+1}/{len(staff)}] {name}: ERROR — {e}")
            findings.append({
                "name": name, "email": email, "pod": pod, "practice": practice,
                "db_hours": db_hours, "clockify_entries": "ERROR",
                "status": "ERROR", "notes": str(e)
            })
            time.sleep(0.15)
            continue

        # Classify
        if db_hours == 0 and entry_count == 0:
            status = "CONFIRMED"
            symbol = "✅"
        elif db_hours == 0 and entry_count > 0:
            status = "FALSE POSITIVE"
            symbol = "⚠️"
        elif db_hours > 0 and entry_count == 0:
            status = "DATA INTEGRITY"
            symbol = "🚨"
        else:
            status = "CONFIRMED"
            symbol = "✅"

        print(f"  [{i+1:2d}/{len(staff)}] {symbol} {name:<30} DB={db_hours:.1f}h  Clockify={entry_count} entries  → {status}")

        findings.append({
            "name": name, "email": email, "pod": pod, "practice": practice,
            "db_hours": db_hours, "clockify_entries": entry_count,
            "status": status, "notes": ""
        })

        # Respect Clockify rate limit (10 req/s)
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # Step 4: Summarise
    # ------------------------------------------------------------------
    total          = len(findings)
    confirmed      = sum(1 for f in findings if f["status"] == "CONFIRMED")
    false_positive = sum(1 for f in findings if f["status"] == "FALSE POSITIVE")
    data_integrity = sum(1 for f in findings if f["status"] == "DATA INTEGRITY")
    errors         = sum(1 for f in findings if f["status"] == "ERROR")

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"  Total non-compliant in DB   : {total}")
    print(f"  Confirmed non-compliant     : {confirmed}")
    print(f"  False positives             : {false_positive}")
    print(f"  Data integrity issues       : {data_integrity}")
    print(f"  Errors (API failures)       : {errors}")
    print(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Step 5: Write Markdown report
    # ------------------------------------------------------------------
    run_date = datetime.now().strftime("%Y-%m-%d")
    report_path = Path(__file__).parent.parent / "docs" / f"compliance-validation-{run_date}.md"

    # Sort: FALSE POSITIVE first, then CONFIRMED, then others
    status_order = {"FALSE POSITIVE": 0, "DATA INTEGRITY": 1, "ERROR": 2, "CONFIRMED": 3}
    findings_sorted = sorted(findings, key=lambda f: (status_order.get(f["status"], 9), f["name"]))

    lines = [
        f"# Compliance Accuracy Validation — {week_start} to {week_end}",
        f"",
        f"**Run date:** {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}  ",
        f"**Reporting week:** {week_start} (Mon) to {week_end} (Sun)  ",
        f"**Data source:** RDS `vw_missing_time_submissions` vs live Clockify API  ",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total non-compliant in DB | {total} |",
        f"| ✅ Confirmed non-compliant (matches Clockify) | {confirmed} |",
        f"| ⚠️ False positives (have Clockify entries, not yet imported) | {false_positive} |",
        f"| 🚨 Data integrity issues (DB has hours, Clockify has none) | {data_integrity} |",
        f"| ❌ API errors | {errors} |",
        f"",
        f"---",
        f"",
        f"## Findings",
        f"",
        f"| Employee | Email | Pod | Practice | DB Hours | Clockify Entries | Status |",
        f"|----------|-------|-----|----------|----------|-----------------|--------|",
    ]

    for f in findings_sorted:
        status_emoji = {
            "CONFIRMED": "✅ CONFIRMED",
            "FALSE POSITIVE": "⚠️ FALSE POSITIVE",
            "DATA INTEGRITY": "🚨 DATA INTEGRITY",
            "ERROR": "❌ ERROR",
        }.get(f["status"], f["status"])
        lines.append(
            f"| {f['name']} | {f['email']} | {f['pod']} | {f['practice']} "
            f"| {f['db_hours']:.1f} | {f['clockify_entries']} | {status_emoji} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## Interpretation",
        f"",
        f"- **✅ CONFIRMED** — User has 0 hours in both RDS and Clockify. Genuinely non-compliant for the week.",
        f"- **⚠️ FALSE POSITIVE** — User has 0 hours in RDS but has time entries in Clockify. The entries exist in Clockify",
        f"  but have not yet been imported into our database. These users should NOT be flagged in the weekly report.",
        f"  **Action:** Re-run the Lambda import to pull the latest data, then re-run this validation.",
        f"- **🚨 DATA INTEGRITY** — RDS shows hours but Clockify shows no entries. Unlikely; may indicate",
        f"  entries were deleted from Clockify after import, or a timezone/date mismatch in the query.",
        f"- **❌ ERROR** — Clockify API returned an error for this user. Manual verification required.",
        f"",
        f"---",
        f"",
        f"## Technical Details",
        f"",
        f"- **RDS query:** `SELECT ... FROM vw_missing_time_submissions`",
        f"- **Clockify endpoint:** `GET /workspaces/{{workspaceId}}/user/{{userId}}/time-entries`",
        f"- **Clockify date range:** `{clockify_start}` → `{clockify_end}`",
        f"- **Rate limiting:** 0.15s sleep between API calls",
        f"- **Script:** `scripts/validate_compliance_accuracy.py`",
    ]

    report_path.write_text("\n".join(lines) + "\n")
    print(f"Report saved to: {report_path}\n")

    # Return exit code 1 if false positives found (useful for CI)
    if false_positive > 0 or data_integrity > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
