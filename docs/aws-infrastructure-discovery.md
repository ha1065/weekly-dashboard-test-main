# AWS Infrastructure Discovery

**Account:** 961341524729
**Region:** us-east-1
**Discovery Date:** 2026-05-12
**Profile:** AWSAdministratorAccess-961341524729

---

## Executive Summary

The weekly-reporting project runs a production-grade internal reporting platform built on a serverless + containerised hybrid architecture. Core components are:

- **ECS Fargate** serving a Streamlit dashboard behind an ALB (1 task, always-on)
- **Lambda** (`production-clockify-import`) handling all data ingestion — Clockify time-tracking, Jira, and QuickSight SPICE refresh — triggered by three EventBridge schedules
- **RDS PostgreSQL 15** (`db.t3.micro`, single-AZ) as the primary data store
- **Amazon QuickSight** with 1 primary data source (PostgreSQL via VPC connection), 47 SPICE datasets, and 7 dashboards (including 2 COO-level dashboards deployed 2026-04-27)
- **Custom VPC** (`10.0.0.0/16`) with public/private subnet pairs across 2 AZs, properly isolating compute and database tiers

The infrastructure is largely IaC-managed across 4 project-specific CloudFormation stacks. Key security findings are surfaced in the Architecture Observations section.

---

## CloudFormation Stacks

### Project Stacks

| Stack Name | Status | Last Updated | Description |
|---|---|---|---|
| `weekly-reporting-production` | UPDATE_COMPLETE | 2026-01-20 | Core infrastructure: VPC, RDS, Lambda, Secrets Manager, SNS |
| `production-weekly-reporting-dashboard` | UPDATE_COMPLETE | 2026-01-29 | ECS Fargate Streamlit dashboard + ALB |
| `cloudelligent-qs-theme` | CREATE_COMPLETE | 2026-04-27 | Cloudelligent brand theme for QuickSight |
| `coo-dashboards-prod` | UPDATE_COMPLETE | 2026-05-04 | COO Operational + Executive Summary QuickSight dashboards |

### Other Active Stacks (non-project)

| Stack Name | Status | Description |
|---|---|---|
| `qsuite-archera-integration` | UPDATE_COMPLETE | Archera.ai + CoreStack MCP proxy with Cognito OAuth |
| `Clockify-Quicksight` | CREATE_COMPLETE | Legacy Clockify QuickSight dashboard (pre-production stack) |
| `CdkStack` | UPDATE_COMPLETE | CDK-deployed aws-funding-rag-api Lambda |
| `CDKToolkit` | CREATE_COMPLETE | CDK bootstrap toolkit |
| `AWS-DevOpsAgent-Lambda-Test` | CREATE_COMPLETE | DevOps agent test Lambda |
| `lambda-service-role-stack` | CREATE_COMPLETE | Lambda service role with inline policies |
| `spektra-saasify-prm-stack` | CREATE_COMPLETE | SaaSify PRM IAM role |
| `amplify-d2xczg2o4pwzq5-main-branch-cb51da7d2f` | UPDATE_COMPLETE | Amplify main branch (AppSync + Cognito + DynamoDB) |
| `amplify-frontendreact-Shaista-sandbox-960010ee7d` | CREATE_COMPLETE | Amplify sandbox environment |
| Various StackSet-* stacks | CREATE_COMPLETE | Control Tower, Archera, New Relic, SentinelOne, CoreStack, QuickSetup |
| Various DataZone-Env-* stacks | CREATE_COMPLETE | DataZone environment stacks |

> **Note:** Drift detection has not been run on any stack (`NOT_CHECKED`). This means live infrastructure may have diverged from IaC definitions.

---

## Lambda Functions

### Project Lambdas

| Function Name | Runtime | Memory | Timeout | VPC | Description |
|---|---|---|---|---|---|
| `production-clockify-import` | python3.11 | 512 MB | 900 s | Yes (`vpc-092443d27523a1fce`) | Primary data ingestion: Clockify → RDS + QuickSight SPICE refresh |
| `production-archera-proxy` | python3.11 | 256 MB | 30 s | No | Proxy to Archera.ai API; reads secret from Secrets Manager |

