# NB Non-Productive Full Audit — 2026-07-07

**Status:** Findings only — no fixes applied  
**Scope:** All NB Non-Productive and NB Productive visuals across COO Operational Dashboard and Weekly Reporting dashboard  
**Trigger:** kpi_snapshot.py fix applied (nb_nonproductive_hours now uses per-user: nb_logged + capacity_gap)  
**SPICE:** Refreshed after fix  

---

## 1. Visual Findings Table

| # | Visual ID | Sheet | Dataset | Column | Status | Issue |
|---|-----------|-------|---------|--------|--------|-------|
| 1 | `kpi-wp-nb-nonproductive` | Weekly Pulse | `kpi_snapshots` | `nb_nonproductive_hours` | ⚠️ NEEDS REVIEW | Fixed by kpi_snapshot.py, but the fix used `billable=false` as NB classifier — see §3 below |
| 2 | `kpi-wp-nb-productive` | Weekly Pulse | `kpi_snapshots` | `productive_nb_hours` | ❌ WRONG | `productive_nb_hours` counts ALL `billable=false` (802h/wk) — should be only project_type-classified productive NB (77h/wk); massive over-count |
| 3 | `kpi-tu-nb-nonproductive` | Time & Utilization | `kpi_snapshots` | `nb_nonproductive_hours` | ⚠️ NEEDS REVIEW | Same as #1 — same data source, same classifier question |
| 4 | `kpi-tu-nb-productive` | Time & Utilization | `kpi_snapshots` | `productive_nb_hours` | ❌ WRONG | Same as #2 — same data source, same wrong column |
| 5 | `tbl-util` table (line ~2440) | Time & Utilization | `productive_util` → `vw_productive_utilization` | `nb_productive_hours`, `nb_non_productive_hours` | ✅ CORRECT (with caveat) | View uses correct project_type classifier; NB Non-Productive = logged hours only (does NOT include capacity gap — this is by design for the row-level view) |
| 6 | `kpi-uh-nb-productive` KPI (line 2828) | Utilization History | `util_history` → `vw_utilization_history` | `nb_productive_hours` | ✅ CORRECT (with caveat) | View correctly classifies by project_type; but shows nb_productive as 77h, not 802h |
| 7 | `line-uh-trend` line chart (line 2873) | Utilization History | `util_history` → `vw_utilization_history` | `nb_productive_hours` | ✅ CORRECT (with caveat) | Same view, same correct classifier |
| 8 | `bar-uh-quarterly` bar chart | Utilization History | `util_history` → `vw_utilization_history` | `billable_hours` only | ✅ CORRECT | Does not reference NB columns |

---

## 2. Classifier Consistency Analysis

### The Core Question: Is `billable=false` the right NB classifier?

**Answer: It depends on which metric you are computing. They are different things.**

#### What `billable=false` means in Clockify data

From the live data (week of 2026-06-29), ALL `billable=false` hours break down as:

| project_type | Hours | NB Productive? | NB Non-Productive? |
|---|---|---|---|
| Overhead | 242.99 | ✅ productive | ❌ |
| Product Development | 167.83 | ✅ productive | ❌ |
| Training and Certs | 162.16 | ✅ productive | ❌ |
| Internal Initiatives | 103.00 | ✅ productive | ❌ |
| Presales | 76.87 | ✅ productive | ❌ |
| None (NULL project) | 43.38 | ❌ | ✅ non-productive |
| Managed Cloud | 6.00 | ❌ | ✅ non-productive |
| **Total billable=false** | **802.23** | **752.85 productive** | **49.38 non-productive** |

There are **zero entries** with `project_type = 'Non Bill Non Productive'` in the current data. The explicit NB NP project type is not being used in Clockify.

#### What each classifier produces

| Method | Column | Value (week 2026-06-29) | What it means |
|---|---|---|---|
| `billable=false` (kpi_snapshot `productive_nb_hours`) | `productive_nb_hours` | 802.23h | ALL non-billable — conflates productive+non-productive |
| `billable=false` + capacity_gap (kpi_snapshot `nb_nonproductive_hours`) | `nb_nonproductive_hours` | 1142.33h | All non-billable logged + all unlogged capacity |
| View project_type classifier (nb_productive) | `nb_productive_hours` | 77.37h | Only `Non Bill Productive` + `Overtime` + `Presales` project types |
| View project_type classifier (nb_non_productive) | `nb_non_productive_hours` | 638.98h | All `billable=false` that are NOT in the productive set |
| View `non_logged_hours` | `non_logged_hours` | 356.10h | Capacity − total logged (shown separately in the table) |

