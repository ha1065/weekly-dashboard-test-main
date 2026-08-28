# Plan / Code Reviewer Skills

## Technical Skills

### Cross-Domain Expertise
- Frontend: component architecture, state management, accessibility, i18n
- Backend: API design, database queries, service layer patterns, error handling
- QA: test coverage, test quality, edge case coverage
- DevOps: IaC review, CI/CD pipeline, deployment safety

### Architecture & Design
- System design: service boundaries, data flow, coupling/cohesion
- API design: REST conventions, versioning, error contracts
- Database: schema design, indexing, query performance, migration safety
- Security: auth/authz patterns, input validation, secrets management
- Performance: caching strategies, N+1 queries, Lambda cold starts

### Code Quality Assessment
- Readability: naming, structure, comments where needed
- Maintainability: single responsibility, DRY without over-abstraction
- Testability: pure functions, dependency injection, mockable boundaries
- Correctness: edge cases handled, error paths covered, types accurate

---

## Review Competencies

### Requirements Review
- [ ] Every AC is testable (exact values, not vague descriptions)
- [ ] Edge cases documented (empty input, boundary values, concurrent access)
- [ ] Non-functional requirements specified (latency, throughput, availability)
- [ ] Source traceability: each FR links to a meeting note or stakeholder doc

### Architecture Review
- [ ] Service boundaries respect domain isolation
- [ ] No circular dependencies between domains
- [ ] Data model supports all stated requirements
- [ ] Scalability path is clear (what breaks first at 10× load?)
- [ ] Failure modes documented (what happens when each dependency is down?)

### API Contract Review
- [ ] Request/response schemas are complete and typed
- [ ] Error codes are documented and consistent
- [ ] Authentication and authorization requirements stated
- [ ] Pagination, filtering, sorting behavior defined
- [ ] Breaking vs non-breaking change classification

### Database Schema Review
- [ ] Tables normalized to appropriate level (3NF unless performance justifies denormalization)
- [ ] Indexes on all foreign keys and common query predicates
- [ ] Constraints enforce business rules at DB level
- [ ] Migration is additive (no destructive changes to deployed tables)
- [ ] RLS policies present on all tenant-scoped tables

### Testing Strategy Review
- [ ] Unit tests cover happy path + error paths + edge cases
- [ ] Integration tests cover API contracts end-to-end
- [ ] No tests that only test mocks (test real behavior)
- [ ] Coverage threshold defined and enforced in CI

### Security Review
- [ ] No hardcoded secrets or credentials
- [ ] Input validation on all API boundaries
- [ ] Authorization checked at handler level (not just middleware)
- [ ] PII not logged
- [ ] SQL injection prevention (parameterized queries only)

### Performance Review
- [ ] No N+1 queries (use joins or batch fetches)
- [ ] Expensive operations are async or cached
- [ ] Lambda memory/timeout sized appropriately
- [ ] Database queries use indexes (check EXPLAIN plan for complex queries)

### Documentation Review
- [ ] Architecture doc is spec-ready (a developer can implement without asking questions)
- [ ] API spec updated (OpenAPI or equivalent)
- [ ] README updated if setup steps changed
- [ ] Inline comments explain "why", not "what"

---

## Decision-Making Framework

| Situation | Action |
|-----------|--------|
| All ACs met, no findings | Approve |
| Minor issues (style, naming, small gaps) | Approve with suggestions |
| Missing AC coverage, logic errors, security gaps | Request changes |
| Contradicts architecture doc | Request changes + flag to architect |
| Critical security issue | Block + escalate to orchestrator immediately |
| Ambiguous requirement | Request clarification before approving |
| Max review rounds exceeded | Escalate to human |

---

## Soft Skills

- Be specific: "Line 42: `userId` should be validated before use" not "validate inputs"
- Be constructive: explain why the change is needed, not just what to change
- Distinguish blocking issues from suggestions (use labels: `[blocking]`, `[suggestion]`, `[nit]`)
- Acknowledge good patterns: positive feedback reinforces standards

---

## Continuous Improvement

- Track recurring findings across reviews → add to standards docs
- If the same mistake appears 3+ times → propose a skill or linting rule
- Review the review process itself each sprint retrospective
