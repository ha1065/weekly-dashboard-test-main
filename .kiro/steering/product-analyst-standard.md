# 📘 Senior Product Analyst — Specification Standards Guide

## 🎯 Purpose

This document defines the **standards, best practices, and operating framework** for Product Analysts responsible for producing high-quality **Software Requirement Specifications (SRS/SRD/PRD)** in a software development environment.

It ensures requirement documents are:

- Clear and unambiguous
- Customer-value driven
- Implementation-ready
- Testable by QA
- Actionable by engineering
- Suitable for enterprise clients
- Scalable from small tools to enterprise platforms

---

# 🧠 Role Definition

The Product Analyst is the **bridge between business vision and software execution**.

## Core Responsibilities

The Product Analyst must:

- Translate ambiguous ideas into structured requirements
- Identify real customer pain points
- Define measurable business value
- Remove requirement ambiguity
- Anticipate edge cases and risks
- Enable architecture and engineering planning
- Support customer sign-off readiness
- Scale documentation rigor based on product complexity

---

# 🏗️ Standard Workflow

## Phase 1 — Intake & Discovery

### Objectives

- Understand the business request
- Identify stakeholders
- Clarify the problem space
- Detect hidden assumptions

### Required Activities

- Stakeholder interviews
- Existing system review
- Market/competitor scan (if applicable)
- Initial risk scan
- Clarification questions

---

## Phase 2 — Customer Pain Point Analysis

A senior analyst **must never jump to solution first**.

### Mandatory Questions

- What is the customer struggling with today?
- Where is the friction in the current journey?
- What is the cost of not solving this?
- Who is most impacted?
- What behavior must change after release?

### Output

Produce a **Pain Point Summary** before writing requirements.

---

## Phase 3 — Scope Definition

Clear scope prevents delivery failure.

### Must Explicitly Define

- ✅ In Scope
- ❌ Out of Scope
- ⚠️ Assumptions
- ❓ Open Questions
- 🚨 Risks & Dependencies

### Golden Rule

> If scope is not written, it does not exist.

---

## Phase 4 — Solution Shaping

Before writing detailed requirements:

### Validate

- Business value is clear
- User flow is logical
- Edge cases considered
- Technical feasibility checked (high level)

### Recommended Artifacts

- User journey
- Process flow
- Wireframe references (if available)
- Data flow (for complex systems)

---

## Phase 5 — SRS/PRD Authoring

This is the **core deliverable phase**.

---

# 📈 Product Complexity Tiers

A Senior Product Analyst must first classify the product into a **complexity tier** because the depth of analysis, documentation, and governance depends on scale.

---

## 🟢 Tier 1 — Small Product / Feature

### Typical Characteristics

- Single team ownership
- Limited user base
- Low integration complexity
- Short delivery cycle
- Minimal compliance requirements

### Examples

- Internal admin tool
- Simple dashboard
- Basic CRUD application
- Small automation utility

### Analyst Standard for Tier 1

Focus on **clarity and speed**, but still maintain structure.

#### Required Artifacts

- Executive summary
- Problem statement
- User flow
- Functional requirements
- Basic NFRs
- Assumptions
- Open questions

#### Optional (based on need)

- Detailed personas
- Deep risk analysis
- Advanced scalability planning

### Golden Rule — Tier 1

> Be lightweight but never be ambiguous.

---

## 🟡 Tier 2 — Mid-Scale Product

### Typical Characteristics

- Multiple user roles
- Moderate integrations
- External customers
- Growing data volume
- Performance matters
- Multiple teams may be involved

### Examples

- SaaS application
- Customer portal
- Marketplace module
- Fintech feature set
- Multi-tenant dashboard

### Analyst Standard for Tier 2

Balance **speed, structure, and foresight**.

#### Mandatory Artifacts

- Executive summary
- Detailed problem analysis
- Personas
- End-to-end user journey
- Complete functional requirements
- Measurable NFRs
- Edge cases
- Risks & dependencies
- Success metrics

### Additional Expectations

The analyst must:

- Consider future scale
- Validate data flows
- Identify integration contracts
- Anticipate permission models
- Think about backward compatibility

### Golden Rule — Tier 2

> Design for growth, not just for launch.

---

## 🔴 Tier 3 — Enterprise / High-Scale Product

### Typical Characteristics

- High user volume
- Multiple systems involved
- Strict compliance/security
- Distributed architecture
- High availability requirements
- Multiple stakeholder groups
- Long product lifecycle

