# Migration 107: Strip Clockify Brace Formatting from Base Tables

**Date:** 2026-08-20
**Status:** Awaiting approval
**Author:** Kiro (automated analysis)

---

## Problem Statement

Clockify's API returns DROPDOWN-type custom field values wrapped in JSON-like brace notation: `{Bravo}`, `{"Free Agent"}`, `{"Professional Services"}`. The Python import layer (`get_custom_field_value()`) strips these before writing to the database — but **older data** imported before this fix was added still contains braced values in the base tables.

This creates:
- Duplicate values in Streamlit filter dropdowns (`Bravo` vs `{Bravo}`)
- Missed rows when querying with exact string matches (e.g., `pod_assignment IN ('Alpha','Bravo')` misses `{Alpha}`)
- Every SQL view must apply a 4-layer `REPLACE(REPLACE(REPLACE(REPLACE(...)` on every read
- Any new query or integration that forgets the REPLACE gets incorrect results

---

## Migration Scope

### Tables to clean

| Table | Columns | Est. rows |
|-------|---------|-----------|
| `clockify_users` | `pod_assignment`, `practice_alignment`, `skill_area`, `location`, `employment_designation` | ~70 |
| `clockify_projects` | `pod_assignment`, `project_type`, `professional_services_type`, `professional_services_phase` | ~200 |
| `clockify_detailed_time_entries` | `pod_assignment`, `practice_alignment`, `skill_area` | ~100k+ |
| `ps_project_mapping` | `pod_assignment` | ~50 |

### Transformation applied

```sql
TRIM(REPLACE(REPLACE(REPLACE(REPLACE(column, '{', ''), '}', ''), '"', ''), '\', ''))
```

Same transformation already used in all SQL views — this makes the base data match what the views produce.

---

## Impact Analysis

### ✅ Safe — No changes needed

| Component | File | Why safe |
|-----------|------|----------|
| All SQL views (10+) | `src/database/create_views.sql` | Already apply REPLACE — becomes a no-op after migration |
| KPI snapshot | `src/integrations/kpi_snapshot.py` | Uses `ILIKE '%exempt%'` — matches regardless of braces |
| Forecast resources | `src/integrations/forecast_resources.py` | Applies REPLACE inline — becomes a no-op |
| Lambda diagnose_free_agents | `src/lambda_handler.py:1592` | Uses `REPLACE(...) = 'Free Agent'` — still matches after cleanup |
| MC V2 audit | `src/integrations/mc_v2_audit.py:69` | Uses `REPLACE(cp.pod_assignment...)` — becomes a no-op |
| lob_practice_mapping table | `migrations/102_lob_practice_mapping.sql` | Already stores clean values; views join with REPLACE on left side |
| QuickSight dashboards | — | Read from views which are already clean |
| Python import pipeline | `src/integrations/import_clockify_data.py` | Already strips braces before INSERT; future data is clean |
| auto_populate_mappings | `src/integrations/import_jira_data.py:731` | Reads `ClockifyProject.pod_assignment` — after migration this is clean |

### ⚠️ Requires code fix (1 file)

| File | Line | Current code | Problem | Fix |
|------|------|-------------|---------|-----|
| `src/integrations/analyze_project_health.py` | 560 | `cu.practice_alignment != '{"Managed Cloud Services"}'` | Explicitly matches the **braced** format. After migration, `practice_alignment` will be `Managed Cloud Services` (no braces), so this filter will never exclude anyone — all PS users will be included in MC project health analysis. | Change to `cu.practice_alignment != 'Managed Cloud Services'` |

### 🟢 Currently broken — fixed by migration (no code change needed)

| # | Component | Current bug | After migration |
|---|-----------|-------------|-----------------|
| 1 | Streamlit Time Entry Detail — POD multiselect (`app.py:388`) | `ClockifyTimeEntry.pod_assignment.distinct()` returns both `{Bravo}` and `Bravo` — duplicates in dropdown | Clean distinct values only |
| 2 | Streamlit Dashboard — MC resource count (`app.py:305`) | `pod_assignment.in_(['Alpha','Bravo','A2Z','SurePoint'])` misses entries stored as `{Alpha}` | All entries match correctly |
| 3 | Streamlit Settings — Practice distribution (`app.py:1735`) | Shows `{Professional Services}` raw in UI | Clean values displayed |
| 4 | Streamlit Resource Directory — POD filter (documented in `dashboard-technical-findings.md` RD-02) | Shows `{Bravo}` in filter dropdown | Clean values |
| 5 | Any ad-hoc SQL query against base tables | Must remember 4-layer REPLACE or get wrong results | Direct queries work correctly |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Table lock during UPDATE on large `time_entries` table | Low-Medium | Brief lock on table (~100k rows) | Run during off-hours; or batch in chunks of 10k if needed |
| Unknown code path matching on braced values | Very Low | That code path breaks | Full codebase grep completed — only `analyze_project_health.py:560` found |
| Future Clockify API changes | None | — | Python import already strips at ingest; this is defense-in-depth |
| Data loss | None | — | REPLACE only removes `{`, `}`, `"`, `\` characters — no data is lost, only formatting noise removed |

---

## Execution Plan

### Step 1: Apply migration SQL

File: `src/database/migrations/107_strip_clockify_brace_formatting.sql`

Cleans all 4 tables. Idempotent — safe to run multiple times (REPLACE on already-clean data is a no-op).

### Step 2: Fix code reference

File: `src/integrations/analyze_project_health.py` line 560

```python
# Before:
practice_filter = "AND (cu.practice_alignment IS NULL OR cu.practice_alignment != '{\"Managed Cloud Services\"}')"

# After:
practice_filter = "AND (cu.practice_alignment IS NULL OR cu.practice_alignment != 'Managed Cloud Services')"
```

### Step 3: Deploy Lambda

Redeploy the Lambda with the updated `analyze_project_health.py`.

### Step 4: Verify

```sql
-- Should return 0 rows after migration:
SELECT pod_assignment FROM clockify_users WHERE pod_assignment LIKE '{%';
SELECT practice_alignment FROM clockify_users WHERE practice_alignment LIKE '{%';
SELECT pod_assignment FROM clockify_detailed_time_entries WHERE pod_assignment LIKE '{%' LIMIT 5;
SELECT pod_assignment FROM clockify_projects WHERE pod_assignment LIKE '{%';
```

---

## Rollback

Not strictly needed — the migration is additive/cleaning (removes noise characters). The views will continue to work regardless since their REPLACE is a no-op on clean data.

If for some reason you need to restore braces: you cannot — but there is no scenario where braced values are desirable. The Python import already strips them, so any re-import produces clean data anyway.

---

## Post-Migration: Optional Cleanup

After confirming everything works, these REPLACE calls in views become dead code (no-ops). They can optionally be removed in a future migration for readability, but leaving them in place is harmless and provides defense-in-depth if Clockify ever changes their API behavior.
