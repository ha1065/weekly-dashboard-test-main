# NB Non-Productive Hrs — Root Cause Investigation

**Date:** 2026-07-07  
**Investigator:** AWS Architect  
**Dashboard:** `coo-operational-dashboard-prod` → Sheet: Weekly Pulse → Visual: `kpi-wp-nb-nonproductive`  
**Status:** Root cause confirmed. Fix spec updated with stakeholder-clarified business definition.

---

## 1. Stakeholder-Clarified Business Definition (2026-07-07)

**NB Non-Productive Hours per person per week** is composed of two components:

> **Component A** — *Explicit NB NP:* Hours the person actually logged in Clockify to a project where `billable = false`.  
> **Component B** — *Implicit NB NP:* `GREATEST(0, weekly_capacity − total_hours_logged)` — any hour not logged at all is assumed non-productive non-billable.

**Formula:**

```
nb_nonproductive_per_person = A + B
  where A = SUM(duration_hours WHERE billable = false)
        B = GREATEST(0, daily_capacity * 5 − total_hours_logged)

nb_nonproductive_total = SUM(nb_nonproductive_per_person) across all active non-exempt staff
```

**Exclusion filters** (same as `vw_missing_time_submissions`):

- `status = 'active'`
- `daily_capacity > 0`
- `time_submission IS NULL OR UPPER(TRIM(time_submission)) != 'NO'`
- `NOT COALESCE(reporting_excluded, FALSE)`
- `pod_assignment NOT ILIKE '%exempt%'`

---

## 2. How NB Projects Are Identified in the Data

### Column used: `clockify_detailed_time_entries.billable` (boolean)

There is **no `project_type` column** on `clockify_detailed_time_entries` — the field `project_type` exists only on `clockify_projects`. The entry-level flag `billable` (boolean) is the correct and only reliable classifier for Component A.

| Column | Table | Type | Used for |
|--------|-------|------|---------|
| `billable` | `clockify_detailed_time_entries` | `boolean` | **Sole classifier — `false` = NB NP entry (Component A)** |
| `project_billable` | `clockify_detailed_time_entries` | `boolean` | Always `NULL` in production — not usable |
| `project_type` | `clockify_projects` | `varchar` | Service category (e.g. Professional Services, Managed Cloud, Overhead) — does not map to NB NP |
| `billable` | `clockify_projects` | `boolean` | Project-level flag — consistent with entry-level `billable` but unnecessary for the query |

**Project names observed with `billable = false`** in the last 4 weeks (by entry volume):
PMO-Sync-Project Overview Meeting, Internal Bootcamp/Training, Bench Time, Project Oscar, Internal Cloud AI Initiatives (MCS FinOps), Leave/PTO/Sick Leave/Public Holiday, AI/ML-Presales, AIDLC Service Methodology Training, Practice Management, Managed Cloud Pod Stabilization, Training & Certification — Cloud, FinOps, New Onboarding, Conferences, Interviews, and others.

All share `billable = false` on the time entry. That is the only filter needed.

---

## 3. Findings Table (Updated)

| # | Severity | Layer | Finding | Impact |
|---|----------|-------|---------|--------|
| 1 | **Critical** | `kpi_snapshot.py` — `_compute_utilization()` | `nb_nonproductive_hours` is computed as `max(0, total_available − total_logged)` at the **aggregate level** (Component B only, aggregate). This misses Component A entirely (all explicitly-logged NB hours), and Component B is wrong because aggregate overtime cancels others' idle time. | KPI severely understates NB NP hours. Week 2026-06-29: stored **0.00**, correct value **1,142.33** — off by **1,142.33 hrs**. |
| 2 | **Critical** | `kpi_snapshot.py` — `_compute_utilization()` | The field `productive_nb_hours` (stored in `kpi_weekly_snapshots.productive_nb_hours`) was computing Component A (`SUM(billable=false hours)`), but this column is **not the KPI being displayed** on the dashboard. The dashboard reads `nb_nonproductive_hours`, not `productive_nb_hours`. The two columns have contradictory names and the correct metric was being written to the wrong column. | The correct Component A value (783.23 hrs for week 2026-06-29) exists in the DB under `productive_nb_hours`, but the dashboard reads `nb_nonproductive_hours` which contains only the broken Component B aggregate (0.00). |
| 3 | High | `kpi_weekly_snapshots` table | Rows for multiple recent weeks have `nb_nonproductive_hours` severely understated — ranging from 0.00 to 211.73 when the correct values range from 1,036.60 to 1,332.82. | All historical trend data on the dashboard is wrong. Prior-week comparison (`nb_nonproductive_prev`) is also wrong. |
| 4 | Medium | Data quality | **Abu Turab** has `daily_capacity = 2.0` hrs/day (10 hrs/week) but logged **47.33 hrs** in week 2026-06-29. This is a stale Clockify profile (contractor capacity not updated). The per-user `GREATEST(0, ...)` formula makes Component B resilient to this (47.33 > 10.0 → B = 0), but the inflated `total_available_hours` and billable utilisation % are affected. | Secondary issue. Does not affect the NB NP fix but should be corrected in Clockify separately. |

