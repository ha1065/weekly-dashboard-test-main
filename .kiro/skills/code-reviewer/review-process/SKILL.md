---
name: review-process
version: 1.0
description: Code review workflow, output format, and severity levels. Use when reviewing any code changes.
---

## Review Workflow

1. Check what files changed (git diff or provided file list)
2. Categorize files: handler / service / db / validation / component / test / migration / cloudformation
3. Run TypeScript diagnostics mentally — check types, imports, missing fields
4. Apply the review checklist per file category (see below)
5. Verify no cross-domain imports (handlers should not import from other handler domains)
6. Produce structured output

## Output Format

```markdown
## Code Review: [Story ID or description]

### 🔴 Critical (block merge)
- **[file:line]** — Description of issue and why it's critical
  - **Fix:** Specific code change needed

### 🟡 Should Fix (fix before or immediately after merge)
- **[file:line]** — Description
  - **Fix:** Suggested change

### 🔵 Suggestions (developer judgment)
- **[file:line]** — Description and rationale

### 💬 Nits (optional, style only)
- **[file:line]** — Minor style suggestion

### ✅ What's Good
- Highlight good patterns, clean code, or smart decisions
```

## Review Checklist

### Backend Handlers
- [ ] Input validated with Zod schema
- [ ] Auth token extracted and userId verified
- [ ] Ownership check on mutations (class owner, enrolled student)
- [ ] Correct HTTP status codes (201 create, 200 read/update, 400/401/403/404/409)
- [ ] Error responses use machine-readable `code` field
- [ ] Handler is thin (~15 lines) — logic delegated to service layer
- [ ] Parameterized SQL queries (no string interpolation)
- [ ] RDS Data API client initialized at module level, not per invocation

### Backend Services
- [ ] Business rules enforced (no past due dates, soft-delete only, etc.)
- [ ] No direct DB calls — uses db/ layer functions
- [ ] No cross-domain service imports

### Database Queries
- [ ] Uses `@aws-sdk/client-rds-data` ExecuteStatementCommand
- [ ] All parameters use the `parameters` array (never string interpolation)
- [ ] Correct column name: `resource_identifier` (not the ERD typo)
- [ ] Soft-delete queries include `AND deleted = false`

### Frontend Components
- [ ] Semantic HTML elements used
- [ ] Loading, empty, and error states handled
- [ ] Accessible labels on interactive elements
- [ ] No hardcoded colors/spacing — uses CSS Modules or design tokens
- [ ] Types imported from `shared/types/`

### CloudFormation
- [ ] Parameterized (no hardcoded ARNs, names, or account IDs)
- [ ] Least-privilege IAM (only rds-data + secretsmanager permissions)
- [ ] API Gateway access logging enabled
- [ ] Lambda runtime Node.js 20.x, ARM64

### Migrations
- [ ] Numbered sequentially
- [ ] Forward-only (no DROP TABLE without explicit approval)
- [ ] Column names match ERD (with `resource_identifier` fix)
- [ ] Includes `created_at`, `updated_at`, `deleted` where applicable

## Severity Levels

| Level | Action | Example |
|-------|--------|---------|
| 🔴 Critical | Block merge | SQL injection, missing auth check, data loss |
| 🟡 Should Fix | Fix before/immediately after | Missing error handling, wrong status code |
| 🔵 Suggestion | Developer judgment | Better naming, refactor opportunity |
| 💬 Nit | Optional | Formatting, comment wording |

## Gotchas

- Check TypeScript types first — many bugs are caught by type mismatches
- Acknowledge good patterns — don't only list problems
- Phrase uncertain issues as questions, not demands
- If a handler changes, check if the corresponding Zod schema was updated too