### Other Account Lambdas

| Function Name | Runtime | Memory | Timeout | VPC | Description |
|---|---|---|---|---|---|
| `jira-data-pull-lambda` | python3.13 | 128 MB | 30 s | No | Jira data pull → S3 (`jira-data-pull-cloudelligent`) |
| `clockify-data-processor` | python3.9 | 1024 MB | 900 s | No | Legacy Clockify processor (pre-production stack) |
| `aws-funding-rag-api` | Image (x86_64) | 2048 MB | 60 s | No | Bedrock RAG API (CDK stack) |
| `funding-program-advisor-lambda-1` | python3.10 | 1024 MB | 600 s | No | OpenSearch-backed funding advisor |
| `purity-health-lambda` | python3.10 | 512 MB | 300 s | No | Purity Health POC |
| `AWS-DevOpsAgent-test-lambda` | python3.12 | 128 MB | 30 s | No | DevOps agent error test |
| `test-lambda-g3-bol` | python3.14 | 128 MB | 3 s | No | G3 BOL test function |
| Various `amplify-*` Lambdas | nodejs20.x / nodejs22.x | 128–1536 MB | 10–900 s | No | Amplify CDK custom resources (table manager, branch linker, S3 auto-delete) |
| `delete-name-tags-us-east-1-*` (×2) | python3.9 | 128 MB | 900 s | No | QuickSetup patch policy tag cleanup |

**`production-clockify-import` environment variable keys:** `DB_PORT`, `SECRET_NAME`, `DB_USER`, `ENVIRONMENT`, `DB_ENDPOINT_PARAMETER`, `NOTIFICATION_TOPIC_ARN`, `DB_NAME`, `BEDROCK_MODEL_ID`

**`production-archera-proxy` environment variable keys:** `ARCHERA_BASE_URL`, `CACHE_BUST`, `SECRET_NAME`, `ARCHERA_ORG_ID`


---

## RDS Instances

| Identifier | Engine | Version | Instance Class | Status | Multi-AZ | Storage | Encrypted | VPC |
|---|---|---|---|---|---|---|---|---|
| `production-weekly-reporting` | PostgreSQL | 15.14 | db.t3.micro | available | **No** | 20 GB gp3 | Yes (KMS) | `vpc-092443d27523a1fce` |

**Additional details:**
- Endpoint: `production-weekly-reporting.cn0g6iw42ap2.us-east-1.rds.amazonaws.com:5432`
- Database name: `weekly_reporting`
- AZ: `us-east-1b` (single-AZ — no standby)
- Backup retention: 7 days; backup window: 03:00–04:00 UTC
- Deletion protection: **Enabled**
- CloudWatch logs: `postgresql` log export enabled
- Performance Insights: Disabled
- Parameter group: `weekly-reporting-postgres15`
- CA certificate valid until: 2027-01-20
- IAM database authentication: Disabled
- Publicly accessible: **No**

---

## ECS

### Clusters

| Cluster Name | ARN |
|---|---|
| `production-weekly-reporting` | `arn:aws:ecs:us-east-1:961341524729:cluster/production-weekly-reporting` |

### Services

| Service Name | Launch Type | Task Definition | Desired | Running | Pending | Subnets | Public IP |
|---|---|---|---|---|---|---|---|
| `production-dashboard-service` | FARGATE | `production-weekly-reporting-dashboard:4` | 1 | 1 | 0 | private-1 (us-east-1a), private-2 (us-east-1b) | Disabled |

**Service details:**
- Load balancer: ALB target group `production-dashboard-tg` → container port 8501
- Deployment strategy: Rolling (max 200%, min healthy 100%)
- Deployment circuit breaker: **Disabled** (no automatic rollback)
- Health check grace period: 120 seconds
- Execute command (ECS Exec): **Enabled**
- AZ rebalancing: Enabled
- Last deployment: 2026-05-08 (task definition revision 4)
- Security group: `sg-06b02f622fefd1e4a` (production-dashboard-ecs-sg)

