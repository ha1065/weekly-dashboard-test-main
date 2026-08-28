# Dashboard Review History

> Ongoing conversation log between user and Kiro for evaluating and improving the COO/Weekly Reporting QuickSight dashboards.

---

## Session 1 — 2026-05-08

### Context Established
- **Project:** Cloudelligent Weekly Reporting & COO Dashboard
- **Stack:** Clockify → Lambda → RDS PostgreSQL → QuickSight SPICE
- **Bigger goal:** Agentic reporting and governance layer (KR5.1) — real-time CEO/COO decision visibility across delivery, finance, and capacity
- **OKR measurement instrument for:** KR2.1, KR2.4, KR5.1, KR5.4, KR3.4

### Dashboards Identified
Two main QuickSight dashboards with multiple sheets each:

#### 1. COO Operational Analysis (`coo-operational-analysis-prod`)
| Sheet | Sheet ID | Dataset(s) |
|-------|----------|------------|
| Weekly Summary | `sheet-weekly-summary` | `kpi_snapshots` |
| Project Hours | `sheet-project-hours` | `project_hours` (vw_project_hours_by_assignment) |
| Delivery Health | `sheet-delivery-health` | `ps_project_status` (vw_ps_project_status) |
| Resource Utilization / Time & Util | `sheet-resource-utilization` / `sheet-time-util` | `productive_util`, `time_compliance` |
| Project Detail | `sheet-project-detail` | `project_detail` (vw_project_detail) |

#### 2. Executive Summary Analysis (`clockify-executive-dashboard-prod`)
| Sheet | Dataset(s) |
|-------|------------|
| Executive Overview | `monthly_summary`, `practice_performance`, `resource_utilization` |
| Pod Performance | `pod_performance` |

#### 3. Additional standalone datasets/tabs referenced in code
- MC Service Delivery (`mc-ticket-activity`)
- Customer Status Assignments (`customer-status-assignments`)
- Project Directory (`project-directory`)
- Missing Time / Time Compliance (`time-compliance-current-week`, `missing-time-history`)
- Escalations (`escalations-detail`)
- PS Stage Trend (`ps-stage-trend`)
- Non-Billable Analysis (`non-billable-analysis`)
- Free Agent Availability (`free-agent-availability`)
- AI PS/MC Analysis (`ai-ps-analysis-by-user`, `ai-ps-analysis-by-project`, etc.)
- Forecast Analysis (`ai-forecast-analysis`, `pm-forecast-accuracy`)
- PS Profitability (`ps-profitability-2026`)

### Review Plan
Going through each dashboard tab one by one:
1. User explains why the tab was created
2. Kiro reviews against the codebase + OKRs
3. Kiro makes recommendations

### Confirmed Design Standards
- **Theme:** MIDNIGHT base with CE brand colors — confirmed live and approved
- **CE Palette:** `#0089DD` blue, `#FF9B00` orange, `#33A94F` green, `#D74018` red, `#27164F` purple, `#F4F3F7` background
- **Theme source of truth:** `scripts/patch_qs_visual_styling.py` (patches live via API) — NOT the CloudFormation template
- **CloudFormation theme file** (`cloudelligent-quicksight-theme.yaml`) is correct but uses CLASSIC base; live theme uses MIDNIGHT base per script

### Three-Tier Reporting Vision (confirmed 2026-05-08)

| Dashboard | Audience | Purpose |
|-----------|----------|---------|
| Executive Summary | CEO/COO | 1–2 page pulse — delivery health at a glance |
| COO Operational | Leadership team | Weekly meeting walkthrough — state of service delivery |
| Weekly Reporting (Streamlit) | COO governance | Granular detail — individual tracking, time compliance, PM/project Jira analysis |

### CUDOS Design Principles (to apply to all dashboards)
- KPI strip always at top (4–6 tiles, full width)
- One question per visual, stated in title
- Consistent color semantics: PS=blue, MC=orange, Green/Amber/Red for health
- Executive: no tables, no filters; Operational: light filters; Weekly: full filter bar

### Known Issues / Open Items
- `sheet-ps-delivery`, `sheet-escalations`, `sheet-time-util` exist only in live analysis — NOT in CloudFormation IaC (risk: lost on redeploy)
- Weekly Reporting Streamlit Dashboard page queries raw ORM instead of views — redundant with QuickSight
- Clarifying questions outstanding (see below)

### Outstanding Clarifying Questions
1. Executive Summary — who else sees it besides COO? Printable/exportable needed?
2. COO Operational — do you walk through sheets sequentially in meetings, or jump around?
3. COO Operational — which current sheets are working well enough to use today?
4. Weekly Reporting — are individual tracking items (time compliance, on-time, PM analysis) built or need to be built?
5. Weekly Reporting — keep in Streamlit or move to a separate QuickSight dashboard?

---

## Dashboard Reviews

### 1. Weekly Reporting (Streamlit)
**Status:** Reviewed 2026-05-08

**Origin:** Initial vibe-coded attempt at weekly reporting. Built iteratively with a lot of back and forth.

**Pages:** Dashboard, Resource Directory, Resource Forecast, Forecasting, Data Management, Project Mapping, Clockify Data Update, Settings

**Issues found:**
- Dashboard page queries raw ORM (`ClockifyTimeEntry`) instead of pre-built views — duplicates logic, can show dirty data
- POD name cleaning done in Python instead of using cleaned views
- Practice Alignment filter hardcodes options instead of pulling from DB
- MC resource count calculated twice (approximation then correction)
- Custom Range week selector renders empty col2

**Recommendation:** Retire Dashboard and Resource Directory pages — they are inferior to QuickSight. Keep Streamlit as the **operational control panel** only: Forecasting, Data Management, Project Mapping, Clockify Data Update.

---

### 2. COO Operational Analysis
**Status:** In review — 2026-05-08

**Origin:** Built with Kiro orchestrator Tue/Wed this week. Agentic approach but still too much back-and-forth vibe coding.

**Sheets in IaC (coo-dashboards.yaml):** Weekly Summary, Project Hours, Delivery Health, Resource Utilization, Project Detail

**Sheets in live analysis only (patched via scripts — NOT in IaC):** sheet-ps-delivery, sheet-escalations, sheet-time-util

**Issues found:**
- Delivery Health sheet is overloaded (KPIs + health bar + billable trend + project table + phase matrix + escalations = 4 concerns on one sheet)
- Billable util KPIs duplicated on Weekly Summary AND Resource Utilization
- 3 sheets are IaC orphans — lost on redeploy
- No clear audience separation between COO-level and ops-level content

**Pending:** Awaiting answers to clarifying questions before recommendations finalized.

---

### 3. Executive Summary
**Status:** Not yet reviewed