#### Why `billable=false` is the WRONG classifier for NB Non-Productive specifically

`billable=false` captures:
- Overhead, Training, Internal Initiatives, Product Development → **NB Productive** (752.85h)
- NULL project type, Managed Cloud → **NB Non-Productive** (49.38h)

Using `billable=false` as the NB Non-Productive classifier sweeps in ~752h of productive work per week as "non-productive." The kpi_snapshot.py fix did the opposite — it used `billable=false` for `nb_nonproductive_hours`, meaning it is counting all non-billable hours (including Overhead, Training, etc.) as non-productive.

---

## 3. Detailed Findings per Metric

### 3.1 `nb_nonproductive_hours` in `kpi_weekly_snapshots` (Visuals #1, #3)

**Current kpi_snapshot.py logic (after the fix):**
```python
# Per-user: nb_logged (billable=false) + capacity_gap
nb_logged = SUM(CASE WHEN te.billable = FALSE THEN te.duration_hours ELSE 0 END)
capacity_gap = GREATEST(0, daily_capacity * 5 - total_logged)
nb_nonproductive = nb_logged + capacity_gap
```

**What this computes for 2026-06-29:**

| Component | Value |
|---|---|
| nb_logged (all billable=false) | 783.23h |
| capacity_gap (unlogged capacity) | 359.10h |
| **nb_nonproductive_hours (snapshot)** | **1142.33h** |

**What vw_productive_utilization computes for the same week:**

| Component | Value |
|---|---|
| nb_non_productive_hours (view) | 638.98h |
| non_logged_hours (view, separate column) | 356.10h |
| **Sum of both (conceptually equivalent)** | **995.08h** |

**Discrepancy: 1142.33h (snap) vs 995.08h (view equivalent)**

The ~147h gap is because `nb_logged` in the snapshot (`billable=false`, 783h) includes ~725h of hours that the view classifies as **NB Productive** (Overhead, Training, etc.). The snapshot is overcounting NB Non-Productive by pulling in all non-billable work.

**Verdict for `nb_nonproductive_hours`:** ⚠️ NEEDS REVIEW — The fix applied the per-user capacity gap correctly, but the `nb_logged` component uses `billable=false` which includes NB Productive work. Whether this is intentional depends on the business definition of "NB Non-Productive" (see §4).

### 3.2 `productive_nb_hours` in `kpi_weekly_snapshots` (Visuals #2, #4)

**Current kpi_snapshot.py logic:**
```python
# From _compute_utilization():
nb_productive_hours = SUM(CASE WHEN te.billable = FALSE THEN te.duration_hours ELSE 0 END)
```

This counts **all** `billable=false` entries as productive, with no project_type filter.

**Actual values for 2026-06-29:**

| Source | nb_productive value |
|---|---|
| kpi_weekly_snapshots (snap) | **802.23h** |
| vw_productive_utilization (view) | **77.37h** |

**Discrepancy: 10× over-count.** The snapshot includes Overhead (243h), Training (162h), Internal Initiatives (103h), Product Development (168h), etc. as "NB Productive." The view correctly restricts to only `Non Bill Productive`, `Overtime`, and `Presales` project types.

**Verdict for `productive_nb_hours`:** ❌ WRONG — This was not addressed by the kpi_snapshot.py fix and is significantly overcounting NB Productive.

### 3.3 `nb_productive_hours` and `nb_non_productive_hours` in `vw_productive_utilization` (Visual #5)

**View logic (from pg_views live definition — matches create_views.sql):**

NB Productive =
```sql
te.billable = FALSE AND (
  cp.project_type IN ('Non Bill Productive', 'Overtime', 'Presales')
  OR (cp.project_type IS NULL AND mc.client_lower IS NOT NULL)
  OR (cp.project_type NOT IN ('Non Bill Productive','Non Bill Non Productive','Overtime','Presales')
      AND cp.project_type IS NOT NULL AND mc.client_lower IS NOT NULL)
)
```

NB Non-Productive = `billable=false AND NOT IN (above productive set)`

This logic is sound. However there is a subtle point: `mapped_clients` join currently contributes **0 hours** to NB Productive for the current week — the client-name match is not triggering. The 77h of NB Productive in the view are from actual `Non Bill Productive`/`Overtime`/`Presales` project types only.

**The view `nb_non_productive_hours` is logged hours only** — it does not include the capacity gap. The capacity gap is shown as the separate `non_logged_hours` column.