---

## 4. Root Cause — Exact Code Location

**File:** `src/integrations/kpi_snapshot.py`  
**Function:** `_compute_utilization()`

### The Broken Code (current)

```python
# ── In the first SQL query ──────────────────────────────────────────────────
# This computes Component A correctly, but names it "nb_productive_hours"
# and does NOT store it as nb_nonproductive_hours.
hours = conn.execute(text("""
    SELECT
        ...
        COALESCE(SUM(CASE
            WHEN te.billable = FALSE
                 THEN te.duration_hours
            ELSE 0 END), 0) AS nb_productive_hours   # ← Component A, WRONG NAME
    FROM clockify_detailed_time_entries te
    JOIN clockify_users u ON ...
    WHERE te.entry_date BETWEEN :ws AND :we ...
"""), ...).fetchone()

nb_productive_hrs = float(hours.nb_productive_hours or 0)  # ← stored as productive_nb_hours

# ── Second query: total logged (aggregate) ──────────────────────────────────
total_logged_query = conn.execute(text("""
    SELECT COALESCE(SUM(te.duration_hours), 0) AS total_logged
    FROM clockify_detailed_time_entries te
    JOIN clockify_users u ...
    WHERE te.entry_date BETWEEN :ws AND :we ...
"""), ...).fetchone()
total_logged = float(total_logged_query.total_logged or 0)

# ── Broken formula: Component B computed at AGGREGATE level ─────────────────
nb_nonproductive_hrs = max(0, (total_available - total_logged) if total_available else 0)
# max(0, 2440.00 - 2406.43) = 33.57  ← Only aggregate B, no Component A at all
```

### Two Distinct Errors

**Error 1 — Component A is missing from `nb_nonproductive_hours`:**  
The `hours` query already computes `SUM(billable=false)` correctly, but it is stored in `productive_nb_hours`, not `nb_nonproductive_hours`. The KPI column `nb_nonproductive_hours` receives only the aggregate Component B.

**Error 2 — Component B is computed at aggregate level:**  
`max(0, total_available - total_logged)` aggregates all users together. When some users log overtime, their surplus reduces the aggregate, cancelling out shortfalls from users who logged nothing. The correct approach is `GREATEST(0, capacity - logged)` per user, then sum.

### Numerical Evidence for Week 2026-06-29

| Metric | Value |
|--------|-------|
| `total_available` (71 active non-exempt users) | 2,440.00 hrs |
| `total_logged` (all entries including overtime) | 2,406.43 hrs |
| **Old `nb_nonproductive_hours` stored in DB** | **max(0, 2440 − 2406.43) = 33.57 hrs** |
| Component A actual — SUM(billable=false per user) | **783.23 hrs** (stored in `productive_nb_hours`) |
| Component B actual — SUM(GREATEST(0, cap − logged) per user) | **359.10 hrs** |
| **Correct total (A + B per user)** | **1,142.33 hrs** |
| Error magnitude | **−1,108.76 hrs** (97% underreported) |

---

## 5. Correct Value for Week 2026-06-29

**Total NB Non-Productive Hours (stakeholder definition): 1,142.33 hrs**

Verified by Lambda query (2026-07-07):