---

## EventBridge Rules

| Rule Name | State | Schedule / Pattern | Target | Input Mode |
|---|---|---|---|---|
| `production-weekly-import-9am-ct` | ENABLED | `cron(0 15 ? * MON *)` — Mon 9 AM CT | `production-clockify-import` | Static JSON: `mode=weekly, weeks_back=2, refresh_quicksight=true` |
| `production-weekly-import-noon-ct` | ENABLED | `cron(0 18 ? * MON *)` — Mon 12 PM CT | `production-clockify-import` | Static JSON: `mode=incremental, snapshot_kpis=true, notify=true, refresh_quicksight=true` + 14 dataset IDs |
| `production-jira-daily-refresh` | ENABLED | `cron(0 10 * * ? *)` — Daily 10 AM UTC / 5 AM CT | `production-clockify-import` | Static JSON: `mode=jira_import, refresh_quicksight=true` |
| `jira-data-pull` | ENABLED | `cron(0 9 * * ? *)` — Daily 9 AM UTC | `jira-data-pull-lambda` | None (default event) |
| `Send_AWS_RISK_Events_To_Management_Account` | ENABLED | Event pattern: `aws.health` RISK events | Management account event bus (`898668804275`) | — |

**Observation:** `production-clockify-import` is the target for three separate EventBridge rules. The Monday noon run (`production-weekly-import-noon-ct`) explicitly refreshes 14 named QuickSight SPICE datasets. The daily Jira run also triggers a QuickSight refresh.


---

## QuickSight

### Dashboards

| Dashboard Name | Dashboard ID | Last Updated | Published Version |
|---|---|---|---|
| Weekly Reporting Dashboard | `b894f691-f392-41c4-bc52-ee732a3cf27e` | 2026-05-06 | v82 |
| COO Operational Dashboard (prod) | `coo-operational-dashboard-prod` | 2026-05-12 | v13 |
| Executive Summary Dashboard (prod) | `coo-executive-dashboard-prod` | 2026-05-04 | v4 |
| Monthly_Utilization_Dashboard | `00c89179-2691-4ba3-86be-8bea673812d0` | 2025-06-16 | v1 |
| Sample_Utilization_Dashboard | `b254f992-8727-4ce1-8a9d-2fd688f9dc97` | 2025-07-07 | v10 |
| ServiceDeskDashboard | `25ef9d70-0949-4ae9-ad95-f6a48c81ffee` | 2025-07-01 | v2 |
| Sales Overview | `548e060f-58bb-4022-96e8-4632c1f32dd2` | 2025-10-08 | v3 |

### Data Sources

| Name | Type | Status | Host | VPC Connection |
|---|---|---|---|---|
| `Weekly-Reporting-PostgreSQL` | POSTGRESQL | CREATION_SUCCESSFUL | `production-weekly-reporting.cn0g6iw42ap2.us-east-1.rds.amazonaws.com:5432` | `weekly-reporting-vpc` |
| `12 May 2026-funding-activities.csv` | FILE | — | — | None |

> **Security Note:** The PostgreSQL data source has `DisableSsl: true`. TLS is not enforced for QuickSight → RDS connections.

### Datasets (47 total — all SPICE import mode)

Key production datasets (refreshed by EventBridge schedules):

