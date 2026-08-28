# Runbook: Database View Deploy Procedure

## Two Deploy Paths

| Path | When to Use |
|---|---|
| **Migration file (preferred)** | Any planned view change — ensures the change is versioned, tracked in `schema_migrations`, and reproducible |
| **`apply_views` Lambda mode (emergency only)** | Hotfix for a broken production view when the next scheduled deploy is too slow |

Always use a migration file for planned work. Reserve direct `apply_views` for emergencies.

---

## Path 1: Migration File (Preferred)

### Naming Convention

Migration files live in `src/database/migrations/` and are named:

```
NNN_description.sql
```

- `NNN` is a zero-padded 3-digit sequence number
- Next available number: **099**
- Use lowercase, underscore-separated description

Examples: `099_add_vw_utilization_history.sql`, `100_fix_vw_project_hours_summary.sql`

### Creating and Applying a Migration

**Step 1 — Create the migration file:**

```bash
# Example: create migration 099
cat > src/database/migrations/099_your_description.sql << 'EOF'
-- Migration 099: describe what this changes and why
DROP VIEW IF EXISTS vw_your_view;
CREATE OR REPLACE VIEW vw_your_view AS
SELECT ...;
EOF
```

**Step 2 — Deploy Lambda and apply views:**

```bash
bash scripts/update_lambda_and_apply_views.sh
```

This script packages the Lambda, uploads to S3, updates the function code, and invokes `{"mode":"apply_views"}` to run all pending migrations.

**Step 3 — Verify:**

The Streamlit app auto-applies pending migrations on restart (idempotent — migrations already recorded in `schema_migrations` are skipped). Migrations are safe to re-run against a production DB that already has the migration applied.

---

## Path 2: Emergency View Fix (No Migration)

Use only when a production view is broken and the Monday import is failing right now.

```bash
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"apply_views"}' \
  --cli-binary-format raw-in-base64-out \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  /tmp/av.json && cat /tmp/av.json
```

This re-applies all views from the current Lambda package. It does **not** create a migration record. Follow up with a proper migration file in the next sprint to formalize the fix.

---

## Post-Deploy Verification

After any view change (migration or emergency), verify that:

```bash
# 1. SPICE datasets that depend on the changed view are healthy
python3 scripts/check_spice_health.py

# 2. Dashboard accuracy — spot-check key metrics haven't changed unexpectedly
python3 scripts/dashboard_accuracy_audit.py
```

If `check_spice_health.py` shows a dataset as FAILED after the view fix, re-trigger it:

```bash
aws quicksight create-ingestion \
  --aws-account-id 961341524729 \
  --data-set-id <dataset-id> \
  --ingestion-id manual-$(date +%s) \
  --region us-east-1 \
  --profile AWSAdministratorAccess-961341524729
```

---

## ⚠️ WARNING: CloudFormation Deploy Safety Check

**Never run `cloudformation deploy` on the `weekly-reporting-production` stack without first running:**

```bash
python3 scripts/check_eventbridge_targets.py
```

**Why:** The `cloudformation/template.yaml` EventBridge rule targets contain hardcoded Lambda payload JSON. A CloudFormation deploy will overwrite any manually applied payload changes (e.g., the corrected `quicksight_dataset_ids` list added to the Monday noon rule) with whatever is in the template at deploy time.

The safety check script compares the live EventBridge rule targets against what CloudFormation would deploy and flags any discrepancies. Resolve all discrepancies by updating `template.yaml` before deploying.