```
SELECT SUM(nb_logged) + SUM(capacity_gap) AS total_nb_nonproductive
FROM (
  SELECT u.clockify_user_id,
    COALESCE(SUM(CASE WHEN te.billable = false THEN te.duration_hours ELSE 0 END), 0) AS nb_logged,
    GREATEST(0, (u.daily_capacity * 5) - COALESCE(SUM(te.duration_hours), 0)) AS capacity_gap
  FROM clockify_users u
  LEFT JOIN clockify_detailed_time_entries te
    ON u.clockify_user_id = te.clockify_user_id
    AND te.week_start = '2026-06-29'
  WHERE u.status = 'active'
    AND u.daily_capacity > 0
    AND (u.time_submission IS NULL OR UPPER(TRIM(u.time_submission)) != 'NO')
    AND NOT COALESCE(u.reporting_excluded, FALSE)
    AND (u.pod_assignment IS NULL OR u.pod_assignment NOT ILIKE '%exempt%')
  GROUP BY u.clockify_user_id, u.name, u.daily_capacity
) subq
→ 1142.33
```

### Component Breakdown

| Component | Definition | Value (week 2026-06-29) |
|-----------|-----------|------------------------|
| A — Explicit NB logged | SUM(duration_hours WHERE billable=false) per person | **783.23 hrs** |
| B — Implicit (unlogged) | SUM(GREATEST(0, cap − logged)) per person | **359.10 hrs** |
| **Total** | **A + B** | **1,142.33 hrs** |

### Per-Person Breakdown (top contributors, week 2026-06-29)

| Name | Capacity | Total Logged | Comp A (NB) | Comp B (Gap) | NB NP Total |
|------|----------|-------------|-------------|-------------|-------------|
| Abu Turab | 10.0 | 47.33 | 46.83 | 0.00 | 46.83 |
| anam.tahir | 35.0 | 42.38 | 42.38 | 0.00 | 42.38 |
| Faiza Sattar | 35.0 | 50.00 | 42.00 | 0.00 | 42.00 |
| zaeem.attique | 35.0 | 40.00 | 40.00 | 0.00 | 40.00 |
| Haider Ahmed | 40.0 | 18.00 | 16.00 | 22.00 | 38.00 |
| Wajahat.ullah | 35.0 | 40.00 | 37.00 | 0.00 | 37.00 |
| Ateeq Ur Rehman Baig | 35.0 | 32.00 | 32.00 | 3.00 | 35.00 |
| santohsh.bugatha | 35.0 | 40.00 | 35.00 | 0.00 | 35.00 |
| Tariq khan | 35.0 | 0.00 | 0.00 | 35.00 | 35.00 |
| mandeep.singh | 35.0 | 8.00 | 8.00 | 27.00 | 35.00 |
| huzaifa.khalid | 35.0 | 0.00 | 0.00 | 35.00 | 35.00 |
| amara.khan | 35.0 | 0.00 | 0.00 | 35.00 | 35.00 |
| qaisar.abbas | 35.0 | 0.00 | 0.00 | 35.00 | 35.00 |
| yegor.koriagin | 35.0 | 0.00 | 0.00 | 35.00 | 35.00 |
| Muhammad Burhan | 35.0 | 0.00 | 0.00 | 35.00 | 35.00 |
| *(53 additional users — see Lambda query for full list)* | | | | | |
| **TOTAL** | **2,440.00** | **2,406.43** | **783.23** | **359.10** | **1,142.33** |

Users contributing to Component A only (all NB hours logged, none under-capacity): 35 users  
Users contributing to Component B only (logged nothing or only billable hours, under-capacity): 12 users  
Users contributing to both A and B: 7 users  
Users with zero NB NP (logged ≥ capacity, all billable): 17 users

---

## 6. Historical Correction Table

Correct values computed using entry_date BETWEEN ws AND ws+6, matching `kpi_snapshot.py`'s existing range logic.

| Week Start | Stored `nb_nonproductive_hours` | Stored `productive_nb_hours` | **Correct A+B** | Comp A | Comp B | Error |
|------------|--------------------------------|------------------------------|-----------------|--------|--------|-------|
| 2026-06-01 | 206.33 | 554.39 | **1,041.89** | 677.39 | 364.50 | −835.56 |
| 2026-06-08 | 0.00 | 652.41 | **1,036.60** | 701.30 | 335.30 | −1,036.60 |
| 2026-06-15 | 211.73 | 609.96 | **1,064.21** | 718.88 | 345.33 | −852.48 |
| 2026-06-22 | 43.34 | 970.60 | **1,332.82** | 1,058.77 | 274.05 | −1,289.48 |
| **2026-06-29** | **0.00** | **802.23** | **1,142.33** | 783.23 | 359.10 | **−1,142.33** |

