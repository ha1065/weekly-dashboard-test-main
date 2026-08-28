# Weekly Reporting — Architecture & Cost Improvement Recommendations

> **Generated:** 2026-08-01
> **Scope:** Cost optimization and architecture design improvements for the Weekly Reporting platform

---

## Table of Contents

1. [Cost Optimization](#cost-optimization)
2. [Architecture Design Improvements](#architecture-design-improvements)
3. [Priority Summary](#priority-summary)

---

## Cost Optimization

### 1. NAT Gateway — Biggest Fixed Cost (~$32-45/month)

The NAT Gateway exists solely because the Lambda is VPC-attached (to reach RDS in private subnets) and also needs internet access (Clockify API, Jira API, Bedrock). At ~$0.045/hr + $0.045/GB processed, this is the single largest infrastructure cost after RDS.

**Options:**

- **Option A — VPC Endpoints (reduce, don't eliminate):** Add VPC endpoints for Secrets Manager, SSM, Bedrock, and QuickSight. NAT is still needed for Clockify/Jira (external APIs), but data processing charges drop significantly.
- **Option B — Remove Lambda from VPC entirely:** Use **RDS Proxy** (adds ~$15/month for db.t3.micro) and make the database accessible via RDS Proxy's IAM auth from non-VPC Lambda. This eliminates the NAT Gateway entirely — net savings ~$17-30/month, plus eliminates VPC cold start penalty (~2-5s).

**Recommended:** Option A short-term, Option B if willing to restructure.

---

### 2. Lambda Deployment Package — 21MB of Bloat

The `lambda-deployment-package.zip` is **21MB** and contains unnecessary dependencies:

| Unnecessary Package | Why It's Included | Lambda Needs It? |
|---------------------|-------------------|------------------|
| `streamlit`, `altair`, `plotly`, `pydeck` | UI frameworks | ❌ No |
| `pandas`, `numpy`, `pyarrow` | Heavy data libs | ❌ No (SQL handles aggregation) |
| `black`, `pytest` | Dev/test tools | ❌ No |
| `fastapi`, `uvicorn` | Web server | ❌ No |
| `PIL/Pillow`, `captcha` | Image processing | ❌ No |
| `gitpython`, `gitdb` | Git operations | ❌ No |

The `requirements-lambda.txt` is correct (6 packages): `SQLAlchemy`, `pg8000`, `requests`, `backoff`, `python-dotenv`, `boto3`.

**Impact:** Larger cold starts, longer deploy times, risk of hitting Lambda's 250MB unzipped limit.

**Fix:** Build Lambda package from `requirements-lambda.txt` only. Add `openpyxl` (for forecast parsing) and note that `boto3` is already in the Lambda runtime. Estimated reduced size: **~5-8MB** (from 21MB).

---

### 3. RDS Instance Right-Sizing

Current: `db.t3.micro` (2 vCPU, 1GB RAM, ~$13-15/month).

The workload pattern is: active ~2-3 hours/week during imports + QuickSight SPICE refreshes, mostly idle otherwise.

**Options:**

- **Aurora Serverless v2** ($0.12/ACU-hr, min 0.5 ACU): With the current usage pattern, estimated cost ~$10-15/month. Breakeven with t3.micro, but gains auto-scaling for Bedrock analysis bursts.
- **Stick with db.t3.micro:** Already the cheapest provisioned option and appropriate for the workload.

**Recommendation:** Stay with db.t3.micro unless Bedrock analysis queries start causing CPU pressure.

---

### 4. QuickSight SPICE Refresh Strategy

Currently refreshing 14+ datasets per import run regardless of whether underlying data changed.

**Problem:** SPICE refreshes consume compute, can fail silently, and waste QuickSight capacity.

**Fix:** Only refresh datasets whose source views have new data. Add a `data_freshness` check before triggering each dataset refresh. Compare `import_logs.completed_at` against last SPICE ingestion time.

---

### 5. Bedrock Token Cost Reduction

Currently using `claude-3-5-sonnet` (`us.anthropic.claude-3-5-sonnet-20241022-v2:0`) for ALL AI analysis tasks.

**Observation:** For structured data comparison (Jira estimates vs Clockify actuals), the task doesn't require Sonnet-level reasoning.

**Recommendation:**

| Task | Current Model | Recommended Model | Cost Reduction |
|------|---------------|-------------------|----------------|
| Project health (data comparison) | Sonnet | Haiku | ~90% per invocation |
| MC V2 audit (structured evaluation) | Sonnet | Haiku | ~90% per invocation |
| Forecast analysis (simple math) | Sonnet | Haiku | ~90% per invocation |
| Narrative generation (summaries) | Sonnet | Keep Sonnet | — |

**Estimated savings:** 50-70% reduction in Bedrock costs by routing simple tasks to Haiku.

---

## Architecture Design Improvements

### 6. CRITICAL: Split Monolithic Lambda (126K lines)

The single Lambda (`production-clockify-import`) serves **20+ distinct modes** — from data imports to migrations to diagnostics to AI analysis.

**Problems:**

- **Blast radius:** A bug in `diagnose_dates` mode can take down the weekly import
- **Timeout risk:** 900s max timeout with cascading operations (import → Jira → KPI → AI → SPICE refresh)
- **Dependency conflicts:** All code shares the same package
- **Untestable:** 126K lines in one handler makes unit testing nearly impossible
- **Cold start:** Monolithic package means every invocation loads all code

**Recommended split:**

| Lambda | Responsibility | Timeout | Memory |
|--------|---------------|---------|--------|
| `import-orchestrator` | Triggers sub-functions, manages workflow | 300s | 256MB |
| `clockify-import` | Clockify API → RDS | 600s | 256MB |
| `jira-import` | Jira API → RDS | 300s | 256MB |
| `ai-analysis` | Bedrock calls → RDS | 900s | 512MB |
| `quicksight-refresh` | SPICE dataset refresh | 120s | 128MB |
| `compliance-email` | SES email sends | 60s | 128MB |
| `admin-tools` | Migrations, diagnostics, view apply | 300s | 256MB |

---

### 7. Adopt Step Functions for Weekly Pipeline

Replace the cascading Lambda mode (`incremental` does import → Jira → KPI → AI → SPICE) with AWS Step Functions:

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  Clockify   │────▶│  Jira       │────▶│  KPI         │
│  Import     │     │  Import     │     │  Snapshot    │
└─────────────┘     └─────────────┘     └──────────────┘
                                               │
                    ┌─────────────┐     ┌──────┴───────┐
                    │  SPICE      │◀────│  AI          │
                    │  Refresh    │     │  Analysis    │
                    └─────────────┘     └──────────────┘
                           │
                    ┌──────┴───────┐
                    │  Compliance  │
                    │  Email       │
                    └──────────────┘
```

**Benefits:**

- Individual step retries with configurable backoff
- Parallel execution where possible (e.g., AI analysis + SPICE refresh in parallel)
- Visible execution history in AWS Console
- Timeout per step (not cumulative across all operations)
- Built-in error handling and catch/retry at each step
- Cost: ~$0.025/1000 state transitions (negligible for weekly runs)

---

### 8. Missing Resilience Patterns

**No Dead-Letter Queue (DLQ):**
If an EventBridge-triggered Lambda fails, the event is lost. Add a DLQ (SQS) to catch failures.

```yaml
ImportLambdaFunction:
  Properties:
    DeadLetterConfig:
      TargetArn: !GetAtt ImportDLQ.Arn
```

**No idempotency:**
If Lambda times out at 895 seconds and EventBridge retries, duplicate imports can occur. Add a locking mechanism:
- DynamoDB-based lock (simple, cheap)
- PostgreSQL advisory lock (`pg_try_advisory_lock`)
- Check `import_logs` for a recent successful run before proceeding

**No circuit breaker for external APIs:**
The `backoff` library is in requirements but unclear if it wraps all Clockify/Jira API calls consistently. Add:
- Max retry count (3-5)
- Exponential backoff with jitter
- Circuit breaker that fails fast after N consecutive failures

---

### 9. Split Streamlit App (122K Lines → Multi-Page)

`src/app.py` is 122K lines — a maintenance nightmare.

**Recommended structure:**

```
src/
  pages/
    01_dashboard.py
    02_resource_directory.py
    03_forecasting.py
    04_data_management.py
    05_project_mapping.py
    06_clockify_update.py
    07_settings.py
  app.py           # Entry point, routing, auth only (~200 lines)
  shared.py        # Shared utilities (already exists)
```

**Benefits:**
- Each page can be developed/tested independently
- Faster page loads (only imports needed modules)
- Easier code review and onboarding
- Standard Streamlit multi-page pattern

---

### 10. Missing Observability

**Current state:** No CloudWatch Alarms defined in the CloudFormation template.

**Recommended alarms:**

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| Lambda Errors | `Errors` | > 0 for 1 period | SNS notification |
| Lambda Duration | `Duration` | > 800,000ms (approaching 900s timeout) | SNS notification |
| Lambda Throttles | `Throttles` | > 0 | SNS notification |
| RDS CPU | `CPUUtilization` | > 80% for 5 min | SNS notification |
| RDS Storage | `FreeStorageSpace` | < 2GB | SNS notification |
| SPICE Refresh Failures | Custom metric | > 0 | SNS notification |
| Import Staleness | Custom metric (hours since last success) | > 48 hours | SNS notification |

**Also needed:**
- CloudWatch Dashboard for weekly import health
- X-Ray tracing on Lambda for performance profiling
- Structured logging (JSON format) for easier CloudWatch Insights queries

---

### 11. Security Improvements

| Issue | Current State | Recommendation |
|-------|--------------|----------------|
| IAM too broad | `quicksight:CreateIngestion` on `dataset/*` | Scope to specific dataset ARNs or tag-based conditions |
| SES permissions | `Resource: '*'` | Scope to verified identity ARNs |
| No WAF | Streamlit ECS has no WAF | Add AWS WAF with rate limiting on ALB |
| Static DB password | Password passed as CloudFormation parameter | Use Secrets Manager auto-rotation |
| No encryption in transit enforcement | RDS allows non-SSL connections | Add `rds.force_ssl=1` parameter group setting |
| Bastion key in repo | `weekly-reporting-bastion-key.pem` in project root | Remove from repo, store in Secrets Manager or SSM |

---

## Priority Summary

| # | Improvement | Effort | Savings/Impact |
|---|-------------|--------|----------------|
| 1 | Fix Lambda package (use requirements-lambda.txt) | Low (1 hour) | Faster deploys, smaller cold starts |
| 2 | Add DLQ to EventBridge targets | Low (1 hour) | Prevents lost events |
| 3 | Add CloudWatch alarms | Low (2 hours) | Early failure detection |
| 4 | Add VPC endpoints (SM, SSM, Bedrock) | Medium (half day) | ~$5-10/month savings + lower latency |
| 5 | Use Haiku for simple AI tasks | Low (2 hours) | ~50-70% Bedrock cost reduction |
| 6 | Split monolithic Lambda | High (1-2 weeks) | Reliability, maintainability, independent scaling |
| 7 | Adopt Step Functions for pipeline | High (1 week) | Visibility, retry logic, timeout isolation |
| 8 | Split app.py into multi-page Streamlit | Medium (3-5 days) | Maintainability |
| 9 | Evaluate removing VPC from Lambda (RDS Proxy) | Medium (1 day) | Eliminate NAT GW (~$32-45/month) |
| 10 | Add observability (alarms, dashboard) | Medium (1 day) | Operational visibility |
| 11 | Security hardening | Medium (1-2 days) | Compliance, reduced attack surface |

---

### Quick Wins (do this week)

1. Rebuild Lambda package from `requirements-lambda.txt` → saves 15MB, faster cold starts
2. Add DLQ to all EventBridge rules → prevents silent failures
3. Add 5 basic CloudWatch alarms → immediate visibility
4. Switch Bedrock model to Haiku for data comparison tasks → 50-70% token cost reduction

### Medium-Term (next sprint)

5. Add VPC endpoints for Secrets Manager, SSM, Bedrock
6. Split `app.py` into multi-page Streamlit structure
7. Add observability dashboard
8. Security hardening (IAM scoping, WAF, force SSL)

### Strategic (next quarter)

9. Split monolithic Lambda into purpose-specific functions
10. Adopt Step Functions for weekly pipeline orchestration
11. Evaluate VPC removal with RDS Proxy

---

*End of document.*
