# MC Customer Health Table — Requirements

**Document:** `docs/mc-customer-health-requirements.md`
**Status:** Draft
**Date:** 2026-05-14
**Author:** Product Analyst

---

## Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v1.0 | 2026-05-14 | Product Analyst | Initial document |

---

## 1. Problem Statement

The `tbl-mc` visual on the MC Service Delivery sheet currently shows one row per `jira_project_key`. Customers with multiple linked Jira project boards appear multiple times, making it impossible to assess a customer's overall health at a glance and inflating the row count in the table.

**Root cause:** The `tbl-mc` visual groups by `(customer_name, health_overall, jira_project_key)`. The `jira_project_key` GroupBy field is the fan-out key. The underlying data source (`vw_mc_ticket_activity`, backed by `mc_ticket_activity_snapshot`) already has a `UNIQUE (week_start, customer_name)` constraint — one row per customer per week — so the fan-out is introduced entirely by the visual configuration, not the view.

---

## 2. Correct Data Grain

**One row per customer per reporting week.**

Rationale:
- The CST board is the master customer list. Each customer has exactly one CST ticket. The COO and delivery leads need to assess customer health at the customer level, not the project level.
- `mc_ticket_activity_snapshot` already enforces `UNIQUE (week_start, customer_name)`. The snapshot aggregates ticket counts across all boards for a customer into a single row.
- `jira_project_key` in the snapshot stores the primary CST project key, not the linked board keys. It is a customer identifier, not a project-level dimension.
- Showing one row per `jira_project_key` implies a customer has multiple health statuses, which is misleading. Health is assessed at the customer level by the PM.

---

## 3. Required Columns

The following columns should be shown in `tbl-mc`, one row per customer:

| Column | Source | Display Label | Notes |
|--------|--------|---------------|-------|
| `customer_name` | `mc_ticket_activity_snapshot.customer_name` | Customer | Primary identifier |
| `health_overall` | `mc_ticket_activity_snapshot.health_overall` | Health | Green / Amber / Red — drives row color |
| `open_issues` | `mc_ticket_activity_snapshot.open_issues` | Open Tickets | |
| `in_progress_issues` | `mc_ticket_activity_snapshot.in_progress_issues` | In Progress | |
| `updated_this_week` | `mc_ticket_activity_snapshot.updated_this_week` | Updated This Week | Activity signal |
| `billable_hours` | `vw_mc_ticket_activity.billable_hours` | Billable Hrs | From Clockify MC projects |
| `open_escalations` | `vw_mc_ticket_activity.open_escalations` | Escalations | 0 = no badge needed |

Columns to **remove** from the GroupBy:
- `jira_project_key` — remove entirely from the visual. It is not a customer-level dimension and is the direct cause of the fan-out.

Columns that are **optional / lower priority**:
- `clockify_hours` (total hours including non-billable) — currently shown but `billable_hours` is more meaningful for the COO view.
- `done_issues` — useful for completeness but adds width; can be hidden by default.

---

## 4. Aggregation Rules for Multi-Project Customers

The `mc_ticket_activity_snapshot` table already aggregates at the customer level (one row per `(week_start, customer_name)`). The snapshot logic in `_capture_mc_ticket_snapshot()` in `import_jira_data.py` handles this:

- **Source 1 (customers with board imports):** `mc_customer_tickets` is grouped by `customer_name` across all `jira_project_key` values for that customer. Ticket counts (`total_issues`, `open_issues`, etc.) are summed across all boards.
- **Source 2 (CST-only customers):** `ps_project_status` rows for the customer are grouped by `client_name`.

`health_overall` is derived using `MODE() WITHIN GROUP (ORDER BY health_overall)` — the most frequent health value across CST rows for the customer. For customers with a single CST ticket (the standard case), this is simply that ticket's health.

**No additional aggregation is needed in the view or dataset SQL.** The snapshot already produces the correct customer-grain. The fix is purely in the visual configuration.

---

