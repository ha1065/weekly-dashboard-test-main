# Weekly Reporting — Architecture & Fixes (High-Level)

**Date:** 2026-08-28
**Account:** 961341524729 | **Region:** us-east-1
**Purpose:** A single high-level view of (1) the current architecture, (2) the three data-accuracy fixes — NB Non-Productive, NB Productive (billable classifier), and Clockify brace removal — (3) the impact of the refactored Lambda, and (4) the proposed new ingestion architecture.

---

## 1. Current Architecture

The system pulls time-tracking data from Clockify and project data from Jira, stores it in RDS PostgreSQL, and serves executive dashboards through QuickSight. A single monolithic Lambda does all the work.

```
┌─────────────┐   ┌─────────────┐
│  Clockify   │   │    Jira     │
│     API     │   │    Cloud    │
└──────┬──────┘   └──────┬──────┘
       │                 │
       ▼                 ▼
┌─────────────────────────────────────────────┐
│   production-clockify-import (MONOLITH)       │
│   - src/lambda_handler.py — 2,034 lines       │
│   - 30 dispatch "modes" (import, jira, KPI,   │
│     views, compliance email, AI analysis,     │
│     11 diagnostics, run_query/run_migration)  │
│   - ~19 MB deployed ZIP, VPC-attached          │
│   - Deployed via shell script (outside CFN)   │
└──────────────────────┬────────────────────────┘
                       │ writes
                       ▼
┌─────────────────────────────────────────────┐
│   RDS PostgreSQL (single-AZ, db.t3.micro)     │
│   - Base tables (users, projects, entries)    │
│   - 50+ SQL views (create_views.sql, 139 KB)  │
│   - kpi_weekly_snapshots table                │
└──────────────────────┬────────────────────────┘
                       │ VPC data source (SSL disabled)
                       ▼
┌─────────────────────────────────────────────┐
│   QuickSight (47 SPICE datasets)              │
│   3 active dashboards: COO Operational,        │
│   Executive Summary, Weekly Reporting          │
└─────────────────────────────────────────────┘

Triggers: EventBridge (Mon 9 AM CT import, Mon noon CT KPI snapshot,
          daily 10 AM UTC Jira refresh, compliance email rules)
Secondary UI: ECS Fargate Streamlit dashboard (write ops, forecast uploads)
```

### Key characteristics and pain points

- **Single point of failure and change:** one 2,034-line handler with 30 modes. A bug in any mode shares the same execution environment as the production import. The full 19 MB package must be redeployed to fix any single mode.
- **IaC drift:** Lambda code, EventBridge payloads, and Bedrock/SES IAM permissions are managed outside CloudFormation. A stack update risks silently overwriting live behavior.
- **Reliability gaps:** single-AZ RDS, no DLQ on the import Lambda, migrations replay on every Streamlit restart (no tracking table), 9 duplicate migration numbers.
- **Accuracy gaps:** KPI values written by `kpi_snapshot.py` used the wrong classifier and formula (see §2), and older base data still carried Clockify's brace formatting (see §2.3).
- **Health at last check:** the import Lambda ran at ~35.6% error rate — core imports succeeded but the QuickSight-refresh tail failed (`get_quicksight_dataset_ids` NameError) and a view schema conflict (`42P16`) surfaced during view recreation.

---

## 2. Data-Accuracy Fixes

Three independent fixes correct the numbers the COO sees. Two are in the KPI computation logic (`kpi_snapshot.py`); one is a data-cleanup migration.

### 2.1 Fix — NB Non-Productive Hours

**Symptom:** The Weekly Pulse "NB Non-Productive Hours" tile showed ~0.00 when the true value was ~1,142 hrs/week (97% underreported for week 2026-06-29).

**Business definition (stakeholder-confirmed):** NB Non-Productive = per person, per week:

- **Component A (explicit):** hours logged to non-billable projects — `SUM(duration_hours WHERE billable = false)`
- **Component B (implicit):** unlogged capacity — `GREATEST(0, weekly_capacity − total_logged)`
- Total = `SUM(A + B)` across active, non-exempt staff.