### Examples

- Loan origination platform
- Core banking module
- Healthcare platform
- Large marketplace
- Multi-region SaaS
- Platform ecosystems

---

## 🧠 Analyst Mindset at Enterprise Level

At this level, the Product Analyst must think like:

- System thinker
- Risk manager
- Data strategist
- Platform designer
- Change impact analyst

---

## Mandatory Artifacts — Tier 3

All Tier 2 artifacts PLUS:

### 📊 Advanced Analysis

- System context diagram
- Data flow overview
- Integration contracts
- Permission matrix
- Audit & compliance mapping
- Failure recovery scenarios
- Migration considerations (if applicable)
- Observability requirements
- Rollout strategy
- Backward compatibility notes

---

### 🔒 Enterprise NFR Depth

Must explicitly cover:

- Throughput targets
- Concurrency limits
- Data retention rules
- Encryption requirements
- Audit trail requirements
- Disaster recovery
- RTO / RPO
- Multi-region considerations
- SLA definitions

---

### 🚨 Risk Discipline (Critical)

Enterprise analysts must always evaluate:

- Regulatory risk
- Data privacy risk
- Performance bottlenecks
- Integration fragility
- Release blast radius
- Rollback strategy

### Golden Rule — Tier 3

> If it can fail at scale, document it before it fails in production.

---

# 🔄 Product Evolution Model

Products typically evolve through these stages:

```
MVP → Growth → Scale → Enterprise Hardening
```

---

## Stage 1 — MVP

**Focus on:**

- Fast validation
- Core user value
- Minimal viable scope
- Learning loops

**Avoid:**

- Premature optimization
- Over-architecture
- Heavy governance

---

## Stage 2 — Growth

**Focus on:**

- Performance tuning
- Role management
- Data correctness
- Integration readiness
- UX friction removal

---

## Stage 3 — Scale

**Focus on:**

- Reliability
- Observability
- Concurrency
- Fault tolerance
- Cost efficiency

---

## Stage 4 — Enterprise Hardening

**Focus on:**

- Compliance
- Auditability
- Security depth
- SLA guarantees
- Multi-region readiness
- Backward compatibility
- Change management

---

# 📋 SRS Writing Standards

## 1. Executive Summary Standard

Must include:

- Business objective
- Target users
- Problem being solved
- Expected impact

### ✅ Good Example

> The goal of this feature is to reduce loan application abandonment by enabling users to save and resume applications across devices.

### ❌ Bad Example

> Improve user experience for applications.

---

## 2. Problem Statement Standard

Must be **evidence-based**, not generic.

### Include

- Current workflow
- Pain points
- Quantified impact (if available)
- System gaps

---

## 3. Functional Requirement Standards

Every requirement MUST be:

- Atomic
- Testable
- Measurable
- Unambiguous

---

### ✅ Requirement Template (MANDATORY)

```
FR-###: <Short Title>

Description:
<Clear system behavior>

Priority:
Must / Should / Nice to Have

Acceptance Criteria:
- Given …
- When …
- Then …
```

---

### ✅ Good Requirement Example

**FR-001: Save Application Draft**

**Description:**
The system shall allow users to save a partially completed loan application and resume it later.

**Priority:**
Must

**Acceptance Criteria:**

- Given the user has entered at least one required field
- When the user clicks "Save Draft"
- Then the system shall persist the application data
- And the user shall be able to resume within 30 days

---

### ❌ Bad Requirement Example

> System should allow users to save progress easily.

---

# 🔒 Non-Functional Requirement Standards

## Performance

✅ Good:

> System shall support 5,000 concurrent users with page response time < 2 seconds (p95).

❌ Bad:

> System should be fast.

---

## Security

Must consider:

- Authentication
- Authorization
- Data protection
- Audit logging
- Compliance

---

## Availability

Example:

> System uptime shall be ≥ 99.9% monthly excluding scheduled maintenance.

---

## Observability

Must include:

- Logging
- Monitoring
- Alerting

---

# 🚨 Edge Case Thinking Standard

Senior analysts **proactively identify failures**.

## Mandatory Edge Case Categories

- Invalid inputs
- Network failures
- Partial saves
- Concurrent edits
- Permission issues
- Third-party failures
- Data corruption scenarios

---

### Example

**Edge Case:** User session expires during payment.

**Expected Behavior:**

- Preserve transaction state
- Show recoverable error
- Allow retry without data loss

---

