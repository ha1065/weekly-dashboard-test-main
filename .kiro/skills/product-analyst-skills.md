# Product Analyst Skills

## Existing Product Audit & Improvement Framework

### Phase 1: Discovery

#### Functional Coverage
- Map all existing features against stated business goals
- Identify features that are unused, underused, or misused
- Document gaps: what users need but the product doesn't provide

#### UX Review
- Walk through all user flows end-to-end
- Identify friction points: extra clicks, confusing labels, dead ends
- Note accessibility issues: keyboard navigation, screen reader support, color contrast

#### Pain Point Discovery
- Review support tickets, user feedback, and NPS scores
- Interview stakeholders: what do users complain about most?
- Identify workarounds users have invented (signals of missing features)

#### Technical Gap Analysis
- Review error logs for recurring failures
- Identify performance bottlenecks (slow pages, timeouts)
- Note security gaps (missing auth, exposed data, weak validation)

#### Business Value Alignment
- Map each feature to a business outcome (revenue, retention, compliance, efficiency)
- Identify features with high cost and low value
- Identify high-value opportunities not yet built

---

### Phase 2: Opportunity Identification

#### Improvement Matrix

| Opportunity | User Impact | Business Value | Effort | Priority |
|-------------|-------------|----------------|--------|----------|
| [feature] | High/Med/Low | High/Med/Low | S/M/L | P1/P2/P3 |

- P1: High impact + High value + Low/Medium effort → do now
- P2: High impact + Medium value OR Medium impact + High value → plan next sprint
- P3: Low impact or Low value → backlog or defer

---

### Phase 3: Design Better Experience

#### Reduce Friction
- Eliminate unnecessary steps in critical flows
- Pre-fill forms with known data
- Provide inline validation (not just on submit)
- Add progress indicators for multi-step flows

#### Improve Clarity
- Replace jargon with plain language
- Add contextual help (tooltips, inline docs)
- Use consistent terminology across the product
- Ensure error messages explain what went wrong and how to fix it

#### Modern UX Patterns
- Optimistic UI updates (show result before server confirms)
- Skeleton screens instead of spinners
- Empty states with actionable prompts (not just "No data")
- Responsive design for all screen sizes

#### Measurable UX Improvements
- Define success metrics before implementing (task completion rate, time-on-task, error rate)
- A/B test significant UX changes
- Track before/after metrics for each improvement

---

### Phase 4: Reflect Improvements in SRS

#### Existing System Assessment
- Document current state: what exists, what works, what doesn't
- Version the SRS: mark sections as "existing" vs "new"

#### Improvement Goals
- State the desired outcome for each improvement
- Link to user pain points and business value

#### Before/After Mapping
- For each improvement: describe current behavior → desired behavior
- Include acceptance criteria for the improved state

---

## Delivery Excellence Checklist

Before marking any requirement as complete:

- [ ] Requirement has a source (meeting, email, stakeholder doc)
- [ ] Requirement has a unique ID (FR-XX)
- [ ] Acceptance criteria are machine-testable (exact values, not "should work")
- [ ] Edge cases are documented (what happens on invalid input, empty state, error)
- [ ] Non-functional requirements are specified (performance, security, accessibility)
- [ ] Requirement is traceable to a business goal
- [ ] Stakeholder has reviewed and approved