## 5. Recommended Implementation

### Fix: Remove `jira_project_key` from the `tbl-mc` GroupBy

The `mc_ticket_activity_snapshot` table has `UNIQUE (week_start, customer_name)`. When QuickSight groups by `(customer_name, health_overall, jira_project_key)`, it produces one row per unique combination. Since `jira_project_key` varies per customer (or is NULL for some), this breaks the one-row-per-customer intent.

**Change required:** Visual configuration only — remove `tbl-mc-g2` (`jira_project_key`) from the GroupBy field wells in the `tbl-mc` TableVisual.

**No view change needed.** `vw_mc_ticket_activity` already joins `mc_ticket_activity_snapshot` at customer grain. The view does not fan out on `jira_project_key`.

**No dataset SQL change needed.** The `mc-projects-at-risk` dataset reads from `vw_mc_ticket_activity` which is already at customer grain.

### Implementation options (in order of preference)

**Option A — Edit the CloudFormation IaC (recommended)**

In `cloudformation/coo-dashboards.yaml`, in the `tbl-mc` TableVisual, remove the `jira_project_key` GroupBy field:

```yaml
# Remove this block from GroupBy:
- CategoricalDimensionField:
    FieldId: tbl-mc-g2
    Column:
      DataSetIdentifier: mc_at_risk
      ColumnName: jira_project_key
```

Then redeploy or republish via `scripts/republish_from_analysis.py`. This keeps IaC and live analysis in sync.

**Option B — Patch the live analysis directly**

Use the QuickSight API (via `scripts/sync_coo_dashboard_iac.py` or a targeted patch script) to remove `tbl-mc-g2` from the live analysis definition, then republish. Use this if a fast fix is needed before the next IaC deployment.

**Option C — Dataset SQL filter (not recommended)**

Adding a `DISTINCT ON (customer_name)` or `GROUP BY customer_name` in the dataset SQL would mask the root cause without fixing it, and would break if `jira_project_key` is ever needed for another visual on the same dataset.

---

## 6. Does `vw_mc_ticket_activity` Need to Be Modified?

No. The view is correct. It joins `mc_ticket_activity_snapshot` (customer grain) with Clockify hours and escalations, both also at customer grain. The view output is one row per `(week_start, customer_name)`.

The only structural concern: `vw_mc_ticket_activity` exposes `jira_project_key` as a passthrough column from the snapshot. This column is the CST project key (e.g. `CST`), not the linked board key. It is not a multi-valued field. Its presence in the view is harmless; the problem is that the visual uses it as a GroupBy dimension.

---

## 7. Open Questions

| # | Question | Impact if unresolved |
|---|----------|----------------------|
| OQ-1 | Should `jira_project_key` be retained as a hidden/tooltip column in `tbl-mc` for drill-through purposes, or removed entirely from the visual? | Low — cosmetic only |
| OQ-2 | For customers with multiple CST tickets (edge case), `health_overall` uses `MODE()` which picks the most frequent value. Should worst-case health (Red > Amber > Green) be used instead? | Medium — affects how at-risk customers are surfaced |
| OQ-3 | Should the table filter to the current reporting week automatically, or show all weeks with a week filter control? Currently `vw_mc_ticket_activity` returns all weeks. | Medium — affects whether the table shows one row or N rows per customer |
| OQ-4 | Is `done_issues` useful to show in the COO table, or should it be hidden to reduce width? | Low |

---

## 8. Acceptance Criteria

- Given the MC Customer Health table is rendered for the current reporting week
- When a customer has tickets on more than one linked Jira project board
- Then the customer appears exactly once in the table

- Given `health_overall = 'Red'` for a customer
- When the table renders
- Then that customer's row has a red background (`#FADBD8`)

- Given `health_overall = 'Green'` for a customer
- When the table renders
- Then that customer's row has a green background (`#D5F5E3`)

- Given the table is sorted by default
- When rendered
- Then Red customers appear before Amber, Amber before Green (worst-case first)