**Verdict for vw_productive_utilization:** ✅ CORRECT — classifier logic is consistent with create_views.sql definition. Column semantics (logged hours only, no capacity gap) are appropriate for a row-level per-employee view. The `non_logged_hours` column correctly shows the remaining capacity.

### 3.4 `vw_utilization_history` (Visuals #6, #7)

`vw_utilization_history` is a pure pass-through view that adds date dimension columns to `vw_productive_utilization`. It inherits the same data with no additional transformation.

**Verdict:** ✅ CORRECT — inherits the correct view logic.

---

## 4. The Classifier Inconsistency (Critical Finding)

### Two fundamentally different NB definitions in use

| System | NB Non-Productive Definition | NB Productive Definition |
|---|---|---|
| `kpi_snapshot.py` | ALL `billable=false` logged + capacity gap | ALL `billable=false` logged (no project_type filter) |
| `vw_productive_utilization` | `billable=false` AND NOT project_type-productive AND NOT mapped_client + unlogged shown separately | `billable=false` AND project_type IN ('Non Bill Productive', 'Overtime', 'Presales') OR mapped_client |

These are not comparable metrics. A single KPI card labelled "NB Non-Productive Hours" on the Weekly Pulse shows a different number from the "NB Non-Productive" column in the Productive Utilization by Person table on the same sheet, by a factor of ~1.7×.

### Specific hours discrepancy (2026-06-29):

| Metric | kpi_snapshot value | View value | Ratio |
|---|---|---|---|
| NB Non-Productive | 1142.33h | 638.98h + 356.10h non-logged | 1.15× (if adding non_logged) or 1.79× (view nb_non_prod alone) |
| NB Productive | 802.23h | 77.37h | **10.4×** |

The NB Productive divergence is the most severe — 10× over-count in the snapshot KPI cards.

### The `project_type = 'Non Bill Non Productive'` issue

The `create_views.sql` comments reference `project_type = 'Non Bill Non Productive'` as the NB NP classifier. However the **live data has zero entries with this project_type** over the last 4+ weeks. This means:
- In `create_views.sql` line 2060: `WHEN NOT billable AND project_type = 'Non Bill Non Productive' THEN duration_hours` → returns 0
- The actual NB Non-Productive classification in `vw_productive_utilization` comes from the residual of all `billable=false` entries that don't match the productive patterns
- The `project_type = 'Non Bill Non Productive'` Clockify type is either not in use, or has been replaced by other project_types in practice

---

## 5. Summary of All Questions Answered

### Q1: Is `billable=false` the correct classifier for NB Non-Productive in kpi_snapshot.py?

**No.** `billable=false` includes NB Productive work (Overhead, Training, Internal Initiatives, Product Development — 752h/wk). Using it as the NB Non-Productive classifier results in a ~10× over-count of NB Productive and a ~1.2–1.8× over-count of NB Non-Productive.

The kpi_snapshot.py fix correctly introduced per-user capacity gap accounting, but the `nb_logged` component (used as the base for NB Non-Productive) should use the same project_type classifier as `vw_productive_utilization` — not a raw `billable=false` filter.

### Q2: Are `productive_util` and `util_history` datasets computing NB Non-Productive correctly?

**Yes**, with one caveat. `vw_productive_utilization` and `vw_utilization_history` use a sound project_type-based classifier. The only caveat is that the view separates non-logged hours into `non_logged_hours` rather than rolling them into `nb_non_productive_hours`. This is the correct design for a row-level view (per-employee data). If you want to match the KPI snapshot's "total unproductive time" concept, you would sum `nb_non_productive_hours + non_logged_hours`.

### Q3: Do any SQL views need to be updated?

**The live view in the database matches create_views.sql.** The view logic is internally consistent. No view SQL changes are needed for the view itself to be correct.

However, there is one potential issue in `create_views.sql`: some views (e.g., the one at line ~2060 in `vw_non_billable_project_analysis`) use `project_type = 'Non Bill Non Productive'` as an explicit classifier. Since no entries have this project_type in live data, those specific calculations will always return 0.

### Q4: Does `productive_nb_hours` in kpi_weekly_snapshots need the same per-user fix that was applied to `nb_nonproductive_hours`?

**Yes, but more than a per-user fix is needed.** `productive_nb_hours` has two problems:
1. **Wrong classifier**: counts all `billable=false` instead of only project_type-classified productive NB
2. **No project_type join**: the current SQL does not join `clockify_projects` for the productive hours calculation, so it cannot distinguish Overhead/Training from actual NB Productive work