**Two root-cause errors:**

1. Component A was computed correctly but written to the wrong column (`productive_nb_hours`) — the dashboard reads `nb_nonproductive_hours`, which only received Component B.

2. Component B was computed at the **aggregate** level (`max(0, total_available − total_logged)`), so one person's overtime cancelled another's idle time.

**The fix:** replace the two aggregate queries with a single **per-user** query that computes A and B per person, applies `GREATEST(0, …)` per user, then sums. Result for week 2026-06-29 moved from 0.00 → correct 1,142.33 hrs. No SQL migration needed (column already exists); requires Lambda redeploy plus a historical backfill and SPICE refresh.

### 2.2 Fix — NB Productive Hours (billable classifier)

**Symptom:** The "NB Productive Hours" tile showed ~802 hrs/week when the correct value was ~77 hrs/week — a ~10× over-count.

**Root cause:** `productive_nb_hours` counted **all** `billable = false` hours with no `project_type` filter. That sweeps in Overhead, Training/Certs, Internal Initiatives, Product Development, and Presales — all of which are productive non-billable work, not non-productive.

**The correct classifier** (matching `vw_productive_utilization`): NB Productive = `billable = false` **AND** `project_type IN ('Non Bill Productive', 'Overtime', 'Presales')` (plus mapped-client logic). Everything else that is `billable = false` is the residual NB Non-Productive.

**Status and dependency:** the billable/non-billable classifier audit (2026-07-07) flagged this as still open after the first NB Non-Productive fix. It also affects the `nb_logged` base of the NB Non-Productive metric: using raw `billable = false` there over-counts by ~147 hrs/week (1,142 vs the view-aligned ~995). The corrective step is to make `kpi_snapshot.py` use the same `project_type`-aware classifier the SQL views already use, so the KPI cards and the per-person utilization table agree.

**Note on the two metrics:** they are related but distinct. NB Non-Productive (§2.1) fixed the *formula* (per-user A + B). NB Productive (§2.2) fixes the *classifier* (project_type, not raw `billable`). Both must land for the Weekly Pulse tiles to reconcile with the row-level views.

### 2.3 Fix — Clockify Brace Removal (Migration 107)

**Symptom:** Clockify returns DROPDOWN custom-field values wrapped in braces — `{Bravo}`, `{"Professional Services"}`. Older data imported before the ingest-time strip still carries braces in the base tables, causing:

- Duplicate filter values (`Bravo` vs `{Bravo}`)
- Missed rows on exact-match queries (`IN ('Alpha','Bravo')` misses `{Alpha}`)
- Every SQL view carrying a 4-layer `REPLACE(REPLACE(REPLACE(REPLACE(...)))` on every read.

**The fix:** Migration `107` applies `TRIM(REPLACE(REPLACE(REPLACE(REPLACE(col,'{',''),'}',''),'"',''),'\',''))` to the affected columns across four tables (`clockify_users`, `clockify_projects`, `clockify_detailed_time_entries`, `ps_project_mapping`). It is idempotent (a no-op on already-clean data) and loses no data — only formatting noise.

**Impact:**

- **Safe / no change:** all SQL views (their REPLACE becomes a no-op), KPI snapshot (`ILIKE` matching), forecast, MC audit, QuickSight dashboards, and the Python import path (already strips at ingest).
- **One code fix required:** `analyze_project_health.py:560` explicitly matched the **braced** form `'{"Managed Cloud Services"}'`. After cleanup that filter would never match, so it must change to `'Managed Cloud Services'`, then redeploy the Lambda.
- **Fixed for free:** five currently-broken Streamlit filters/counts (POD multiselect duplicates, MC resource count misses, practice distribution display) become correct automatically.

---

## 3. Impact of the Refactored Lambda

The current-state assessment recommends **not** aggressively splitting the monolith for an internal tool, but applying targeted refactors. The proposed ingestion spec goes further and decomposes it into single-responsibility functions. The impact either way:

### 3.1 What changes

