# JIRA Data Flow Architecture

## High-Level Architecture

```
Jira Cloud (Service Desk)
        │
        │  REST API v3 (Basic Auth: email + API token)
        │  JQL-based search with cursor pagination
        ▼
┌─────────────────────────────────┐
│  Lambda: ImportLambdaFunction   │  ← Triggered daily at 10 AM UTC
│  (src/lambda_function.py)       │     via EventBridge schedule
│                                 │
│  Calls: run_jira_import()       │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  src/integrations/jira_client.py │  ← API Client (auth, pagination, field extraction)
└─────────────┬───────────────────┘
              │
              ▼
┌──────────────────────────────────────────┐
│  src/integrations/import_jira_data.py    │  ← ETL logic
│                                          │
│  Steps:                                  │
│  1. import_jira_projects()               │  → jira_projects table
│  2. import_ps_project_status()           │  → ps_project_status table (upsert)
│  3. import_mc_customer_boards()          │  → mc_customer_tickets table
│  4. auto_populate_mappings()             │  → ps_project_mapping table
│  5. _capture_stage_snapshot()            │  → ps_stage_weekly_snapshot
│  6. _capture_mc_ticket_snapshot()        │  → mc_ticket_activity_snapshot
└─────────────┬────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  PostgreSQL (RDS)               │
│  Tables + Reporting Views       │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  AWS QuickSight (SPICE)         │  ← Datasets auto-refreshed post-import
│  Datasets:                      │
│  - ps-project-status-view       │
│  - escalations-detail           │
│  - mc-ticket-activity           │
│  - mc-projects-at-risk          │
│  - ps-projects-at-risk          │
└─────────────────────────────────┘
```

---

## Trigger Mechanism

- **AWS EventBridge** fires a cron rule (`cron(0 10 ? * * *)`) daily at 10:00 AM UTC
- The event payload specifies `"mode":"jira_import"` and lists QuickSight datasets to refresh after import
- The Lambda (`ImportLambdaFunction`) receives the event and calls `run_jira_import()`
- EventBridge payload:
  ```json
  {
    "mode": "jira_import",
    "refresh_quicksight": true,
    "quicksight_dataset_ids": [
      "ps-project-status-view",
      "escalations-detail",
      "mc-ticket-activity",
      "mc-projects-at-risk",
      "ps-projects-at-risk"
    ]
  }
  ```

---

## API Client (`src/integrations/jira_client.py`)

- Authenticates via **Basic Auth** (base64-encoded `email:api_token`)
- Uses **Jira REST API v3** (`/rest/api/3/search/jql`) with cursor-based pagination (`nextPageToken`)
- Extracts **~40+ custom fields** from each issue:

| Field Category | Fields |
|----------------|--------|
| Project classification | `project_type` |
| Team members | PM, architect, engineer, AE, CSM |
| Health status | overall, budget, scope, schedule, escalation, impact, risks/blockers |
| Dates (planning) | planned start/end, kickoff, SOW signing, expected/revised completion |
| Dates (actual) | actual kickoff, actual completion, phase completion dates (5 phases) |
| Narrative | summary, what we did, what's next, mitigation plan, slippages |
| Links | SOW link, Jira board link |

- Implements **retry with exponential backoff** (3 attempts) on request failures
- Parses `client_name` and `project_name` from Jira issue summary using pattern matching:
  - "Client - Project" (dash separator)
  - "Client: Project" (colon separator)
  - Known project type suffixes (Migration, AppDev, etc.)

---

## ETL Logic (`src/integrations/import_jira_data.py`)

### Orchestration Function: `run_jira_import()`

Runs 4 sequential steps:

| Step | Function | Target Table | What It Does |
|------|----------|-------------|--------------|
| 1 | `import_jira_projects()` | `jira_projects` | Syncs project metadata (key, name, lead) |
| 2 | `import_ps_project_status()` | `ps_project_status` | Core import — maps issues to PS/MC status rows |
| 3 | `import_mc_customer_boards()` | `mc_customer_tickets` | Imports Managed Cloud customer board tickets |
| 4 | `auto_populate_mappings()` | `ps_project_mapping` | Creates Jira↔Clockify project mappings |

