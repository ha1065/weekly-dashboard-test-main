# COO Dashboard Theme Loss — Root Cause Analysis & Fix Plan

**Date:** 2026-07-01  
**Analyst:** AWS Architect  
**Affected Resource:** `coo-operational-dashboard-prod` (version 35)  
**Status:** Theme currently MISSING — dashboard showing AWS default theme

---

## Executive Summary

The CE brand theme was lost when dashboard version 35 was published at **18:02 ET on June 29, 2026**. The root cause is a structural gap in the IaC architecture: the `coo-dashboards-prod` CloudFormation stack manages only the **Analysis** (not the Dashboard), so every time someone republishes the dashboard via a script, the `ThemeArn` must be explicitly passed to `update_dashboard`. The specific trigger for v35 was one of the post-deploy scripts run during the P0-3 session that called `update_dashboard` without `ThemeArn`.

---

## 1. Root Cause Analysis

### How the theme is lost — the mechanism

The QuickSight API separates theme assignment into two independent objects:

| Object | ThemeArn | Controls |
|--------|----------|----------|
| `AWS::QuickSight::Analysis` | Set via `ThemeArn` property in CFN | How the analysis looks in the QuickSight editor |
| Dashboard (via `update_dashboard`) | Must be passed explicitly in **every** `update_dashboard` API call | What viewers see in the published dashboard |

**Critical API behaviour:** When you call `update_dashboard`, if you omit `ThemeArn`, QuickSight does **not** inherit it from the analysis or the previous dashboard version. It strips the theme entirely and falls back to the AWS default. There is no "preserve existing theme" behaviour — every `update_dashboard` call is authoritative.

This is confirmed by the version history:

| Version | ThemeArn | Created | Mechanism |
|---------|----------|---------|-----------|
| v32 | ✅ `cloudelligent-brand-theme` | 2026-06-15 | Script with `ThemeArn` |
| **v33** | ❌ `null` | **2026-06-23 10:31** | **Script without `ThemeArn`** |
| v34 | ✅ `cloudelligent-brand-theme` | 2026-06-29 14:05 | `restore_dashboard_theme.py` |
| **v35** | ❌ `null` | **2026-06-29 18:02** | **Script without `ThemeArn`** |

The theme was lost **twice** — once before the sprint (v33) and once during (v35). Version 34 was an intentional restoration that was immediately undone by v35 four hours later.

### Why the CFN deploy did NOT cause this

The `coo-dashboards-prod` stack contains exactly one resource: `CooOperationalAnalysis` (`AWS::QuickSight::Analysis`). It does **not** contain the dashboard. Confirmed via `describe-stack-resources`:

```
Type: AWS::QuickSight::Analysis
LogicalId: CooOperationalAnalysis
PhysicalId: coo-operational-analysis-prod|961341524729
```

The CFN deploy on June 26 at 21:26 UTC updated only the analysis (renaming `pWeekEnd` → `pWeekStart`). This has no effect on the published dashboard — the dashboard has its own `ThemeArn` state which is only changed by explicit `update_dashboard` calls.

### What `sync_coo_dashboard_iac.py` does to the theme

`sync_coo_dashboard_iac.py` calls `describe_analysis_definition`, which returns the **Definition** block. This block contains sheets, visuals, filters, and calculated fields — but **not** `ThemeArn`. `ThemeArn` is a top-level property of the Analysis/Dashboard resource, not part of the Definition.

The script correctly hardcodes `THEME_ARN` in `build_cloudformation()` and sets it on the `CooOperationalAnalysis` resource. However, because that resource is the Analysis — not the Dashboard — this only affects the editor view, not what viewers see.

### The specific culprit script

`scripts/add_tu_filters.py` is the only script in the repository that calls `update_dashboard` **without** any `ThemeArn` parameter:

```python
# add_tu_filters.py — lines 149-161
resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=coo['Name'],
    Definition=defn,
    VersionDescription='Add POD and Person filters to Time & Utilization sheet'
    # ← ThemeArn MISSING
)
```

This script was run during the sprint to add POD/Person filters to the Time & Utilization sheet. It likely produced v35 (or v33 for the earlier loss).

All other `update_dashboard` callers in the scripts directory either:
- Explicitly pass `ThemeArn=THEME_ARN` (hardcoded), or  
- Read the existing ThemeArn from `describe_dashboard` and conditionally pass it through (`if theme_arn: kwargs['ThemeArn'] = theme_arn`)

---

## 2. Current State

**Confirmed via live API calls (2026-07-01):**

| Resource | ThemeArn | Status |
|----------|----------|--------|
| Dashboard `coo-operational-dashboard-prod` v35 (current) | `null` ❌ | Theme missing — default AWS theme |
| Dashboard v34 (previous version) | `arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme` ✅ | Has CE theme |
| Analysis `coo-operational-analysis-prod` (CFN-managed) | `null` ❌ | Missing (does not affect dashboard viewers) |
| Analysis `0c48736d-0c17-4607-998c-4c2410d20025` (live editor) | `arn:...:theme/cloudelligent-brand-theme` ✅ | Has CE theme |
| Theme `cloudelligent-brand-theme` | — | EXISTS and is accessible |

**Note:** There are two separate analyses:
- `coo-operational-analysis-prod` — created and managed by the `coo-dashboards-prod` CFN stack
- `0c48736d-0c17-4607-998c-4c2410d20025` — the **live working analysis** that the dashboard was built from

The CFN-managed analysis (`coo-operational-analysis-prod`) currently has no ThemeArn set either, but this does not affect dashboard viewers.

---

## 3. Findings Table

| # | Severity | Area | Finding | Recommendation | Effort |
|---|----------|------|---------|----------------|--------|
| 1 | **Critical** | Dashboard | v35 has `ThemeArn: null` — dashboard is showing AWS default theme to all viewers | Run `restore_dashboard_theme.py` immediately (Option A) | Low — 1 min |
| 2 | **High** | Scripts | `add_tu_filters.py` calls `update_dashboard` without `ThemeArn` — this is the definitive cause of theme loss | Add `ThemeArn=THEME_ARN` to the call in `add_tu_filters.py` | Low — 1 line change |
| 3 | **High** | Architecture | Dashboard is not managed by CloudFormation — there is no IaC that ensures the dashboard always has the correct theme | Add `AWS::QuickSight::Dashboard` resource to `coo-dashboards.yaml` (Option B) | Medium |
| 4 | **Medium** | Scripts | `sync_coo_dashboard_iac.py` only syncs the Analysis definition, not the Dashboard. Developers may assume running sync + deploy also fixes the dashboard theme | Add a warning comment to `sync_coo_dashboard_iac.py` and update the Next Steps instructions to include `restore_dashboard_theme.py` | Low |
| 5 | **Medium** | Process | No verification step after publishing a new dashboard version to confirm the theme is still present | Add a post-publish assertion to `publish_coo_dashboard.py` and `restore_dashboard_theme.py` | Low |

---

## 4. Fix Options

### Option A — Script-based fix (immediate, 1 minute)

Run the existing `restore_dashboard_theme.py`. It:
1. Finds the CE theme (`cloudelligent-brand-theme`)
2. Gets the current dashboard definition (which already has the correct v35 content including all 3 new sheets)
3. Calls `update_dashboard` with the CE `ThemeArn`
4. Publishes the new version as the published version

**Exact command:**
```bash
cd /Users/cdx/weekly-reporting/weekly-reporting
python3 scripts/restore_dashboard_theme.py
```

Expected output:
```
  cloudelligent-brand-theme  Cloudelligent Brand Theme

Restoring theme: Cloudelligent Brand Theme (cloudelligent-brand-theme)
Version 36 created. Waiting 5s...
✅ Theme restored and version 36 published.
```