- **Diagnostic modes retired (11 modes, ~400 lines):** `diagnose_*` and `debug_*` modes are removed from the handler. Ad-hoc queries move to a direct RDS connection via SSM port-forward. This shrinks the handler and reduces attack surface.
- **`run_query` / `run_migration` gated:** arbitrary SQL execution against production (invokable by anyone with `lambda:InvokeFunction`) is removed or placed behind an allowlist. This also eliminates the known duplicate-definition bug (`run_migration` defined twice; the second silently overrides the first).
- **Import path isolated:** separating the production import from AI analysis, compliance email, and diagnostics means a failure in one no longer shares the import's execution environment or its oversized 900s timeout.

### 3.2 Positive impact

- **Blast radius reduced:** a fault in analysis or diagnostics can no longer break the Monday import.
- **Right-sized timeouts and memory:** short operations (e.g., QuickSight refresh) no longer inherit a 15-minute timeout.
- **Smaller packages, faster cold start:** removing heavy/rarely-used code paths shrinks the deployment from ~19 MB toward ~2 MB for the extraction functions.
- **Security surface shrinks:** no arbitrary SQL path, fewer IAM permissions per function (least privilege per role).

### 3.3 Risks to manage during refactor

- **IaC reconciliation first:** because Bedrock/SES permissions and EventBridge payloads live outside CloudFormation today, they must be brought into IaC *before* any stack update — otherwise the refactor deploy silently deletes them and breaks compliance email and AI analysis.
- **KPI fixes must ship with the redeploy:** the NB Non-Productive and NB Productive fixes (§2.1–2.2) and the `analyze_project_health.py` brace fix (§2.3) all require a Lambda redeploy plus a historical backfill and SPICE refresh. Sequence these together to avoid multiple redeploys.

---

## 4. Proposed New Architecture (Ingestion Pipeline Spec)

Replace the monolithic Lambda with an **AWS Step Functions** pipeline orchestrating lightweight, single-responsibility Lambdas. Raw API responses land immutably in S3, transforms produce Parquet, and Glue/Athena serve QuickSight — removing RDS from the read path and eliminating the VPC dependency.

```
EventBridge (Mon 9 AM CT / daily Jira / monthly full sync)
              │
              ▼
┌───────────────────────────────────────────────────────────┐
│         Step Functions: WeeklyIngestionPipeline             │
│                                                             │
│  ┌──────────┐   ┌──────────┐  (parallel extract)           │
│  │ clockify │   │   jira   │                                │
│  │  import  │   │  import  │                                │
│  └────┬─────┘   └────┬─────┘                                │
│       └──────┬───────┘                                      │
│              ▼                                              │
│      ┌───────────────────┐   ┌──────────────────┐          │
│      │ transform-and-     │──▶│ quicksight-      │          │
│      │ snapshot (Parquet  │   │ refresh (SPICE)  │          │
│      │ + KPI compute)     │   └──────────────────┘          │
│      └───────────────────┘                                  │
│   Retries, Catch, SNS success/partial/failure notifications │
└───────────────────────────────────────────────────────────┘
              │
              ▼
┌───────────────────────────────────────────────────────────┐
│   S3 Data Lake  s3://cdx-reporting-{env}/                   │
│   raw/     (immutable JSON, date-partitioned, versioned)    │
│   curated/ (Parquet, partitioned by week_start / snapshot)  │
│   athena-results/ (7-day lifecycle)                         │
└──────────────────────┬────────────────────────────────────┘
                       ▼
┌───────────────────────────────────────────────────────────┐
│   Glue Data Catalog + Athena (database: cdx_reporting)      │
│   Tables: time_entries, users, projects, jira_projects,     │
│           kpi_snapshots  |  Views: weekly summary, util…    │
└──────────────────────┬────────────────────────────────────┘
                       ▼
┌───────────────────────────────────────────────────────────┐
│   QuickSight (Athena data source — no VPC)                  │
│   ~12 consolidated SPICE datasets (down from 47)            │
└───────────────────────────────────────────────────────────┘
```

### 4.1 Components

