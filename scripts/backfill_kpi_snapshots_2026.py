#!/usr/bin/env python3
"""
Backfill KPI snapshots for all weeks in 2026 (2026-01-05 through 2026-06-29).
Invokes the production-clockify-import Lambda for each week via snapshot_kpis mode.
"""

import subprocess
import json
import sys
from datetime import date, timedelta

LAMBDA_FUNCTION = "production-clockify-import"
PROFILE = "AWSAdministratorAccess-961341524729"
REGION = "us-east-1"

# Generate all Monday dates from 2026-01-05 through 2026-06-29
weeks = []
w = date(2026, 1, 5)
while w <= date(2026, 6, 29):
    weeks.append(w.isoformat())
    w += timedelta(days=7)

print(f"Backfilling {len(weeks)} weeks: {weeks[0]} through {weeks[-1]}\n")

results = []
for week in weeks:
    payload = json.dumps({"mode": "snapshot_kpis", "week_start": week})
    out_file = f"/tmp/snap_{week}.json"

    result = subprocess.run(
        [
            "aws", "lambda", "invoke",
            "--function-name", LAMBDA_FUNCTION,
            "--profile", PROFILE,
            "--region", REGION,
            "--cli-binary-format", "raw-in-base64-out",
            "--payload", payload,
            out_file,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"{week}: ERROR invoking lambda — {result.stderr.strip()}")
        results.append((week, "INVOKE_ERROR", None, None))
        continue

    try:
        with open(out_file) as f:
            resp = json.load(f)
    except Exception as e:
        print(f"{week}: ERROR reading response — {e}")
        results.append((week, "READ_ERROR", None, None))
        continue

    # Lambda returns either the row dict or an error structure
    status = resp.get("statusCode", resp.get("status", "ok"))
    nb_p = resp.get("productive_nb_hours", resp.get("productive_nb_hours", "?"))
    nb_np = resp.get("nb_nonproductive_hours", "?")
    err = resp.get("errorMessage", "")

    if err:
        print(f"{week}: ERROR — {err[:120]}")
        results.append((week, "LAMBDA_ERROR", None, None))
    else:
        print(f"{week}: {status} | productive_nb_hours={nb_p} | nb_nonproductive_hours={nb_np}")
        results.append((week, status, nb_p, nb_np))

print(f"\n{'='*60}")
print(f"SUMMARY: {len([r for r in results if r[1] not in ('INVOKE_ERROR','READ_ERROR','LAMBDA_ERROR')])} of {len(weeks)} weeks succeeded")

errors = [r for r in results if r[1] in ("INVOKE_ERROR", "READ_ERROR", "LAMBDA_ERROR")]
if errors:
    print(f"\nFailed weeks:")
    for r in errors:
        print(f"  {r[0]}: {r[1]}")
    sys.exit(1)
