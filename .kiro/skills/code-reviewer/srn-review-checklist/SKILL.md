---
name: project-review-checklist
description: Project-specific code review checklist for backend and frontend. Use when reviewing Lambda handlers, services, components, infrastructure, or migrations.
metadata:
  version: '1.0'
---

## Backend Review Checklist

### Handler Review

- [ ] Uses middleware with correct role array for authorization
- [ ] Uses tenant context wrapper for all DB queries (if multi-tenant)
- [ ] Handler is thin — delegates to service layer (max ~15 lines of logic)
- [ ] Request body parsed and validated with a schema library (e.g., Zod)
- [ ] One-line JSDoc referencing OpenAPI spec — no heavy JSDoc
- [ ] File named `{action}.ts` (e.g., `search.ts`, `create.ts`)

### Service Review

- [ ] No imports from other domains' `services/` — only from `shared/`
- [ ] Parameterized queries only — no string interpolation in SQL
- [ ] Errors thrown as typed error classes with machine-readable codes
- [ ] No PII in log statements

### Types & Validation

- [ ] Types defined in shared types package
- [ ] Schema definitions match TypeScript interfaces
- [ ] No `any` types — `unknown` if truly unknown

### Infrastructure

- [ ] New Lambda uses the project's Lambda construct
- [ ] New route uses the project's API route construct with correct roles
- [ ] IAM permissions are least-privilege (no `*` grants)
- [ ] Stateless stack updated if new domain added

### Documentation

- [ ] OpenAPI spec updated in `specs/api/{domain}.yaml`
- [ ] Domain `README.md` has env vars and IAM permissions listed
- [ ] Types serve as code documentation — no redundant JSDoc

### Database

- [ ] New tables have RLS policies if the project uses row-level security (check project data model)
- [ ] Migration file follows the project migration naming convention (e.g., `001_description.sql` — check `migrations/` directory)
- [ ] Migration is additive — no destructive changes to deployed migrations

---

## Frontend Review Checklist

### Component Review

- [ ] Uses design system components and theme tokens
- [ ] Error boundaries on critical features
- [ ] Loading, error, and empty states handled
- [ ] Accessible: semantic HTML, ARIA labels, keyboard navigation

### Data & State

- [ ] API calls go through domain hooks
- [ ] Types imported from shared types package
- [ ] No raw `fetch` calls — uses the project's API client wrapper

### i18n

- [ ] User-facing strings use translation keys, not hardcoded text
- [ ] Translation keys added to all supported locale files

---

## Security Review (Both)

- [ ] No hardcoded secrets, API keys, or credentials
- [ ] Authorization checked before accessing sensitive data
- [ ] Input validation on all API boundaries
- [ ] Audit logging for sensitive actions (impersonation, admin operations, data export)
- [ ] PII/PHI obfuscation applied where required by compliance

---

## Gotchas

- Missing tenant context = silent empty results, not an error. This is the #1 bug to catch in multi-tenant apps.
- Cross-domain service imports are the #2 most common violation. Use `find_references` to verify.
- Handlers that grow beyond ~15 lines of logic always need extraction to a service.
- New endpoints without OpenAPI spec updates break the documentation contract.
- Frontend components without error boundaries will crash the entire page on failure.
- Missing locale translation keys will show raw keys to non-English users.