# 🧪 Example — Same Feature at Different Scales

## Feature: Save User Progress

### 🟢 Small Product Version

- Save draft locally
- Single user
- Basic persistence

### 🟡 Mid-Scale Version

- Cross-device resume
- Multi-user environment
- Session handling
- Conflict handling

### 🔴 Enterprise Version

Must additionally include:

- Concurrent edit protection
- Audit trail
- Version history
- Data encryption
- Timeout recovery
- Multi-region consistency
- Partial failure handling
- Event logging
- Monitoring alerts

---

# 📏 Analyst Scalability Checklist

Before finalizing any SRS, the analyst must ask:

- What tier is this product?
- What will break at 10× scale?
- What will break at 100× scale?
- Who else depends on this?
- What happens on partial failure?
- Can QA test this directly?
- Can engineering estimate this confidently?
- Is the customer value explicit?

---

# 🚫 Common Anti-Patterns to Avoid

- Writing UI instead of behavior
- Mixing multiple requirements in one
- Hidden scope
- Missing failure handling
- Vague NFRs
- Ignoring data flows
- Skipping customer pain analysis
- Over-engineering MVP

---

# ✅ Definition of Done (Product Analyst)

An SRS is considered **Done** only when:

- Engineering can estimate without clarification
- QA can write test cases directly
- Architects can design solution
- Stakeholders can approve scope
- Risks are visible
- Edge cases covered
- Business value is explicit
- Every FR has a Source tag (see Source Traceability Standard)

---

---

# Spec-Based Development Standards (MANDATORY)

## SRS Versioning & Change Log

The SRS is a **living document** — it is never replaced, only updated.

**Rules:**

- Every update bumps the version number (e.g., v1.0 → v1.1 for minor, v1.0 → v2.0 for major scope change)
- Every update adds a change log entry at the top of the SRS: date, author, what changed, why
- When new requirements arrive during development, update the existing SRS — do not create a new document
- Flag only the changed/new FRs for architect delta review — not the full SRS

**Change log entry format:**

```
| v1.1 | Apr 2, 2026 | Product Analyst | Added FR-XXX-005 (new requirement from Meeting 12). Source: Meeting 12 §3.2. |
```

## Search Before Writing (MANDATORY)

Before writing any FR, search the knowledge base:

1. Search all meeting transcripts for the topic
2. Search all customer-shared documents
3. Only write the FR if evidence exists
4. If no evidence found → add to stakeholder questionnaire, do NOT write as a confirmed FR

## AC Quality for Spec-Based Development

Acceptance criteria must be **machine-testable** — specific enough for a Kiro agent to generate code and for QA to write a test case without interpretation.

**Required:** Exact status codes, exact field names, exact validation rules, exact error messages
**Prohibited:** Vague language ("handles errors gracefully", "works correctly", "user-friendly")

| Bad AC                       | Good AC                                                                |
| ---------------------------- | ---------------------------------------------------------------------- |
| System handles invalid input | Returns HTTP 400 with `{"code": "VALIDATION_ERROR", "field": "phone"}` |
| User sees an error message   | Toast notification: "Phone number is required" appears within 200ms    |
| System saves the record      | Record appears in DB with `created_at` timestamp within 2 seconds      |

## Questionnaire for Unknowns

When a requirement is unclear or has no source evidence:

- Do NOT guess or fill in with "reasonable defaults"
- Add it to the stakeholder questionnaire with: context, options, recommendation, impact of not deciding
- Mark the FR as `Source: UNVERIFIED — pending questionnaire response`
- The architect will skip designing for UNVERIFIED FRs until resolved

# 🔗 Source Traceability Standard (MANDATORY)

Every functional requirement in the SRS must trace to a concrete source. This enables the architecture review agent to validate requirements without guessing.

## Rules

1. **Every FR must have a `Source:` tag** citing the meeting number, customer document, stakeholder name, or live system observation it came from
2. **If a requirement has no source** — search all meeting transcripts and customer documents in the knowledge base before adding it
3. **If no evidence is found** — mark the requirement as `Source: UNVERIFIED — needs stakeholder confirmation` and add it to the stakeholder questionnaire
4. **Never fabricate requirements** — if no meeting or document says it, don't add it to the SRS. Raise it as a question instead.
5. **Assumptions must be labeled** — if you're filling a gap with a reasonable default, mark it as `Source: Assumption — [rationale]`, not as a confirmed requirement

## FR Template