The `nb_nonproductive_hours` fix addressed the per-user capacity gap but did not fix the `productive_nb_hours` column, and the classifier problem in `nb_nonproductive_hours` itself was not fully addressed.

---

## 6. Recommended Fixes (NOT applied — audit only)

### Fix 1 (Critical): `productive_nb_hours` in kpi_snapshot.py

Replace the current `billable=false` count with a project_type-aware classifier matching `vw_productive_utilization`:

```python
# WRONG (current):
CASE WHEN te.billable = FALSE THEN te.duration_hours ELSE 0 END AS nb_productive_hours

# CORRECT (should be):
CASE WHEN te.billable = FALSE
     AND (   cp.project_type IN ('Non Bill Productive', 'Overtime', 'Presales')
          OR cp.project_type IS NULL  -- or mapped_client logic
     ) THEN te.duration_hours ELSE 0 END AS nb_productive_hours
```

This would change `productive_nb_hours` from ~802h to ~77h for week 2026-06-29.

### Fix 2 (High): `nb_nonproductive_hours` classifier in kpi_snapshot.py

The `nb_logged` component in the per-user NB Non-Productive calculation currently uses `billable=false` (capturing 783h including productive NB work). It should use only the residual non-productive NB logged hours:

```python
# WRONG (current nb_logged):
SUM(CASE WHEN te.billable = FALSE THEN te.duration_hours ELSE 0 END)

# CORRECT (should match view's nb_non_productive_hours):
SUM(CASE WHEN te.billable = FALSE
         AND NOT (cp.project_type IN ('Non Bill Productive','Overtime','Presales'))
         THEN te.duration_hours ELSE 0 END)
```

This would change `nb_nonproductive_hours` from 1142h to approximately 995–1000h for week 2026-06-29 (638h logged non-productive + ~359h capacity gap).

### Fix 3 (Low): `project_type = 'Non Bill Non Productive'` references in create_views.sql

Since no Clockify entries use this project_type, the explicit `WHEN project_type = 'Non Bill Non Productive' THEN ...` clauses in `vw_non_billable_project_analysis` and related views always return 0. These are not causing harm but are dead code that should either be documented or removed.

---

## 7. Data Verification Numbers (reference for fix validation)

All values from week starting 2026-06-29:

| Metric | Current snap value | Correct target (view-aligned) |
|---|---|---|
| `productive_nb_hours` | 802.23h | ~77.37h |
| `nb_nonproductive_hours` | 1142.33h | ~995h (638h logged NNP + 359h cap gap) |
| View `nb_productive_hours` | 77.37h | ✅ correct |
| View `nb_non_productive_hours` | 638.98h | ✅ correct |
| View `non_logged_hours` | 356.10h | ✅ correct |

Historical kpi_weekly_snapshots (for reference after fixes would be applied to backfill):

| week_start_date | productive_nb_hours (current) | nb_nonproductive_hours (current) |
|---|---|---|
| 2026-07-06 | NULL | 0.00 |
| 2026-06-29 | 802.23 | 1142.33 |
| 2026-06-22 | 1080.52 | 1332.82 |
| 2026-06-15 | 735.13 | 1064.21 |
| 2026-06-08 | 711.30 | 1036.60 |
| 2026-06-01 | 692.39 | 1041.89 |

---

## 8. Dataset and View Lineage

```
kpi-wp-nb-nonproductive  (KPI visual, Weekly Pulse)
kpi-tu-nb-nonproductive  (KPI visual, Time & Utilization)
    └── kpi_snapshots dataset (kpi-weekly-snapshots-prod)
        └── kpi_weekly_snapshots table
            └── kpi_snapshot.py (WRONG: billable=false as NB classifier)

kpi-wp-nb-productive     (KPI visual, Weekly Pulse)
kpi-tu-nb-productive     (KPI visual, Time & Utilization)
    └── kpi_snapshots dataset
        └── kpi_weekly_snapshots table
            └── kpi_snapshot.py (WRONG: all billable=false counted as productive, 10× over-count)

tbl-util (table visual, Time & Utilization)
    └── productive_util dataset → vw_productive_utilization (CORRECT)
        └── project_type-based classifier
        └── nb_non_productive_hours = logged NNP hours only (no capacity gap — by design)
        └── non_logged_hours = capacity gap (separate column)

kpi-uh-nb-productive (KPI, Utilization History)
line-uh-trend (line chart, Utilization History)
    └── util_history dataset → vw_utilization_history (CORRECT)
        └── pass-through of vw_productive_utilization
```

---

*Audit completed: 2026-07-07. No fixes applied.*
