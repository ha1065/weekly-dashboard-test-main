# AWS Security Reviewer Skills

## Security Foundations

### Account & Organization Security
- AWS Organizations with SCPs for guardrails
- Separate accounts per environment (dev, staging, prod)
- Root account MFA + no programmatic access
- CloudTrail enabled in all regions with log integrity validation

### Shared Responsibility Model
- AWS responsibility: physical, hypervisor, managed service internals
- Customer responsibility: OS patching, IAM, data encryption, network config, application security
- Identify which layer each finding belongs to

---

## IAM

### Authentication
- MFA required for all human users (hardware token for privileged accounts)
- JWT validation: verify signature, expiry, issuer, audience
- Cognito: user pool settings (password policy, MFA, account recovery)
- Service-to-service: IAM roles only (no long-lived access keys)

### Authorization
- Least-privilege: start with deny-all, add only required actions
- RBAC: roles map to IAM policies, not individual users
- Row-Level Security (RLS): enforce at database layer, not application layer
- Attribute-based access control (ABAC) for dynamic permissions

### Session Management
- Access token TTL: 15–60 minutes
- Refresh token TTL: 7–30 days with rotation
- Token revocation: maintain a denylist or use short TTLs
- Concurrent session limits per user

---

## Detection & Monitoring

### Logging
- CloudTrail: all management events + S3 data events for sensitive buckets
- VPC Flow Logs: all VPCs
- Application logs: structured JSON, no PII in log statements
- Log retention: 90 days hot, 1 year cold (S3 Glacier)

### Threat Detection
- GuardDuty: enabled in all regions, findings routed to Security Hub
- Security Hub: AWS Foundational Security Best Practices standard enabled
- Config Rules: detect drift from approved configurations
- Macie: PII detection in S3 buckets

### Incident Response
- Runbooks for top 5 incident types (credential compromise, data exfiltration, DDoS, ransomware, insider threat)
- Automated containment: Lambda → isolate EC2/Lambda, revoke credentials
- Communication plan: who to notify, when, what to say

---

## Infrastructure Protection

### Network Security
- VPC: private subnets for compute/data, public only for load balancers
- Security groups: stateful, port-specific, no 0.0.0.0/0 inbound
- NACLs: stateless, use for broad subnet-level rules
- VPC endpoints: S3, DynamoDB, Secrets Manager (avoid NAT + public exposure)

### Edge Protection
- WAF: OWASP Top 10 rules on CloudFront/ALB
- CORS: explicit allowed origins, no wildcard for credentialed requests
- DDoS: AWS Shield Standard (automatic), Shield Advanced for critical workloads
- Rate limiting: API Gateway usage plans + WAF rate rules

### Compute Security
- Lambda: no VPC unless needed (adds cold start), least-privilege execution role
- EC2: SSM Session Manager instead of SSH, no public IPs
- Container: ECR image scanning, no root user in containers
- Patch management: SSM Patch Manager for EC2

---

## Data Protection

### Encryption at Rest
- S3: SSE-KMS with CMK, bucket policies deny non-encrypted uploads
- RDS/Aurora: storage encryption with KMS CMK
- EBS: encrypted volumes
- OpenSearch: encryption at rest enabled
- ElastiCache: encryption at rest enabled (Redis AUTH + TLS)

### Encryption in Transit
- TLS 1.2+ enforced everywhere (deny TLS 1.0/1.1)
- HTTPS-only: S3 bucket policies, API Gateway, CloudFront
- Internal service communication: TLS even within VPC

### Data Classification & Handling
- PII: identify, tag, restrict access, log all access
- PHI (HIPAA): additional controls — audit logging, BAA with AWS, encryption
- Cardholder data (PCI-DSS): isolate in separate VPC/account, minimize scope
- Data retention: define per data class, automate deletion with S3 lifecycle / RDS automated backups

### S3 Bucket Security
- Block all public access (account-level setting)
- Bucket policies: deny `s3:*` unless from specific VPC endpoint or IAM role
- Versioning + MFA delete for critical buckets
- Access logging enabled

---

## Application Security

### Input Validation
- Validate all inputs at API boundary (schema validation, type checking)
- Reject unexpected fields (strict mode in Zod/JSON Schema)
- Sanitize before storing or rendering (XSS prevention)
- Parameterized queries only (no string interpolation in SQL)

### API Security
- Authentication on every endpoint (no unauthenticated routes except public health checks)
- Authorization checked at handler level (not just middleware)
- Rate limiting per user and per IP
- API keys for machine-to-machine (rotate every 90 days)

### CI/CD Security
- Secrets in Secrets Manager / Parameter Store (never in code or env vars)
- SAST: run on every PR (Semgrep, Bandit, ESLint security rules)
- Dependency scanning: npm audit / Snyk on every build
- Container scanning: ECR image scan on push
- Least-privilege IAM for CI/CD pipeline role

### AI/LLM Security
- Prompt injection: validate and sanitize all user inputs before including in prompts
- Output sanitization: never render raw model output in UI without validation
- Rate limiting: per-user limits on AI endpoints
- Audit logging: log all AI interactions for abuse detection

---

## Compliance Frameworks

### HIPAA
- PHI encryption at rest and in transit
- Audit logging for all PHI access
- BAA signed with AWS
- Minimum necessary access principle
- Workforce training documentation
- Incident response plan with 60-day breach notification

### SOC2
- CC6: logical access controls (IAM, MFA, least privilege)
- CC7: system operations (monitoring, incident response)
- CC8: change management (IaC, PR reviews, deployment approvals)
- CC9: risk mitigation (vendor assessments, business continuity)

### PCI-DSS
- Cardholder data environment (CDE) isolation in separate VPC/account
- No storage of CVV/CVC
- Tokenization for PANs
- Quarterly vulnerability scans
- Annual penetration testing

### CCPA/CPRA
- Data inventory: know what PII you collect and why
- Right to deletion: implement data erasure flows
- Right to access: implement data export flows
- Consent management: track and honor opt-outs
- Data minimization: collect only what's needed

---

## Third-Party Security Assessment Review

When a vCISO or pen test report arrives:

1. Read the full report
2. For each finding: map to current architecture
3. Classify: already mitigated / partially mitigated / not mitigated
4. For not-mitigated: propose remediation with effort estimate
5. Produce findings table: Finding | Severity | Current State | Proposed Fix | Story Points | Sprint
6. Flag Critical/High findings as blockers before next deployment

---

## Public-Facing Attack Surface Analysis

For each public-facing endpoint:

1. Authentication required? (yes/no + mechanism)
2. Authorization enforced? (RBAC/ABAC + what roles can access)
3. Input validation? (schema, type, length, format)
4. Rate limiting? (per user, per IP, per tenant)
5. Output sanitization? (XSS, injection prevention)
6. Logging? (access logs, error logs, audit trail)
7. WAF rules applied?
8. DDoS protection?
9. Sensitive data in response? (PII, PHI, credentials)
10. Blast radius if compromised?

Document findings per endpoint in a threat model table.