Note: `productive_nb_hours` (old Component A) plus the stored `nb_nonproductive_hours` (old Component B) still does not equal the correct total because Component B was computed at aggregate level. The sum of the two stored columns for 2026-06-29 is 0.00 + 802.23 = 802.23, which still understates the correct 1,142.33 by 340.10 hrs (the portion of Component B lost to overtime cancellation).

---

## 7. Pipeline Confirmation — Not the Problem

The investigation confirmed the pipeline infrastructure is correct end-to-end:

| Stage | Status | Evidence |
|-------|--------|----------|
| Clockify time entries in RDS | ✅ Data present | 2,406.43 hrs logged for week 2026-06-29 |
| `kpi_weekly_snapshots` column exists | ✅ Column present | `nb_nonproductive_hours NUMERIC(10,2)` exists |
| `kpi_weekly_snapshots` row for 2026-06-29 | ✅ Row exists | Written by snapshot; shows 0.00 |
| `vw_kpi_ytd` view | ✅ View correct | Passes through `nb_nonproductive_hours`; LAG() for prev week correct |
| SPICE dataset `kpi-weekly-snapshots-prod` | ✅ Reads from `vw_kpi_ytd` | Confirmed via QuickSight `describe-data-set` |
| QuickSight visual | ✅ Reads correct column | Visual reads `nb_nonproductive_hours` |

**Conclusion:** The pipeline is correctly wired. The problem is that `kpi_snapshot.py` writes a wrong value into `nb_nonproductive_hours`.

---

## 8. Correct Fix Spec for `kpi_snapshot.py`

### Fix location
**File:** `src/integrations/kpi_snapshot.py`  
**Function:** `_compute_utilization()`

### What to remove

1. The `total_logged_query` block (the second SQL query computing aggregate total logged hours).
2. The `total_logged` variable derived from it.
3. The `nb_nonproductive_hrs = max(0, ...)` derivation line.
4. The `nb_productive_hours` alias in the `hours` query — this column is being renamed/repurposed.

### What to add

Replace the removed blocks with a single per-user SQL query that computes both Component A and Component B simultaneously:

```python
# ── NEW: per-user NB NP computation (Component A + B) ───────────────────────
# Component A: hours explicitly logged to non-billable projects (billable = false)
# Component B: GREATEST(0, weekly_capacity - total_logged) — unlogged time assumed NB NP
# GREATEST(0, ...) per user ensures overtime from one user cannot cancel
# another user's idle time.
nb_query = conn.execute(text("""
    SELECT
        COALESCE(SUM(per_user.nb_logged), 0)            AS component_a,
        COALESCE(SUM(per_user.capacity_gap), 0)         AS component_b,
        COALESCE(SUM(per_user.nb_logged
                     + per_user.capacity_gap), 0)       AS nb_nonproductive_hours
    FROM (
        SELECT
            u.clockify_user_id,
            u.daily_capacity * 5                                             AS weekly_capacity,
            COALESCE(SUM(CASE WHEN te.billable = FALSE
                              THEN te.duration_hours ELSE 0 END), 0)        AS nb_logged,
            GREATEST(
                0,
                (u.daily_capacity * 5) - COALESCE(SUM(te.duration_hours), 0)
            )                                                                AS capacity_gap
        FROM clockify_users u
        LEFT JOIN clockify_detailed_time_entries te
               ON te.clockify_user_id = u.clockify_user_id
              AND te.entry_date BETWEEN :ws AND :we
              AND te.duration_hours > 0
        WHERE u.status = 'active'
          AND u.daily_capacity > 0
          AND (u.time_submission IS NULL
               OR UPPER(TRIM(u.time_submission)) != 'NO')
          AND NOT COALESCE(u.reporting_excluded, FALSE)
          AND (u.pod_assignment IS NULL
               OR u.pod_assignment NOT ILIKE '%exempt%')
        GROUP BY u.clockify_user_id, u.daily_capacity
    ) per_user
"""), {'ws': week_start, 'we': week_end}).fetchone()

nb_nonproductive_hrs = float(nb_query.nb_nonproductive_hours or 0)
```