| Dataset ID | Name | Last Updated |
|---|---|---|
| `kpi-weekly-snapshots-prod` | KPI Weekly Snapshots (prod) | 2026-05-12 |
| `clockify-missing-time-submissions-prod` | Missing Time Submissions (prod) | 2026-05-12 |
| `clockify-missing-time-submissions` | Clockify Missing Time Submissions | 2026-05-12 |
| `mc-v2-audit-by-phase` | MC V2 Audit by Phase | 2026-05-12 |
| `data-freshness` | data_freshness | 2026-05-12 |
| `ps-project-status-view` | ps_project_status | 2026-05-12 |
| `vw_forecast_vs_actual` | vw_forecast_vs_actual | 2026-05-12 |
| `vw_contractor_time_summary` | vw_contractor_time_summary | 2026-05-12 |
| `productive-utilization` | Productive Utilization | 2026-05-11 |
| `escalations-detail` | Escalations Detail | 2026-05-11 |
| `ps-stage-trend` | PS Stage Trend | 2026-05-11 |
| `ai-forecast-analysis` | AI Forecast Analysis | 2026-05-11 |
| `ai-forecast-summary` | AI Forecast Summary | 2026-05-11 |
| `project-hours-summary-prod` | Project Hours Summary (prod) | 2026-05-11 |
| `project-hours-current-week-prod` | Project Hours Current Week (prod) | 2026-05-11 |
| `time-compliance-current-week` | Weekly Compliance Report | 2026-05-11 |

Additional datasets: `vw_forecast_summary`, `vw_contractor_weekly_trend`, `ps_resource_forecasts`, `vw_forecast_over_40_hours`, `ai-mc-analysis-by-project`, `ai-mc-analysis-by-user`, `ai-ps-analysis-by-project`, `ai-ps-analysis-by-user`, `category-hours-summary-prod`, `clockify-daily-activity-trend-prod`, `clockify-import-activity-prod`, `clockify-pod-performance-prod`, `clockify-skill-area-summary-prod`, `customer-status-assignments`, `escalations-by-customer`, `free-agent-availability`, `mc-projects-at-risk`, `mc-ticket-activity`, `mc-v2-audit-by-customer`, `mc-v2-audit-grid`, `missing-time-history`, `non-billable-analysis`, `pm-forecast-accuracy`, `practice-group-performance`, `project-detail-view`, `project-directory`, `project-hours-by-assignment`, `project-time-detail`, `ps-profitability-2026`, `ps-profitability-chart`, `ps-profitability-weekly-2026`, `ps-projects-at-risk`, `resource-capacity-plan`, `12 May 2026-funding-activities.csv`

---

## Secrets Manager

