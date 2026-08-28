# Security Quick Start

## Immediate Actions (Before First Use)

### 1. Secure Your .env File

```bash
# Set correct permissions
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (only you can read/write)
```

### 2. Use Strong Credentials

In your `.env` file:
```bash
# ❌ DON'T use these
DATABASE_URL=postgresql://admin:password@localhost/db
CLOCKIFY_API_KEY=test

# ✅ DO use these
DATABASE_URL=postgresql://report_user:Xk9#mP2$vL8@localhost/weekly_reporting
CLOCKIFY_API_KEY=<your-actual-20+-char-key>
```

### 3. Run Security Check

```bash
# Install security tools
pip install safety bandit

# Run security check
./scripts/security_check.sh

# Fix any errors before proceeding
```

## Production Deployment Checklist

### Before Deploying

- [ ] Run `./scripts/security_check.sh` with 0 errors
- [ ] Enable database SSL (`DATABASE_URL` should include `?sslmode=require`)
- [ ] Use AWS Secrets Manager (not .env files)
- [ ] Set up database in private VPC subnet
- [ ] Configure security groups properly
- [ ] Enable database encryption at rest
- [ ] Set up CloudWatch logging
- [ ] Review IAM roles (least privilege)

### Database Security

```bash
# For RDS, ensure:
# - Encryption at rest: ENABLED
# - SSL/TLS: REQUIRED
# - Public accessibility: DISABLED
# - VPC: Private subnet only
# - Security group: Restricted to Lambda/QuickSight only
```

### Secrets Management

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
    --name weekly-reporting/prod \
    --secret-string '{
        "database_url": "postgresql://...",
        "clockify_api_key": "...",
        "clockify_workspace_id": "..."
    }'
```

## Common Security Issues

### Issue 1: .env File Exposed

**Symptom**: .env file committed to git

**Fix**:
```bash
# Remove from git history
git rm --cached .env
git commit -m "Remove .env from git"

# Rotate all secrets
# - Change database password
# - Regenerate Clockify API key
# - Update .env with new values
```

### Issue 2: Weak Database Password

**Symptom**: Password is "password", "admin", or similar

**Fix**:
```bash
# Generate strong password
openssl rand -base64 24

# Update database user
psql -c "ALTER USER report_user PASSWORD 'NEW_STRONG_PASSWORD';"

# Update .env
nano .env
```

### Issue 3: No SSL for Database

**Symptom**: Connection not encrypted

**Fix**:
```bash
# Update DATABASE_URL in .env
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# For RDS, SSL is automatic
# For self-hosted, configure PostgreSQL SSL
```

## Security Monitoring

### Daily Checks

```bash
# Check import logs for failures
tail -100 logs/scheduled_import.log | grep ERROR

# Check database logs
psql -c "SELECT * FROM vw_import_activity WHERE status = 'failed';"
```

### Weekly Checks

```bash
# Check for vulnerabilities
pip list --outdated
safety check

# Review access logs (if using CloudWatch)
aws logs tail /aws/lambda/clockify-import --since 7d | grep ERROR
```

### Monthly Checks

```bash
# Update dependencies
pip install --upgrade -r requirements.txt

# Run security scan
bandit -r src/

# Review IAM permissions
aws iam get-role-policy --role-name lambda-execution-role
```

## Quick Security Tips

1. **Never** commit `.env` to git
2. **Always** use `chmod 600 .env`
3. **Never** hardcode credentials in code
4. **Always** enable database SSL in production
5. **Never** use default passwords
6. **Always** rotate API keys every 90 days
7. **Never** expose Streamlit to public internet without authentication
8. **Always** use VPC for Lambda and RDS
9. **Never** log sensitive data
10. **Always** sanitize error messages

## Emergency Response

If credentials are compromised:

```bash
# 1. Immediately rotate credentials
# Generate new Clockify API key in Clockify UI
# Change database password:
psql -c "ALTER USER report_user PASSWORD 'NEW_PASSWORD';"

# 2. Update .env
nano .env

# 3. Restart all services
# Stop cron jobs, Lambda functions, etc.

# 4. Review logs for unauthorized access
grep "UNAUTHORIZED\|FAILED\|ERROR" logs/*.log

# 5. Update AWS Secrets Manager (if using)
aws secretsmanager update-secret --secret-id weekly-reporting/prod \
    --secret-string '{"database_url":"...","clockify_api_key":"..."}'

# 6. Document incident
# Create incident report with timeline
```

## Resources

- Full security documentation: [docs/SECURITY.md](docs/SECURITY.md)
- AWS Security best practices: https://aws.amazon.com/security/
- PostgreSQL security: https://www.postgresql.org/docs/current/security.html
- OWASP Top 10: https://owasp.org/www-project-top-ten/

## Questions?

For security concerns, contact your security team immediately.

**Do not**:
- Post credentials in Slack/email
- Share .env files
- Commit secrets to git
- Ignore security warnings
