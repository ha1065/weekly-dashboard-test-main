# Technical PM Skills

## Kanban Board Management

### Board Columns
1. **Backlog** — stories not yet scheduled
2. **Spec Ready** — architecture doc exists, ACs complete, story is implementation-ready
3. **In Progress** — developer actively working
4. **In Review** — code review or spec review in progress
5. **Done** — code reviewed, merged, deployed to staging

### WIP Limits
- In Progress: max 2 stories per developer
- In Review: max 3 stories total
- If WIP limit hit: finish current work before pulling new stories

---

## Estimation Framework

### Traditional Development
- Story points: Fibonacci (1, 2, 3, 5, 8, 13)
- 1 point ≈ 4 hours of focused work
- Include: implementation + unit tests + code review + bug fixes
- Add 20% buffer for unknowns

### Spec-Based Development (Kiro)
- 40–60% effort reduction vs traditional
- Kiro generates code from architecture specs — developer reviews and integrates
- Story points still apply but represent review + integration effort
- Track actual vs estimated to calibrate velocity

### Velocity Tracking
- Sprint velocity = story points completed per sprint
- Use last 3 sprints average for planning
- Flag if velocity drops >20% — investigate blockers

---

## Dependency Management

### Dependency Rules
- No story can start until all its blockers are Done
- Infrastructure stories always precede feature stories
- Database migrations precede any story that reads/writes the new schema
- Auth/RBAC stories precede any story that requires authorization

### Dependency Sources
- Architecture docs (explicit "depends on" sections)
- Data model (table creation order)
- API contracts (consumer depends on producer)
- Environment setup (dev environment before any feature work)

---

## Risk Management

### Blockers
- A story is blocked if: a dependency is not Done, a question is unanswered, or a resource is unavailable
- Blocked stories must have a "Blocked By" note with the specific blocker
- Escalate blockers older than 2 days to the orchestrator

### Escalation Path
1. Developer flags blocker in story
2. PM identifies resolution path
3. If unresolved in 2 days → orchestrator
4. If unresolved in 5 days → human stakeholder

---

## Sprint Planning

### Pre-Sprint Checklist
- [ ] All stories in sprint have architecture doc references
- [ ] All stories have acceptance criteria
- [ ] No story is blocked (or blocked stories are explicitly deferred)
- [ ] Sprint capacity calculated (team size × hours × focus factor)
- [ ] Dependencies are ordered correctly within the sprint

### Sprint Ceremonies
- Sprint planning: 1 hour per week of sprint length
- Daily standup: 15 minutes (what did I do, what will I do, any blockers)
- Sprint review: demo completed stories to stakeholders
- Retrospective: what went well, what to improve, action items

---

## Reporting

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Sprint velocity | Stable or improving | Story points completed per sprint |
| Cycle time | < 3 days per story | Time from In Progress to Done |
| Blocked rate | < 10% of stories | Blocked stories / total stories |
| Defect rate | < 5% of stories | Stories reopened after Done |
| Spec coverage | 100% | Stories with spec reference / total stories |
| On-time delivery | > 90% | Stories completed in planned sprint |
| Review round avg | < 1.5 | Total review rounds / stories reviewed |

---

## JIRA-Importable CSV Format

Required columns for all backlog exports:

```
Issue Type, Summary, Description, Priority, Story Points, Sprint, Labels, Component, Assignee Role, Blocked By, SRS Reference, Spec Strategy
```

### Column Definitions

| Column | Values | Notes |
|--------|--------|-------|
| Issue Type | Story, Task, Bug, Epic | Use Story for feature work |
| Summary | Short title | Max 80 chars |
| Description | Full AC list | Markdown supported |
| Priority | Highest, High, Medium, Low | Default: Medium |
| Story Points | 1, 2, 3, 5, 8, 13 | Use Fibonacci |
| Sprint | Sprint 1, Sprint 2, ... | Match sprint names exactly |
| Labels | backend, frontend, infra, security, data | Comma-separated |
| Component | [domain-name] | Match architecture domain |
| Assignee Role | backend-developer, frontend, cloudformation-developer | Match agent names |
| Blocked By | Story IDs | Comma-separated, e.g., "PROJ-1, PROJ-2" |
| SRS Reference | FR-XX | Functional requirement ID from SRS |
| Spec Strategy | Path to architecture doc | e.g., "docs/[feature]-architecture.md" |
```