**Verification after running:**
```bash
aws quicksight describe-dashboard \
  --aws-account-id 961341524729 \
  --dashboard-id coo-operational-dashboard-prod \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --query 'Dashboard.Version.{Version:VersionNumber,ThemeArn:ThemeArn}'
```
Expected: `ThemeArn: "arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme"`

**Pros:** Immediate, zero risk, preserves all current content (all 8 sheets, pWeekStart parameter)  
**Cons:** Doesn't prevent recurrence

### Option B — IaC-based fix (durable, prevents recurrence)

Add a `AWS::QuickSight::Dashboard` resource to `coo-dashboards.yaml`. This makes the dashboard a managed CFN resource, ensuring `ThemeArn` is always set on every deploy.

**Exact change to `coo-dashboards.yaml`:**

Add after the `CooOperationalAnalysis` resource:

```yaml
  CooOperationalDashboard:
    Type: AWS::QuickSight::Dashboard
    DependsOn: CooOperationalAnalysis
    Properties:
      AwsAccountId: !Ref AwsAccountId
      DashboardId: !Sub coo-operational-dashboard-${Environment}
      Name: !Sub COO Operational Dashboard
      ThemeArn: !ImportValue CloudelligentQuickSightThemeArn
      SourceEntity:
        SourceTemplate:
          # Use the analysis as the source via a template reference.
          # Since we don't use AWS::QuickSight::Template, use Definition instead.
      # Note: AWS::QuickSight::Dashboard supports Definition property (same as Analysis)
      Definition: !GetAtt CooOperationalAnalysis.Definition
      # Note: GetAtt Definition is NOT supported — see below
```

**⚠️ Important limitation:** `AWS::QuickSight::Dashboard` does not support `!GetAtt` on the Analysis's Definition. The dashboard's Definition must be provided directly. This means `sync_coo_dashboard_iac.py` would need to embed the definition into both the Analysis AND the Dashboard resource in the same template — which is already what it does for the analysis section.

**Practical approach for Option B:**

Update `sync_coo_dashboard_iac.py` to also emit a `CooOperationalDashboard` resource in the same template, with the same `Definition` as the analysis and `ThemeArn: !ImportValue CloudelligentQuickSightThemeArn`. On every CFN deploy, both the analysis and the dashboard get updated atomically with the correct theme.

**Pros:** Theme is always correct after any CFN deploy; no manual script needed  
**Cons:** Adds ~2 hours of implementation; the dashboard Definition in CFN will be ~5000 lines; CFN dashboard updates can be slower than script-based ones

---

## 5. Recommended Fix

**Do both, in order:**

### Step 1 — Immediate fix (now, 1 minute)

```bash
python3 scripts/restore_dashboard_theme.py
```

This restores the CE theme on the live dashboard without touching any content. All 8 sheets remain intact.

### Step 2 — Bug fix (same session, 5 minutes)

Fix `add_tu_filters.py` so it cannot strip the theme again:

```python
# Line ~149 in scripts/add_tu_filters.py — CURRENT (broken):
resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=coo['Name'],
    Definition=defn,
    VersionDescription='Add POD and Person filters to Time & Utilization sheet'
)

# FIXED — add ThemeArn:
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'
resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=coo['Name'],
    Definition=defn,
    ThemeArn=THEME_ARN,
    VersionDescription='Add POD and Person filters to Time & Utilization sheet'
)
```

### Step 3 — Sync script update (same session, 10 minutes)

Add a warning and post-deploy instruction to `sync_coo_dashboard_iac.py`:

In the `main()` function, change the "Next steps" output:

```python
# Current:
print("  1. Review the file: git diff cloudformation/coo-dashboards.yaml")
print("  2. Commit: ...")
print("  3. To redeploy: ...")

# Updated:
print("  1. Review the file: git diff cloudformation/coo-dashboards.yaml")
print("  2. Commit: git add cloudformation/coo-dashboards.yaml && git commit -m 'sync: ...'")
print("  3. To redeploy the analysis:")
print("     aws cloudformation deploy --template-file cloudformation/coo-dashboards.yaml \\")
print("       --stack-name coo-dashboards-prod --parameter-overrides ...")
print("")
print("  ⚠️  IMPORTANT: The CFN deploy updates the ANALYSIS only, not the dashboard.")
print("  After deploying, run the following to republish the dashboard with CE theme:")
print("     python3 scripts/publish_coo_dashboard.py")
print("")
print("  This is required because the Dashboard is not managed by CloudFormation.")
print("  Skipping this step leaves the published dashboard on the old analysis version.")
```

### Step 4 — Durable IaC fix (next sprint, 2 hours)

In the next sprint, add `CooOperationalDashboard` to `coo-dashboards.yaml` via an updated `sync_coo_dashboard_iac.py`. This makes the theme enforcement automatic on every deploy and eliminates the need for `restore_dashboard_theme.py` as a recovery tool.

---

## 6. Prevention

### What must change to prevent recurrence

**Rule for all future `update_dashboard` calls:**

Every call to `update_dashboard` on the COO dashboard **must** include:
```python
ThemeArn='arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'
```

There is no "preserve existing theme" mode in the QuickSight API. Omitting `ThemeArn` is always a destructive action.

**Correct pattern** (used by most existing scripts):
```python
THEME_ARN = 'arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme'

resp = qs.update_dashboard(
    AwsAccountId=ACCOUNT,
    DashboardId=DASHBOARD_ID,
    Name=name,
    Definition=defn,
    ThemeArn=THEME_ARN,    # ← ALWAYS required
    VersionDescription='...'
)
```

**Or the defensive pattern** (reads from current version, works even if ThemeArn changes):
```python
d = qs.describe_dashboard(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID)['Dashboard']
theme_arn = d['Version'].get('ThemeArn') or THEME_ARN  # fallback to hardcoded if null
kwargs = dict(AwsAccountId=ACCOUNT, DashboardId=DASHBOARD_ID, Name=name, Definition=defn)
kwargs['ThemeArn'] = theme_arn
resp = qs.update_dashboard(**kwargs)
```

### Scripts to audit before next sprint

The following scripts were **not** in the last sprint commit but call `update_dashboard`. Verify they have `ThemeArn` before running:

- All scripts in `scripts/` that call `update_dashboard` — confirmed ✅ they all have `ThemeArn` **except** `add_tu_filters.py` (fixed in Step 2 above)

### Post-publish verification (add to sprint checklist)

After any `update_dashboard` + `update_dashboard_published_version` sequence, add this verification:

```bash
aws quicksight describe-dashboard \
  --aws-account-id 961341524729 \
  --dashboard-id coo-operational-dashboard-prod \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --query 'Dashboard.Version.{Version:VersionNumber,ThemeArn:ThemeArn,Status:Status}'
```

Pass criteria: `ThemeArn` must equal `arn:aws:quicksight:us-east-1:961341524729:theme/cloudelligent-brand-theme`.

---

## 7. Summary Checklist

- [ ] **IMMEDIATE:** Run `python3 scripts/restore_dashboard_theme.py` — restores CE theme on v36
- [ ] **IMMEDIATE:** Verify: `aws quicksight describe-dashboard ... --query 'Dashboard.Version.ThemeArn'` = CE ARN
- [ ] **TODAY:** Fix `scripts/add_tu_filters.py` — add `ThemeArn=THEME_ARN` to `update_dashboard` call
- [ ] **TODAY:** Update `sync_coo_dashboard_iac.py` next-steps output to include `publish_coo_dashboard.py` reminder
- [ ] **NEXT SPRINT:** Add `CooOperationalDashboard` resource to `coo-dashboards.yaml` via updated `sync_coo_dashboard_iac.py`