| Secret Name | ARN | Description | Last Accessed |
|---|---|---|---|
| `production/weekly-reporting/secrets` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:production/weekly-reporting/secrets-wz2cJg` | Secrets for Weekly Reporting application | 2026-05-11 |
| `production/archera/api-key` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:production/archera/api-key-ttszZe` | Archera.ai API key for qsuite integration | 2026-04-16 |
| `production/corestack/credentials` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:production/corestack/credentials-bCNeZL` | CoreStack credentials (access_key+secret_key or username+password) | 2026-04-19 |
| `QBusiness-Slack-slack` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:QBusiness-Slack-slack-C3eoTK` | Q Business Slack integration | 2026-04-10 |
| `sharepoint` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:sharepoint-aMNwFT` | SharePoint credentials | — |
| `redshift-secret` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:redshift-secret-QBYS1I` | Redshift credentials | 2025-10-14 |
| `redshiftdatashare-admin-redshift-creds` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:redshiftdatashare-admin-redshift-creds-6ZXsNP` | Redshift data share admin credentials | 2025-10-14 |
| `sqlworkbench!3c6faf54-...` | `arn:aws:secretsmanager:us-east-1:961341524729:secret:sqlworkbench!3c6faf54-9d11-4af4-ba36-e2e146afd66f-OXzVZb` | SQL Workbench connection secret | 2025-10-15 |

> Secret values were not retrieved. Names and ARNs only.

---

## S3 Buckets

### Project-Related Buckets

| Bucket Name | Created |
|---|---|
| `weekly-reporting-production-deployments-961341524729` | 2026-01-20 |
| `clockify-dashboard-961341524729-us-east-1` | 2025-08-18 |
| `jira-data-pull-cloudelligent` | 2026-02-18 |
| `internal-dashboard-bucket` | 2025-07-21 |
| `executivereporting` | 2025-06-03 |

### Other Account Buckets

| Bucket Name | Created |
|---|---|
| `cf-templates-961341524729-us-east-1` | 2026-04-29 |
| `cf-templates-19t1iwzukcedg-us-east-1` | 2025-08-18 |
| `cf-templates-lfksqzoxka320-us-west-2` | 2025-12-18 |
| `aws-funding-rag` | 2025-10-13 |
| `cdk-hnb659fds-assets-961341524729-us-east-1` | 2025-10-16 |
| `aws-athena-query-results-us-east-1-961341524729` | 2025-08-21 |
| `internal-projects-cloudelligent` | 2025-09-06 |
| `purity-health-poc-bucket` | 2025-08-21 |
| `clockify-quicksight-lambda` | 2025-08-19 |
| `dev-g3-bol-docs` | 2026-02-20 |
| `rag-training-test05` | 2026-01-07 |
| `cloudelligent-proj-x-poc` | 2025-08-17 |
| `spillbox-test` | 2025-01-21 |
| `strands-test-bucket-txt` | 2025-11-06 |
| `test-nehmer-pdf` | 2025-10-23 |
| `amazon-sagemaker-961341524729-us-east-1-5ada3e15422b` | 2024-12-11 |
| `sagemaker-studio-961341524729-ntusniefh4b` | 2024-12-15 |
| `sagemaker-studio-961341524729-piic0frx3fe` | 2025-01-01 |
| `sagemaker-us-east-1-961341524729` | 2024-12-15 |
| `firehose-backup-5eec49d0` | 2024-12-10 |
| `new-relic-firehose-backup-03-apr-6a3aba60` | 2024-12-10 |
| Various `amplify-*` buckets (×4) | 2025-10-16 |

---

## ECR Repositories

| Repository Name | Created | Image Tag Mutability | Scan on Push | Images |
|---|---|---|---|---|
| `production-weekly-reporting-dashboard` | 2026-01-28 | MUTABLE | **Yes** | 12 (1 tagged `latest`) |
| `weekly-reporting` | 2026-02-03 | MUTABLE | **No** | 9 (1 tagged `latest`) |
| `aws-funding-rag-lambda` | 2025-10-16 | MUTABLE | **No** | — |
| `cdk-hnb659fds-container-assets-961341524729-us-east-1` | 2025-10-16 | IMMUTABLE | **No** | — |

> `production-weekly-reporting-dashboard` has scan-on-push enabled (good). `weekly-reporting` does not — this repo should also have scanning enabled.


---

## VPC & Networking

### VPCs

| VPC ID | Name | CIDR | Default | Stack |
|---|---|---|---|---|
| `vpc-092443d27523a1fce` | `production-weekly-reporting-vpc` | `10.0.0.0/16` | No | `weekly-reporting-production` |
| `vpc-03a763497396ed066` | *(unnamed)* | `172.31.0.0/16` | **Yes** | — |

### Subnets (production VPC only)

| Subnet ID | Name | CIDR | AZ | Type | Auto-assign Public IP |
|---|---|---|---|---|---|
| `subnet-07e2e18fbcdfe7f6a` | `production-public-subnet-1` | `10.0.101.0/24` | us-east-1a | Public | Yes |
| `subnet-00489d34605908b7f` | `production-public-subnet-2` | `10.0.102.0/24` | us-east-1b | Public | Yes |
| `subnet-045290e60558e8b92` | `production-private-subnet-1` | `10.0.1.0/24` | us-east-1a | Private | No |
| `subnet-0b08e78de8da700e4` | `production-private-subnet-2` | `10.0.2.0/24` | us-east-1b | Private | No |

### Security Groups (production VPC)

| SG ID | Name | Purpose | Inbound | Outbound |
|---|---|---|---|---|
| `sg-0148e12bab6c4d046` | `production-dashboard-alb-sg` | ALB | TCP 80 from `0.0.0.0/0`, TCP 443 from `0.0.0.0/0` | All traffic |
| `sg-06b02f622fefd1e4a` | `production-dashboard-ecs-sg` | ECS tasks | TCP 8501 from ALB SG only | TCP 5432 to `0.0.0.0/0`, TCP 443 to `0.0.0.0/0` |
| `sg-072193341ebe1f56e` | `production-lambda-sg` | Lambda | None (no inbound) | TCP 5432 to DB SG, TCP 443 to `0.0.0.0/0` |
| `sg-0afdd548eee15c49d` | `production-database-sg` | RDS PostgreSQL | TCP 5432 from Lambda SG, QuickSight SG, ECS SG, self | All traffic |
| `sg-05d2ad8e102773fcf` | `production-quicksight-sg` | QuickSight VPC connection | None | TCP 5432 to DB SG, all traffic to `0.0.0.0/0` |
| `sg-0d71ad1d75e0bc310` | `quicksight-vpc-sg` | QuickSight (secondary) | None | All traffic |
| `sg-05f84963432924309` | `default` | Default VPC SG | Self only | All traffic |

**Network topology summary:**
```
Internet
    │
    ▼