| Component | Responsibility |
|-----------|----------------|
| `clockify-import` Lambda | Pure extraction of users/projects/entries → raw JSON in S3. No DB, no VPC. ~2 MB. |
| `jira-import` Lambda | Extract PS/MC issues + custom fields → raw JSON in S3. No VPC. |
| `transform-and-snapshot` Lambda | Read raw JSON, flatten to Parquet in `curated/`, compute weekly KPIs. Only function needing pandas/pyarrow; VPC only during transition for RDS write-back. |
| `quicksight-refresh` Lambda | Trigger SPICE ingestion on the consolidated datasets. |
| Step Functions | Orchestration: parallel extract, sequential transform, retries, catch, SNS alerts, full execution visibility. |
| S3 + Glue + Athena | Immutable raw store, Parquet curated layer, serverless SQL for QuickSight. |

### 4.2 Benefits over current

- **No VPC / no RDS in the read path:** QuickSight reads S3 via Athena; removes the SSL-disabled VPC data source and the single-AZ RDS availability risk.
- **Immutable, reprocessable raw data:** any historical week can be reprocessed from S3 without re-calling external APIs.
- **Observability:** Step Functions console shows each step at a glance; per-Lambda log groups; SNS success/partial/failure notifications.
- **Cost:** estimated **~$2/month** for the pipeline vs ~$85 today.
- **Dataset consolidation:** ~12 meaningful SPICE datasets replace the current 47 (mostly manual) datasets.

### 4.3 Migration approach (phased, reversible)

1. **Parallel write (wk 1–2):** run new pipeline alongside the monolith; both write; validate S3/Parquet parity against RDS views.
2. **Athena layer (wk 2–3):** deploy Glue crawler/tables + Athena views; build test dashboards on Athena.
3. **QuickSight cutover (wk 3–4):** switch datasets from RDS to Athena; validate all 3 dashboards; repoint EventBridge to Step Functions.
4. **Decommission (wk 4–5):** disable (not delete) old rules, keep RDS 2 weeks as safety net, then remove VPC SG, old Lambda, and RDS. S3 raw data allows reprocessing at any point → instant rollback by re-enabling old rules.

### 4.4 Where the §2 fixes live in the new design

The KPI computations move into `transform-and-snapshot`, computed from in-memory DataFrames rather than SQL. The **same corrected logic** must carry over: per-user A + B for NB Non-Productive, and the `project_type`-aware classifier for NB Productive. The brace issue disappears structurally — transforms flatten clean values from raw JSON, so no `REPLACE` layers are needed in the Athena views.

---

## 5. Summary

| Area | Current | After Fixes / New Architecture |
|------|---------|-------------------------------|
| Compute | 1 monolith Lambda, 30 modes, 19 MB | Step Functions + 4 single-purpose Lambdas (~2 MB each) |
| Read path | QuickSight → VPC → RDS (SSL off) | QuickSight → Athena → S3 (no VPC) |
| NB Non-Productive | 0.00 (aggregate, wrong column) | Per-user A + B → 1,142 hrs (correct) |
| NB Productive | ~802 hrs (raw billable=false) | ~77 hrs (project_type classifier) |
| Brace formatting | Braced values in base tables | Cleaned via Migration 107; structurally gone in new design |
| Reliability | Single-AZ RDS, no DLQ, migration replay | Immutable S3, retries, SNS alerts, reprocessable |
| Cost (pipeline) | ~$85/month | ~$2/month |

**Sequencing recommendation:** land the three accuracy fixes (with one combined Lambda redeploy + backfill + SPICE refresh) and reconcile IaC drift *before* beginning the ingestion-pipeline migration, so the new pipeline inherits correct KPI logic and a clean IaC baseline.

---

*Sources: `docs/ingestion-pipeline-spec.md`, `docs/nb-nonproductive-investigation-2026-07-07.md`, `docs/nb-nonproductive-full-audit-2026-07-07.md`, `docs/migration-107-strip-clockify-braces-impact.md`, `docs/current-state-assessment.md`, `docs/lambda-health-report.md`.*
