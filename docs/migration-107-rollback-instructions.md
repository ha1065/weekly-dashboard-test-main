# Migration 107 — Rollback Instructions

**Date:** 2026-08-20
**Migration:** `107_strip_clockify_brace_formatting.sql`

---

## Important Notes

This migration **removes characters** (`{`, `}`, `"`, `\`) from stored values. It is not automatically reversible because the original braced values are not preserved anywhere after the UPDATE runs.

However, rollback is achievable because:
1. The Clockify API still returns braced values — a full re-import will restore them
2. The Python import strips braces at ingest — so re-import actually produces the **same clean state** the migration creates

If you genuinely need the braced values back (unlikely — there is no scenario where they're useful), follow the steps below.

---

## Rollback Option 1: Re-import from Clockify (recommended)

This restores the data to whatever Clockify currently has. Since the Python import strips braces, the result is identical to the post-migration state. Use this if the migration caused unexpected data corruption.

```bash
# Re-import all users (overwrites all user custom fields from Clockify)
aws lambda invoke --function-name production-clockify-import \
  --cli-binary-format raw-in-base64-out \
  --payload '{"mode": "full"}' \
  /tmp/response.json

cat /tmp/response.json
```

This re-fetches all users, projects, and 52 weeks of time entries from Clockify.

---

## Rollback Option 2: Restore braces (if absolutely needed)

**Warning:** This is NOT recommended. It re-introduces the formatting that causes bugs in Streamlit filters and mismatches with `lob_practice_mapping`. Only use this if you discover a dependency that explicitly requires braced values.

```sql
-- CAUTION: This wraps ALL non-null values in braces, even those that were never braced.
-- Only run this if you have confirmed which specific rows need braces restored.

-- clockify_users
UPDATE clockify_users
SET pod_assignment = '{' || pod_assignment || '}'
WHERE pod_assignment IS NOT NULL AND pod_assignment != '';

UPDATE clockify_users
SET practice_alignment = '{' || practice_alignment || '}'
WHERE practice_alignment IS NOT NULL AND practice_alignment != '';

UPDATE clockify_users
SET skill_area = '{' || skill_area || '}'
WHERE skill_area IS NOT NULL AND skill_area != '';

UPDATE clockify_users
SET location = '{' || location || '}'
WHERE location IS NOT NULL AND location != '';

UPDATE clockify_users
SET employment_designation = '{' || employment_designation || '}'
WHERE employment_designation IS NOT NULL AND employment_designation != '';

-- clockify_projects
UPDATE clockify_projects
SET pod_assignment = '{' || pod_assignment || '}'
WHERE pod_assignment IS NOT NULL AND pod_assignment != '';

UPDATE clockify_projects
SET project_type = '{' || project_type || '}'
WHERE project_type IS NOT NULL AND project_type != '';

UPDATE clockify_projects
SET professional_services_type = '{' || professional_services_type || '}'
WHERE professional_services_type IS NOT NULL AND professional_services_type != '';

UPDATE clockify_projects
SET professional_services_phase = '{' || professional_services_phase || '}'
WHERE professional_services_phase IS NOT NULL AND professional_services_phase != '';

-- clockify_detailed_time_entries
UPDATE clockify_detailed_time_entries
SET pod_assignment = '{' || pod_assignment || '}'
WHERE pod_assignment IS NOT NULL AND pod_assignment != '';

UPDATE clockify_detailed_time_entries
SET practice_alignment = '{' || practice_alignment || '}'
WHERE practice_alignment IS NOT NULL AND practice_alignment != '';

UPDATE clockify_detailed_time_entries
SET skill_area = '{' || skill_area || '}'
WHERE skill_area IS NOT NULL AND skill_area != '';

-- ps_project_mapping
UPDATE ps_project_mapping
SET pod_assignment = '{' || pod_assignment || '}'
WHERE pod_assignment IS NOT NULL AND pod_assignment != '';
```

**After running Option 2, you must also revert the code fix:**

```python
# src/integrations/analyze_project_health.py line 560
# Revert to:
practice_filter = "AND (cu.practice_alignment IS NULL OR cu.practice_alignment != '{\"Managed Cloud Services\"}')"
```

---

## Rollback Option 3: Point-in-time database restore

If you took a database snapshot before running the migration, restore from that snapshot. This is the cleanest full rollback but requires RDS snapshot availability and causes downtime.

```bash
# List available snapshots
aws rds describe-db-snapshots --db-instance-identifier <your-instance> \
  --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime]' \
  --output table

# Restore (creates a new instance — you'd need to swap endpoints)
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier <new-instance-name> \
  --db-snapshot-identifier <snapshot-id>
```

---

## Pre-Migration Checklist (before running 107)

- [ ] Take an RDS snapshot (provides clean rollback path)
- [ ] Confirm no active imports running (`SELECT * FROM import_logs WHERE status = 'running'`)
- [ ] Run during low-traffic window (the `time_entries` UPDATE may briefly lock the table)
- [ ] Have the `analyze_project_health.py` code fix ready to deploy immediately after

---

## Post-Migration Verification

```sql
-- All should return 0 rows:
SELECT COUNT(*) FROM clockify_users WHERE pod_assignment LIKE '{%';
SELECT COUNT(*) FROM clockify_users WHERE practice_alignment LIKE '{%';
SELECT COUNT(*) FROM clockify_projects WHERE pod_assignment LIKE '{%';
SELECT COUNT(*) FROM clockify_projects WHERE project_type LIKE '{%';
SELECT COUNT(*) FROM clockify_detailed_time_entries WHERE pod_assignment LIKE '{%' LIMIT 1;
SELECT COUNT(*) FROM clockify_detailed_time_entries WHERE practice_alignment LIKE '{%' LIMIT 1;
SELECT COUNT(*) FROM ps_project_mapping WHERE pod_assignment LIKE '{%';
```

```sql
-- Confirm distinct clean values look correct:
SELECT DISTINCT pod_assignment FROM clockify_users WHERE pod_assignment IS NOT NULL ORDER BY 1;
SELECT DISTINCT practice_alignment FROM clockify_users WHERE practice_alignment IS NOT NULL ORDER BY 1;
SELECT DISTINCT project_type FROM clockify_projects WHERE project_type IS NOT NULL ORDER BY 1;
```