ALB (public subnets: 10.0.101.0/24, 10.0.102.0/24)
    │  sg-0148e12bab6c4d046 — port 80/443 open to internet
    ▼
ECS Fargate task (private subnets: 10.0.1.0/24, 10.0.2.0/24)
    │  sg-06b02f622fefd1e4a — port 8501 from ALB only
    ▼
RDS PostgreSQL (private subnets, us-east-1b)
       sg-0afdd548eee15c49d — port 5432 from Lambda, ECS, QuickSight SGs only

Lambda (private subnets) ──────────────────────────────────────────────────────┘
    │  sg-072193341ebe1f56e — no inbound; outbound 5432 to RDS, 443 to internet
    ▼
QuickSight VPC connection ─────────────────────────────────────────────────────┘
    sg-05d2ad8e102773fcf
```

---

## Architecture Observations

### 🔴 Critical — Security

**1. Hardcoded credentials in Lambda environment variables**
`jira-data-pull-lambda` has a live Jira API token and email address stored directly in its Lambda environment variables (not in Secrets Manager). This is a critical security violation — environment variables are visible in the AWS console, CloudTrail, and any IAM principal with `lambda:GetFunctionConfiguration`. The token should be rotated immediately and moved to Secrets Manager.

**2. QuickSight SSL disabled for RDS connection**
The `Weekly-Reporting-PostgreSQL` QuickSight data source has `DisableSsl: true`. All data in transit between QuickSight and RDS PostgreSQL is unencrypted. SSL should be enforced.

**3. `clockify-data-processor` Lambda has Clockify API key in environment variables**
The legacy `clockify-data-processor` Lambda (from the `Clockify-Quicksight` stack) stores a Clockify API key directly in its environment variables. This key should be rotated and moved to Secrets Manager.

### 🟠 High — Security / Reliability

**4. RDS is single-AZ**
`production-weekly-reporting` runs on a single `db.t3.micro` in `us-east-1b` with no Multi-AZ standby. An AZ failure or instance failure causes a full outage with manual recovery. For a production reporting system, Multi-AZ should be evaluated.

**5. No drift detection on any CloudFormation stack**
All stacks show `DriftStatus: NOT_CHECKED`. Manual changes made outside CloudFormation (e.g., security group rule edits, parameter changes) will not be detected. Drift detection should be run and scheduled.

**6. ECS deployment circuit breaker disabled**
`production-dashboard-service` has `deploymentCircuitBreaker.enable: false`. A bad deployment will not automatically roll back — it will stall and require manual intervention.

**7. `weekly-reporting` ECR repository has no scan-on-push**
The `weekly-reporting` repo (9 images) does not scan images on push, unlike `production-weekly-reporting-dashboard`. Vulnerability scanning should be enabled on all repos.

### 🟡 Medium — Cost / Operations

**8. `production-clockify-import` Lambda has a 900-second timeout**
The Lambda runs with a 15-minute maximum timeout. If it hangs (e.g., Clockify API unresponsive), it will consume the full timeout before failing. A dead-letter queue (DLQ) and/or a shorter timeout with retry logic would improve resilience.

**9. No auto-scaling on ECS service**
The Streamlit dashboard runs with `desiredCount: 1` and no auto-scaling policy. A single task failure causes a brief outage until ECS replaces it. Application Auto Scaling with a minimum of 1 and target tracking would improve availability.

**10. X-Ray tracing disabled on all project Lambdas**
Both `production-clockify-import` and `production-archera-proxy` have `TracingConfig.Mode: PassThrough`. Enabling X-Ray would provide end-to-end visibility into Lambda → RDS and Lambda → external API call latency.

**11. Duplicate/legacy Clockify infrastructure**
The `Clockify-Quicksight` stack and `clockify-data-processor` Lambda appear to be a legacy predecessor to the production stack. If no longer in use, these should be decommissioned to reduce cost and attack surface.

**12. Monday noon EventBridge rule hardcodes 14 QuickSight dataset IDs**
The `production-weekly-import-noon-ct` rule passes a static list of 14 dataset IDs in its input JSON. If datasets are renamed or new ones added, this list must be manually updated. Consider driving the refresh list from a configuration parameter or SSM Parameter Store.

### 🔵 Info — IaC / Drift

**13. Two separate CloudFormation stacks for core infrastructure**
The project is split across `weekly-reporting-production` (VPC, RDS, Lambda, secrets) and `production-weekly-reporting-dashboard` (ECS, ALB). This is a reasonable separation but means cross-stack references must be kept in sync manually (the ECS stack takes the VPC/subnet/SG IDs as parameters).

**14. `quicksight-vpc-sg` (`sg-0d71ad1d75e0bc310`) is not CloudFormation-managed**
This security group exists in the production VPC but has no CloudFormation tags, suggesting it was created manually. It has no inbound rules and all-traffic egress — it may be unused or a duplicate of `production-quicksight-sg`.

---

## Open Questions

1. **Is the `Clockify-Quicksight` stack and `clockify-data-processor` Lambda still in use?** If not, they should be decommissioned. The `clockify-dashboard-961341524729-us-east-1` S3 bucket and `clockify-quicksight-lambda` bucket may also be orphaned.

2. **What is the ALB DNS name / custom domain for the Streamlit dashboard?** The discovery did not enumerate ALBs directly — the ALB endpoint is needed to confirm whether HTTPS is enforced and whether a custom domain/ACM certificate is in place.

3. **Is there a NAT Gateway in the production VPC?** ECS tasks and Lambda run in private subnets but need internet access (Clockify API, Bedrock, SNS). The security group egress rules allow outbound 443, but a NAT Gateway or VPC endpoints must exist for this to work. This was not confirmed in the discovery.

4. **Are VPC endpoints configured for Secrets Manager, SSM, and SNS?** The Lambda reads secrets from Secrets Manager and publishes to SNS. Without VPC endpoints, this traffic traverses the internet via NAT Gateway, incurring data transfer costs and bypassing VPC isolation.

5. **What is the RTO/RPO target for the reporting platform?** Single-AZ RDS with 7-day backup retention implies an RPO of up to 24 hours (point-in-time recovery) and an RTO of 20–30 minutes for a restore. If the business requires tighter targets, Multi-AZ and/or Aurora Serverless should be evaluated.

6. **Who has access to the QuickSight dashboards?** QuickSight user/group permissions were not enumerated. It is unclear whether the COO dashboards are restricted to specific users or broadly accessible within the account.

7. **Is the `jira-data-pull-lambda` part of the weekly-reporting project or a separate system?** It writes to `jira-data-pull-cloudelligent` S3 and is triggered by its own EventBridge rule (`jira-data-pull`), separate from `production-jira-daily-refresh`. The relationship between these two Jira pipelines should be clarified.
