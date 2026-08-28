# Secrets Manager Migration — Team Review Document

**Date:** 2026-05-14
**Author:** Platform Engineering
**Status:** Proposed — awaiting team review
**Detailed plan:** `docs/secrets-manager-migration-plan.md`

---

## Summary

Migrate two Lambda API keys from plaintext environment variables into AWS Secrets Manager. No key rotation — values are migrated as-is. This eliminates plaintext secrets visible in the Lambda console and CloudFormation outputs.

---

## What's Changing

| Lambda | Current (plaintext env var) | Target (Secrets Manager) |
|--------|----------------------------|--------------------------|
| `jira-data-pull-lambda` | `JIRA_API_TOKEN` | New secret: `production/weekly-reporting/jira` |
| `clockify-data-processor` | `CLOCKIFY_API_KEY` | Existing secret: `production/weekly-reporting/secrets` |

**Note:** The `clockify_api_key` value already exists in `production/weekly-reporting/secrets` (managed by CloudFormation stack `weekly-reporting-production`). The Clockify Lambda just doesn't read from it yet.

---

## Why

1. **Security posture** — Plaintext API keys are visible to anyone with Lambda console access or `GetFunctionConfiguration` permissions.
2. **Audit trail** — Secrets Manager logs every access via CloudTrail.
3. **Consistency** — The main weekly-reporting Lambda already uses Secrets Manager. These two older Lambdas are the outliers.
4. **Compliance** — Aligns with our standard: no hardcoded credentials in Lambda environment variables.

---

## Scope

### In scope
- Create one new secret (`production/weekly-reporting/jira`)
- Add IAM policies to two existing Lambda roles
- Add a shared `load_secrets()` helper to both Lambda codebases
- Remove plaintext env vars after verification

### Out of scope
- Key rotation (values migrated as-is)
- Changes to the main weekly-reporting Lambda (already uses Secrets Manager)
- Changes to the CloudFormation-managed `ApplicationSecrets` resource
- Any database credential changes

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lambda fails to read secret (IAM misconfiguration) | Medium | High — Lambda stops working | Plaintext vars kept in place during testing; removed only after verification |
| Secret JSON key name mismatch | Low | High — env var not populated | Verification step checks exact key names before removing plaintext |
| Cold start latency increase | Low | Low — one Secrets Manager API call cached per container | `_cache` pattern ensures single fetch per container lifetime |
| Rollback needed after plaintext removal | Low | Low — single CLI command restores env vars | Rollback commands documented with exact values |

---

## Rollback Strategy

- **Before plaintext removal:** Zero risk — both paths work simultaneously. `load_secrets()` only sets env vars that aren't already present.
- **After plaintext removal:** Single AWS CLI command per Lambda restores the plaintext env var. Recovery time: < 2 minutes.

---

## Implementation Sequence

```
Step 1: Create Jira secret in Secrets Manager
Step 2: Attach IAM policies to both Lambda roles
Step 3: Add SECRET_NAME env var to both Lambdas (keep plaintext vars)
Step 4: Deploy code changes (load_secrets() helper)
Step 5: Verify both Lambdas work via invocation + CloudWatch logs
Step 6: Remove plaintext env vars (only after Step 5 passes)
Step 7: Final verification — confirm no auth failures
```

Each step is independently reversible. Steps 1–5 are non-breaking (existing behavior unchanged).

---

## Cost Impact

- **Secrets Manager:** $0.40/month per secret + $0.05 per 10,000 API calls
- **Estimated additional cost:** ~$0.45/month (one new secret + minimal API calls due to container-level caching)
- **No new AWS services introduced**

---

## Decision Points for Team Review

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Proceed with migration? | Yes / No / Defer | Yes — low risk, high security value |
| 2 | Acceptable to keep both paths live during testing? | Yes / No | Yes — zero-downtime approach |
| 3 | Who runs the AWS CLI commands? | Platform eng / DevOps lead | Whoever has `AWSAdministratorAccess-961341524729` profile |
| 4 | Add the Jira secret to CloudFormation long-term? | Yes / No / Defer | Yes (template change in detailed plan §4a), but can defer |
| 5 | Timeline for removing plaintext vars after verification? | Same day / Next day / 1 week soak | Next day — gives time to monitor CloudWatch |

---

## Dependencies

- Access to `AWSAdministratorAccess-961341524729` AWS profile
- Current plaintext values for `JIRA_API_TOKEN` and `CLOCKIFY_API_KEY` (read from Lambda console)
- Ability to deploy updated code to both Lambda functions

---

## Next Steps (after team approval)

1. Schedule implementation window (non-peak hours preferred but not required — zero-downtime approach)
2. Execute steps from `docs/secrets-manager-migration-plan.md`
3. Log completion in `docs/project-progress.md` session log

---

## Approvals

| Role | Name | Decision | Date |
|------|------|----------|------|
| Engineering Lead | | | |
| DevOps / Platform | | | |
| Security (if required) | | | |