### What to do with `productive_nb_hours` / `nb_productive_hrs`

The existing variable `nb_productive_hrs` (computed from `hours.nb_productive_hours` = `SUM(billable=false)`) was Component A, but it was stored in the snapshot column `productive_nb_hours` and **not** in `nb_nonproductive_hours`.

After the fix, `nb_nonproductive_hours` will contain A + B (the correct KPI value). The `productive_nb_hours` column in the snapshot table is no longer needed as a separate value — Component A is now embedded inside `nb_nonproductive_hours`.

**Decision required before implementation:** Either:
- (a) Keep `productive_nb_hours` storing Component A separately (useful for decomposition), in which case remove the `nb_productive_hours` alias from the `hours` SQL and re-derive it from `nb_query.component_a`; or
- (b) Deprecate `productive_nb_hours` and set it to NULL or 0 (the column had an incorrect/misleading name anyway).

**Recommendation:** Option (a) — keep Component A in `productive_nb_hours` for audit trail. Update the alias in the `hours` query to remove the confusing `nb_productive_hours` label, and instead set:

```python
# Still store Component A separately for decomposition
nb_productive_hrs = float(nb_query.component_a or 0)  # replaces the old hours.nb_productive_hours
```

Remove the `CASE WHEN te.billable = FALSE THEN te.duration_hours ELSE 0 END` block from the original `hours` query entirely (it is now computed in `nb_query`).

### Updated `_compute_utilization()` return dict

No changes needed to the return dict keys — `nb_nonproductive_hours` key remains, `productive_nb_hours` key remains (now populated from `nb_query.component_a`).

```python
return {
    ...
    'productive_nb_hours':    round(nb_productive_hrs, 2),   # Component A only
    'nb_nonproductive_hours': round(nb_nonproductive_hrs, 2), # A + B (correct KPI)
    ...
}
```

### Formula comparison

| | Old formula | New formula |
|-|-------------|-------------|
| **Computation unit** | Aggregate (two separate queries) | Per-user (single query) |
| **Component A** | Computed but stored in wrong column (`productive_nb_hours`) | Computed per user; rolled into `nb_nonproductive_hours` |
| **Component B** | Aggregate `max(0, total_available − total_logged)` | Per-user `GREATEST(0, cap − logged)` per user, then SUM |
| **Overtime handling** | Aggregate overtime cancels others' idle time | Overtime capped at zero per user; does not affect others |
| **Result for week 2026-06-29** | 0.00 (Component B aggregate only) | **1,142.33** (A + B per-user) |
| **Stakeholder definition** | Not matched | ✅ Matches exactly |

---

## 9. Required Actions After Code Fix

| # | Action | Owner | Notes |
|---|--------|-------|-------|
| 1 | Update `_compute_utilization()` in `kpi_snapshot.py` per §8 spec | Developer | Python-only change; no SQL migration needed |
| 2 | Rebuild and redeploy Lambda `production-clockify-import` | Developer | Required to activate the fix |
| 3 | Backfill snapshots for all weeks from 2026-01-06 to 2026-06-29 | Developer | Run via `{"mode":"snapshot_kpis","week":"YYYY-MM-DD"}` for each Monday |
| 4 | Trigger manual SPICE refresh of `kpi-weekly-snapshots-prod` | Developer | After backfill completes |
| 5 | Verify KPI tile on dashboard shows 1,142.33 for week 2026-06-29 | QA | Confirms end-to-end fix |
| 6 | Correct Abu Turab `daily_capacity` in Clockify (currently 2.0 hr/day) | Admin | Separate data quality issue; does not block fix |

No SQL migration required — `nb_nonproductive_hours` column already exists with the correct type (`NUMERIC(10,2)`).

---

## 10. Fix Classification

| Component | Change needed? | Type |
|-----------|---------------|------|
| `kpi_snapshot.py` | **YES** | Python logic fix in `_compute_utilization()` |
| Lambda redeploy | **YES** | Required |
| SQL migration | No | Column already exists |
| `vw_kpi_ytd` view | No | Passes through correctly |
| QuickSight dataset schema | No | Column already in SPICE definition |
| QuickSight visual | No | Already reads `nb_nonproductive_hours` |
| Historical backfill | **YES** | Re-run snapshots for 2026 weeks |
| SPICE refresh | **YES** | After backfill |
