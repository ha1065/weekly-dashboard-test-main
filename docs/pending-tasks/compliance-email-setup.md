# Compliance Email Setup — Pending Tasks

**Created:** 2026-06-22  
**Status:** Blocked on Cloudflare DNS

---

## What Was Done

- Added `send_compliance_report` Lambda mode (sends non-compliance email via SES)
- Added two EventBridge rules to `cloudformation/template.yaml`:
  - `production-compliance-email-930am-ct` — Mon 9:30 AM CT, `run=morning`
  - `production-compliance-email-1230pm-ct` — Mon 12:30 PM CT, `run=noon`
- CloudFormation **not yet deployed** — pending SES verification first

---

## Blocked On: Cloudflare DNS — DKIM Records

Colleague needs to add these 3 CNAME records in Cloudflare for `cloudelligent.com`.  
**Proxy must be DNS only (grey cloud) — NOT proxied.**

| Type | Name | Target |
|------|------|--------|
| CNAME | `5k5gw4uayom33vsa4rjq7bteufegt4dv._domainkey` | `5k5gw4uayom33vsa4rjq7bteufegt4dv.dkim.amazonses.com` |
| CNAME | `fy2juwpdz57bae3shqc4zp56akjthmq3._domainkey` | `fy2juwpdz57bae3shqc4zp56akjthmq3.dkim.amazonses.com` |
| CNAME | `4xbbpwkwukotih5dvklarc6x4rp2x2t7._domainkey` | `4xbbpwkwukotih5dvklarc6x4rp2x2t7.dkim.amazonses.com` |

---

## Steps to Complete (in order, after DNS records are added)

```bash
# 1. Confirm DNS resolves (all 3 should return a value)
dig CNAME 5k5gw4uayom33vsa4rjq7bteufegt4dv._domainkey.cloudelligent.com +short
dig CNAME fy2juwpdz57bae3shqc4zp56akjthmq3._domainkey.cloudelligent.com +short
dig CNAME 4xbbpwkwukotih5dvklarc6x4rp2x2t7._domainkey.cloudelligent.com +short

# 2. Re-trigger SES verification
aws sesv2 delete-email-identity --email-identity cloudelligent.com --profile AWSAdministratorAccess-961341524729 --region us-east-1
aws sesv2 create-email-identity --email-identity cloudelligent.com --dkim-signing-attributes SigningAttributesOrigin=AWS_SES --profile AWSAdministratorAccess-961341524729 --region us-east-1

# 3. Poll until Verified=true (may take 15-30 min)
aws sesv2 get-email-identity --email-identity cloudelligent.com --profile AWSAdministratorAccess-961341524729 --region us-east-1 --query '{Verified:VerifiedForSendingStatus,DkimStatus:DkimAttributes.Status}'

# 4. Deploy CloudFormation (adds the two EventBridge rules)
aws cloudformation deploy \
  --template-file cloudformation/template.yaml \
  --stack-name weekly-reporting-production \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile AWSAdministratorAccess-961341524729 \
  --region us-east-1 \
  --no-fail-on-empty-changeset

# 5. Verify recipients are configured in Streamlit Settings → Compliance Report Recipients

# 6. Test the email manually
aws lambda invoke --function-name production-clockify-import --payload '{"mode":"send_compliance_report","run":"morning"}' --cli-binary-format raw-in-base64-out --profile AWSAdministratorAccess-961341524729 /tmp/r.json && cat /tmp/r.json

# 7. Commit the CloudFormation change
git add cloudformation/template.yaml
git commit -m "Add EventBridge rules for Monday compliance email (9:30 AM and 12:30 PM CT)"
git push
```
