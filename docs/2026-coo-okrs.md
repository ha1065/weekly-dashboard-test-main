# 2026 COO OKRs — Key Results

> Source: 2026 coo okrs.xlsx (pasted 2026-05-01)

| KR | Owner | Pillar | Description | Baseline | Q1 | Q2 | Q3 | Q4 | Measurement |
|----|-------|--------|-------------|----------|----|----|----|----|-------------|
| KR2.1 | COO | Delivery | Increase on-time/ahead-of-schedule delivery rate from 30% to 90% by Q4, enabled by Kiro-driven project scaffolding and agentic delivery workflows | 30% | 45% | 60% | 75% | 90% | PMO delivery dashboard |
| KR2.2 | COO | Delivery | Reduce average engagement delivery duration from 15.2 weeks to 5 weeks by Q4, driven by Kiro-automated project scaffolding and reusable solution blueprints | 15.2 weeks | 12 weeks | 10 weeks | 7 weeks | 5 weeks | PMO cycle-time report |
| KR2.3 | COO | Delivery | 90% of new engagements launched with a Kiro steering file and embedded solution blueprint across Migration, AI/ML, Connect, and MCS practices by Q3 — sustained through Q4 | <10% | 40% | 70% | 90% | 90%+ | Kiro adoption dashboard / playbook tracker |
| KR2.4 | COO | Delivery | Deploy DeliverPro agentic delivery governance layer — Kiro-driven status reporting, risk flags, and escalation triggers — across 100% of active engagements by Q3; maintain projects-in-Red below 10% of active portfolio through Q4 | High / ad hoc | DeliverPro governance framework defined | 50% of projects on DeliverPro; Red <20% | 100% live; Red <15% | <10% projects in Red; DeliverPro fully automated | PMO Red/Amber/Green dashboard / DeliverPro |
| KR3.4 | COO + CFO | Delivery; Finance | Introduce expansion-linked incentives for MS and FinOps delivery teams; achieve 30%+ of active delivery touchpoints logging expansion signals by Q3 and 50%+ by Q4 | 0% incentivized / 0 opportunities logged | Incentive model designed and approved by CFO | Incentives live; opportunity logging active | 30%+ of delivery touchpoints logging expansion signals | 50%+ logging; first expansion deals attributed to delivery team | HubSpot opportunity log / delivery expansion tracker |
| KR5.1 | CEO + COO | People & Ops | Deploy agentic reporting and governance layer across delivery, finance, capacity, and pipeline — achieving 95%+ data hygiene and real-time CEO/COO decision visibility by Q3; sustained and expanded to all functions by Q4 | Clockify 67% / no real-time visibility | Data definitions + owners locked; agentic reporting scope defined | MVP live across delivery + finance; 80% data hygiene | 95%+ hygiene; real-time visibility live for CEO/COO | Full agentic governance layer across all functions; 95%+ sustained | Agentic ops dashboard / CRM QA / Clockify report |
| KR5.2 | CPO + COO | People & Ops | Achieve 95% AWS AI Practitioner certification across all roles by Q3; 100% of delivery team AIDLC / Agentic Software Development certified by Q4 | 5.5% AI Practitioner / 0% AIDLC | Certification roadmap published; cohort 1 enrolled | 60% AI Practitioner certified; AIDLC curriculum defined | 95% AI Practitioner certified; 60% AIDLC certified | 95%+ AI Practitioner sustained; 100% delivery AIDLC certified | Certification tracker / LMS |
| KR5.3 | CPO + COO | People & Ops | Restructure teams — reduce max direct reports from 20+ to 8 by Q4, publish decision rights matrix by Q2, move 80% of routine operating decisions below CEO/COO by Q4 | 20+ max reports / decisions centralized | Org redesign plan approved; decision rights matrix drafted | Matrix published + trained; max reports at 12 | Max reports at 10; 60% of routine decisions below CEO/COO | Max reports at 8; 80% decisions decentralized | Org design report / decision-rights audit |
| KR5.4 | CPO + COO | People & Ops | Identify and elevate top 20% of offshore talent into strategic roles — contributing to presales support, practice leadership, or strategic initiative delivery by Q3 | 0% offshore talent in strategic roles | Top 20% identified; strategic role definitions drafted | Elevation plans active; first offshore talent in presales/practice lead role | Top 20% fully elevated into strategic roles | Continuous motion established; tracked quarterly | Talent elevation tracker / CPO review |
| KR6.1 | CEO + COO | Product; Delivery | Launch OpsAI Managed Services product with managed fee + usage pricing — live with 2+ paying pilot customers by Q3 and 5+ by Q4 | 0 MS product customers | OpsAI MS product scoped; pricing model + ICP defined | Product built; 2+ paying pilot customers live | Pilot validated; 5+ paying customers | 5+ paying MS product customers; managed fee + usage model proven | Product revenue tracker / customer contracts |
| KR6.2 | COO + CRO | Product; Delivery | Package FinOps AI and WAFR AI as commercial products — pricing defined, delivery framework built, first pilot customer for each by Q4 | 0 packaged products | FinOps AI + WAFR AI product briefs drafted | Pricing + ICP defined; delivery frameworks complete | FinOps AI pilot customer live | WAFR AI pilot customer live; both products packaged | Product packaging doc / pilot customer contracts |
| KR6.4 | CFO + COO | Finance; Product | Achieve 40%+ gross margin on all Services as Software engagements from first pilot onward — no margin-negative product deals in 2026 | Undefined / PS margin ~20% | Cost model defined per product; margin floor approved by CFO | First MS pilot priced at 40%+ margin | All active product deals at 40%+ margin | 40%+ gross margin sustained across all SaS engagements | Finance margin tracker / deal desk approval |

