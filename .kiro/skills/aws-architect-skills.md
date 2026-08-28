# AWS Architect Skills

## Architecture Design

### Well-Architected Framework
- Apply all 6 pillars: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, Sustainability
- Identify trade-offs between pillars and document decisions with rationale
- Use Well-Architected Tool for formal reviews

### Solution Design Patterns
- Serverless-first: Lambda + API Gateway + managed services before EC2
- Event-driven: SQS/SNS/EventBridge for async decoupling
- Multi-tenant isolation: per-tenant resources vs shared resources with RLS
- CQRS: separate read/write paths for high-throughput domains
- Strangler fig: incremental migration from monolith to microservices

### Diagramming
- Produce architecture diagrams using the aws-diagram MCP server
- Include: data flows, service boundaries, IAM trust relationships, VPC topology
- Label all arrows with protocol and direction

---

## Security Domain

### IAM
- Least-privilege: start with deny-all, add only required actions
- Use roles (not users) for service-to-service auth
- Condition keys: `aws:SourceVpc`, `aws:PrincipalTag`, `aws:RequestedRegion`
- SCPs for org-level guardrails

### Network Security
- VPC: private subnets for compute/data, public only for load balancers
- Security groups: stateful, port-specific, no 0.0.0.0/0 inbound
- VPC endpoints for S3, DynamoDB, Secrets Manager (avoid NAT costs + exposure)
- WAF on CloudFront/ALB for public-facing APIs

### Data Protection
- Encryption at rest: KMS CMK for RDS, S3, EBS, ElastiCache, OpenSearch
- Encryption in transit: TLS 1.2+ enforced, no HTTP
- Secrets Manager for credentials (never env vars or SSM plain text)
- PII classification: identify, tag, restrict access

### Threat Detection
- GuardDuty enabled in all regions
- Security Hub with AWS Foundational Security Best Practices standard
- CloudTrail in all regions, log integrity validation enabled
- VPC Flow Logs for network forensics

### Compliance
- HIPAA: PHI encryption, audit logging, BAA with AWS
- SOC2: CC6-CC9 controls mapped to AWS services
- PCI-DSS: cardholder data isolation, network segmentation
- CCPA/GDPR: data residency, right-to-erasure flows, consent tracking

---

## Infrastructure Analysis

### Resource Inspection (read-only)
- Use `aws` CLI with `describe-*`, `list-*`, `get-*` commands only
- Never mutate infrastructure during analysis
- Document findings in architecture docs, not in AWS console

### IaC Review
- CloudFormation/SAM: validate templates before deployment
- Check for hardcoded values that should be parameters
- Verify deletion policies on stateful resources (RDS, S3, DynamoDB)
- Confirm rollback triggers and stack policies

### Cost Analysis
- Use AWS Pricing MCP server for accurate estimates
- Include: compute, storage, data transfer, API calls, support
- Identify cost drivers and optimization opportunities
- Document assumptions (requests/day, data size, retention period)

---

## Reliability & Performance

- Multi-AZ for all stateful resources (RDS, ElastiCache, OpenSearch)
- Auto-scaling: Lambda concurrency limits, RDS Aurora Serverless min/max ACUs
- Circuit breakers for downstream service calls
- Dead-letter queues on all SQS consumers and async Lambda invocations
- Read replicas for read-heavy workloads
- CloudFront for static assets and API caching

---

## Observability

- Structured logging: JSON with `requestId`, `userId`, `duration`, `statusCode`
- Metrics: custom CloudWatch metrics for business KPIs
- Tracing: X-Ray on Lambda + API Gateway for distributed tracing
- Dashboards: one per domain with SLI/SLO panels
- Alarms: p99 latency, error rate, DLQ depth, Lambda throttles

---

## Spec-Based Development

Architecture docs must be detailed enough for code generation:

- Complete TypeScript interfaces (no `any`, no partial types)
- Explicit API contracts: method, path, request schema, response schema, error codes
- Precise edge case handling: what happens on missing fields, expired tokens, concurrent writes
- SQL schemas with all constraints, indexes, RLS policies
- Acceptance criteria must be machine-testable: exact status codes, exact field names, exact validation rules

---

## Edge Case & Cascade Analysis

For every state-changing operation, verify:

1. What happens if the operation is retried (idempotency)?
2. What happens if a downstream service is unavailable?
3. What happens if the user's session expires mid-operation?
4. What happens if two users perform the same operation concurrently?
5. What happens if the database write succeeds but the response fails to send?
6. What happens if the input is at the boundary of validation rules?
7. What happens if a required foreign key no longer exists?
8. What happens if the operation partially succeeds (e.g., DB write OK, SQS publish fails)?
9. What is the blast radius if this service goes down?

---

## Meeting Notes → SRS Verification

When verifying SRS against meeting notes:

1. Extract every requirement mentioned in meeting notes (explicit and implied)
2. Map each to an SRS functional requirement
3. Flag any requirement in meeting notes not covered in SRS
4. Flag any SRS requirement with no source in meeting notes
5. Produce a traceability matrix: Meeting Note → SRS FR → Acceptance Criteria

---

## Security Delta Analysis

When a vCISO or pen test report arrives:

1. Read the full report
2. Map each finding to the current architecture
3. Classify: already mitigated / partially mitigated / not mitigated
4. For not-mitigated findings: propose architecture change
5. Produce findings table: Finding | Severity | Current State | Proposed Fix | Story Points

---

## Implementation Planning

### Backlog Health Checks
- Every story has: title, description, acceptance criteria, story points, sprint assignment, spec reference
- No story enters the backlog without a referenced architecture doc
- Dependencies are explicit (blocked-by relationships)
- No sprint is overloaded (check velocity × team size)

### Environment Planning
- Dev, staging, prod environments defined
- Feature flags for gradual rollout
- Database migration strategy per environment
- Secrets rotation plan

---

## Stakeholder Questionnaire Management

When producing a stakeholder questionnaire:

- Group questions by domain (auth, data, integrations, compliance, operations)
- Mark each question as: Required (blocks architecture) vs Optional (informs design)
- Include "why we're asking" context for each question
- Track answers and update architecture docs when answers arrive
- Flag stories as BLOCKED until required questions are answered

---

## Cost-Conscious Architecture

- Always include a cost estimate in architecture docs
- Identify the top 3 cost drivers
- Propose cost optimization alternatives with trade-offs
- Set CloudWatch billing alarms at 80% and 100% of budget
- Use Savings Plans / Reserved Instances for predictable workloads

---

## Architecture Change Discipline

Before changing an existing architecture doc:

1. Identify all stories that reference this doc
2. Check if any are In Progress or Done
3. If yes: produce an impact analysis before changing
4. If no: update the doc and bump the version
5. Notify the orchestrator of the change so dependent stories can be re-validated

---

## AI Agent Architecture

### Design Patterns
- Tool use: prefer narrow, composable tools over broad multi-purpose tools
- Context window management: summarize long conversations, use knowledge bases
- Prompt injection defense: validate all user-supplied content before including in prompts
- Rate limiting: implement per-user and per-tenant limits on AI endpoints

### Public-Facing AI Security
- Never expose raw model errors to end users
- Sanitize all model outputs before rendering in UI
- Log all AI interactions for audit and abuse detection
- Implement content filtering for user inputs

---

## TCO Validation

When comparing build vs buy:

1. Calculate 3-year TCO for each option
2. Include: licensing, infrastructure, engineering time, maintenance, support
3. Use AWS Pricing MCP server for infrastructure costs
4. Document assumptions and sensitivity analysis
5. Present as a decision matrix with recommendation