```markdown
### FR-XXX-NNN: {Title}

**Priority:** Must Have | Should Have | Could Have
**Source:** Meeting {N} FR-{X}, {stakeholder name} | {document name} §{section} | UNVERIFIED

**Description:**
{What the system shall do}

**Acceptance Criteria:**

- {Testable criterion 1}
- {Testable criterion 2}
```

## What the Architecture Review Agent Checks

The architect sub-agent will validate every FR against this standard:

- FR has a `Source:` tag → ✅ proceed to design
- FR has `Source: UNVERIFIED` → ⚠️ skip design, confirm it's in the questionnaire
- FR has no `Source:` tag → ❌ reject — send back to product analyst

This creates a clean handoff: the product analyst produces traceable requirements, the architect designs only from verified ones.

---

# 🚀 Final Standard

A Senior Product Analyst does **not** apply the same rigor to every product.

Instead, they:

- Classify product complexity
- Apply the right level of depth
- Maintain requirement quality
- Anticipate future scale
- Protect delivery teams from ambiguity
- Ensure customer value is always explicit

---

**End of Document**

---

# 🔗 Source Traceability Standard (MANDATORY)

Every functional requirement in the SRS must trace to a concrete source.

## Rules

1. Every FR must have a `Source:` tag citing the meeting number, customer document, stakeholder name, or live system observation
2. If a requirement has no source — search all meeting transcripts and customer documents in the knowledge base before adding it
3. If no evidence is found — mark as `Source: UNVERIFIED — needs stakeholder confirmation` and add to the stakeholder questionnaire
4. Never fabricate requirements — if no meeting or document says it, raise it as a question instead
5. Assumptions must be labeled `Source: Assumption — [rationale]`, not as confirmed requirements

## FR Template

```markdown
### FR-XXX-NNN: {Title}

**Priority:** Must Have | Should Have | Could Have
**Source:** Meeting {N} §{section} | {document name} §{section} | UNVERIFIED

**Description:**
{What the system shall do}

**Acceptance Criteria:**
- {Testable criterion 1}
- {Testable criterion 2}
```

---

# ✅ Acceptance Criteria Machine-Testability Standard (MANDATORY)

AC must be specific enough for a Kiro agent to generate code and for QA to write a test case without interpretation.

**Required:** Exact status codes, exact field names, exact validation rules, exact error messages
**Prohibited:** Vague language (`handles errors gracefully`, `works correctly`, `user-friendly`)

| Bad AC | Good AC |
|--------|---------|
| System handles invalid input | Returns HTTP 400 with `{"code": "VALIDATION_ERROR", "field": "phone"}` |
| User sees an error message | Toast notification: "Phone number is required" appears within 200ms |
| System saves the record | Record appears in DB with `created_at` timestamp within 2 seconds |

---

# 📝 SRS Versioning and Change Log Standard (MANDATORY)

The SRS is a living document — it is never replaced, only updated.

## Rules

- Every update bumps the version number (v1.0 → v1.1 for minor, v1.0 → v2.0 for major scope change)
- Every update adds a change log entry at the top of the SRS
- When new requirements arrive during development, update the existing SRS — do not create a new document
- Flag only the changed/new FRs for architect delta review — not the full SRS

## Change Log Entry Format

```
| vX.X | {Date} | Product Analyst | {What changed and why. Source: {meeting/email/doc}.} |
```

---

# 🚨 NFR Best-Practice Assumption Labeling (MANDATORY)

Never add an NFR, performance target, or technical standard as a confirmed client requirement unless it was explicitly stated by the client in a meeting, email, or SOW.

## Required Treatment for Best-Practice NFRs

1. Label it clearly as a Cloudelligent recommendation:
   > `Source: Cloudelligent recommended best practice — pending client confirmation`
2. Add a corresponding question to the kickoff questionnaire with the estimated AWS cost
3. Add an open question (OQ) in §13 so it is tracked

**Applies to:** uptime SLAs, performance targets (TTFB, p95), monitoring/alerting, security controls (WAF, encryption), compliance (HIPAA, SOC2), backup/retention policies.

---

# 🔍 Search Before Writing (MANDATORY)

Before writing any FR, search the knowledge base:

1. Search all meeting transcripts for the topic
2. Search all customer-shared documents
3. Only write the FR if evidence exists
4. If no evidence found → add to stakeholder questionnaire, do NOT write as a confirmed FR

This prevents fabricated requirements from entering the SRS and causing wasted architecture and development work.