---

## Data Governance Rules

- **Clockify is the system of record for all time reporting** (actual hours, billable hours, utilization, compliance) — except forecasted hours
- **Clockify is the system of record for project classification and naming** — project names, client names, categories, POD assignments all come from Clockify
- **Jira is the system of record for project status, schedule, and health** — planned/actual dates, Red/Amber/Green health, stage, PM/SA assignments
- **Forecasted hours** come from the PS Resource Forecast (Excel template import into `ps_resource_forecasts` table)
- **Jira provides SOW hours only** (budgeted/contracted hours — `budget_hours`). No actual hours come from Jira.
- **Consequence for Sheet 5:** `actual_hours` column must be sourced from Clockify, not Jira. `budget_hours` (SOW) from Jira remains valid as the budget ceiling.
- **Consequence for project naming:** Any discrepancy between Jira project names and Clockify project names must resolve to the Clockify name

## Data Source Constraints

- **DeliverPro is not yet available** — KR2.4 metrics cannot be sourced from DeliverPro; must use existing data sources
- **All time reporting comes from Clockify** — utilization, billable hours, compliance, presales hours
- **All project reporting comes from Jira** — project status, schedule (planned/actual dates), health (Red/Amber/Green), on-time delivery rate, engagement duration

## Dashboard-Relevant KRs (tracked in COO Dashboard)

| KR | What the dashboard must show |
|----|------------------------------|
| KR5.1 | Clockify adoption %, data hygiene score, real-time utilization, time compliance |
| KR2.1 | On-time delivery rate (% projects delivered on/ahead of schedule) |
| KR2.4 | Projects in Red/Amber/Green; % in Red vs 10% target |
| KR5.4 | Offshore talent in strategic roles (people metric) |
| KR3.4 | Expansion signals logged from delivery touchpoints |

## Branding Colors (CE Official — from CE Branding Colors.rtf)

| Role | Hex |
|------|-----|
| Primary blue | `#0089DD` |
| Orange | `#FF9B00` |
| Red | `#D74018` |
| Green | `#33A94F` |
| Dark purple | `#27164F` |
| Background | `#F4F3F7` |
| Font | Inter (Regular + Bold) in `#27164F` |

> **Note:** Current CloudFormation theme uses `#1B2766` (navy) and `#2D6DF6` (blue) — these differ from the official brand colors above. Theme needs updating.