### Key Behaviors

- **Incremental by default**: Only fetches issues updated since last successful import (tracked in `import_logs` table)
- **Upsert on `jira_issue_id`**: Uses `INSERT ... ON CONFLICT DO UPDATE` — intentionally preserves `client_name` and `project_name` on update to protect manual normalizations
- **Category classification**: Issues categorized as `PS` or `MC` based on issue type matching against configurable `MC_ISSUE_TYPES` env var
- **Weekly snapshots**: After import, stage counts (`ps_stage_weekly_snapshot`) and MC ticket activity (`mc_ticket_activity_snapshot`) are captured for historical trending
- **PROJ board filtered out**: Issues from the PROJ board are skipped entirely (PS Delivery tab is CST-only)

### Post-Import Actions (Lambda Handler)

1. **Verification query**: Checks row counts in `ps_project_status`, `ps_project_mapping`, `jira_projects`
2. **QuickSight SPICE refresh**: Triggers `create_ingestion()` for all listed datasets
3. **Optional KPI snapshot**: If `snapshot_kpis=true` in event payload

---

## Database Schema

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `jira_projects` | Project metadata | `jira_project_id`, `project_key`, `project_name`, `lead_name` |
| `ps_project_status` | Main status table — one row per Jira issue | `jira_issue_id` (unique), all health/date/narrative fields |
| `ps_project_mapping` | Maps Jira project keys → Clockify projects/clients | `jira_project_key`, `clockify_project_id` |
| `mc_customer_tickets` | Managed Cloud customer board issues | `customer_name`, `jira_project_key`, `status_category` |
| `ps_stage_weekly_snapshot` | Weekly stage distribution counts | `week_start`, `stage`, `category`, `project_count` |
| `mc_ticket_activity_snapshot` | Weekly MC ticket counts per customer | `week_start`, `customer_name`, open/in-progress/done counts |
| `import_logs` | Audit trail of all imports | `import_category`, `status`, `records_imported`, timestamps |

### Reporting Views

Views like `vw_ps_project_status` are defined in `src/database/create_views.sql` and:
- Normalize health fields (e.g., escalation → Red/Green for QuickSight conditional formatting)
- Join with Clockify data for budget/hours analysis
- De-duplicate and filter (exclude PROJ board, filter to in-progress issues)
- Compute derived fields (schedule slippage, burn rate)

---

## Configuration

All JIRA settings from environment variables or Secrets Manager:

| Variable | Purpose |
|----------|---------|
| `JIRA_BASE_URL` | Jira Cloud instance URL |
| `JIRA_API_EMAIL` | Service account email |
| `JIRA_API_TOKEN` | API token (stored in Secrets Manager) |
| `JIRA_PROJECT_KEYS` | Comma-separated project keys to sync |
| `JIRA_PHASE_FIELD_ID` | Custom field ID for project phase |
| `MC_ISSUE_TYPES` | Issue types classified as Managed Cloud (default: "Managed Services") |

---

## Data Flow Sequence (Per Import Run)

1. EventBridge triggers Lambda at 10 AM UTC
2. Lambda retrieves secrets from Secrets Manager
3. Lambda calls `run_jira_import()`
4. `JiraClient` authenticates and paginated-fetches issues via JQL
5. Each issue is parsed: custom fields extracted, client/project parsed from summary
6. Upsert into `ps_project_status` (preserves manually-corrected names)
7. MC customer boards imported separately
8. Jira↔Clockify mappings auto-populated
9. Weekly snapshots captured (stage counts, ticket activity)
10. Post-import verification queries run
11. QuickSight SPICE datasets refreshed via `create_ingestion()` API
12. Import logged to `import_logs` table with counts and status
