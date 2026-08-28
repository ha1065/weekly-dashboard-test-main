# Security Guidelines

## Current Security Assessment

### ✅ Existing Security Features

1. **Credentials Management**
   - Environment variables for secrets
   - `.env` excluded from git
   - No hardcoded credentials

2. **Database Security**
   - SQLAlchemy ORM prevents SQL injection
   - Parameterized queries throughout
   - No raw SQL string concatenation

3. **API Security**
   - API keys in headers (not URLs)
   - HTTPS for Clockify API
   - Retry logic with backoff

### 🔴 Critical Security Issues to Address

#### 1. Database Connection Security

**Issue**: Passwords visible in connection strings and logs

**Fix**: Use connection pooling with SSL and mask credentials in logs

```python
# In src/database/config.py
from urllib.parse import urlparse, parse_qs

# Create engine with SSL and connection pooling
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "sslmode": "require",  # Enforce SSL
        "connect_timeout": 10,
        "application_name": "weekly-reporting"
    },
    echo=False,  # Never log SQL in production
    hide_parameters=True  # Mask parameters in logs
)
```

#### 2. Secrets Validation

**Issue**: Missing/invalid credentials not caught early

**Fix**: Add validation to Settings class

```python
# In src/database/config.py
from pydantic import validator, Field

class Settings(BaseSettings):
    database_url: str = Field(..., min_length=1)
    clockify_api_key: str = Field(..., min_length=20)
    clockify_workspace_id: str = Field(..., min_length=10)

    @validator('database_url')
    def validate_database_url(cls, v):
        if not v or v == "":
            raise ValueError("DATABASE_URL must be set")
        if "password" in v and "password@" in v:
            raise ValueError("Do not use 'password' as your password")
        return v

    @validator('clockify_api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 20:
            raise ValueError("Invalid Clockify API key")
        return v
```

#### 3. Secure .env File Permissions

**Issue**: `.env` file may be readable by all users

**Fix**: Set proper file permissions

```bash
# After creating .env
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (owner read/write only)
```

#### 4. Error Message Sanitization

**Issue**: Stack traces may expose internal details

**Fix**: Add error sanitization

```python
# In src/scheduled_import.py
def sanitize_error(error_message: str) -> str:
    """Remove sensitive information from error messages."""
    import re

    # Remove connection strings
    sanitized = re.sub(r'postgresql://[^/]+@[^/]+/[^\s]+',
                      'postgresql://***:***@***/***/***',
                      str(error_message))

    # Remove API keys
    sanitized = re.sub(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[\w-]+',
                      r'\1***',
                      sanitized,
                      flags=re.IGNORECASE)

    return sanitized
```

### 🟡 Medium Priority Security Enhancements

#### 5. API Key Rotation

**Recommendation**: Implement API key rotation strategy

```python
# In .env
CLOCKIFY_API_KEY=current_key
CLOCKIFY_API_KEY_NEXT=next_key  # For rotation

# In code, support fallback
api_key = settings.clockify_api_key or settings.clockify_api_key_next
```

#### 6. Rate Limiting

**Issue**: No protection against excessive API calls

**Fix**: Add rate limiting to Streamlit UI

```python
# In src/app.py
import time

if 'last_import_time' not in st.session_state:
    st.session_state.last_import_time = 0

if st.button("🔄 Run Import", type="primary"):
    time_since_last = time.time() - st.session_state.last_import_time

    if time_since_last < 300:  # 5 minutes
        st.error(f"Please wait {int(300 - time_since_last)} seconds before importing again")
    else:
        # Run import
        st.session_state.last_import_time = time.time()
```

#### 7. Database Connection Timeout

**Issue**: Long-running queries could lock resources

**Fix**: Add query timeout

```python
# In src/database/config.py
engine = create_engine(
    settings.database_url,
    connect_args={
        "options": "-c statement_timeout=30000"  # 30 second timeout
    }
)
```

#### 8. Audit Logging

**Issue**: No tracking of who did what

**Fix**: Add user context to import logs

```python
# In src/database/models.py - Add to ImportLog
created_by = Column(String(255))  # Username/email
source_ip = Column(String(50))    # IP address (if applicable)

# In import code
import getpass
log.created_by = getpass.getuser()
```

### 🟢 Best Practices to Implement

#### 9. AWS Secrets Manager (Production)

For AWS deployments, use Secrets Manager instead of .env:

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# In config.py
if os.getenv('ENV') == 'production':
    secrets = get_secret('weekly-reporting/prod')
    DATABASE_URL = secrets['database_url']
    CLOCKIFY_API_KEY = secrets['clockify_api_key']
```

#### 10. Database Encryption at Rest

Enable encryption for PostgreSQL:

**AWS RDS**: Enable encryption when creating instance
**Self-hosted**: Configure PostgreSQL with encryption

```sql
-- Verify encryption is enabled
SELECT name, setting
FROM pg_settings
WHERE name LIKE '%encryption%';
```

#### 11. Network Security

**AWS RDS Security Group Rules**:
```
Inbound:
- Port 5432 from Lambda Security Group only
- Port 5432 from specific IP ranges (for QuickSight)

Outbound:
- All traffic (for responses)
```

**QuickSight IP Ranges**: Add to security group
```
# Get QuickSight IP ranges
aws quicksight describe-account-settings --aws-account-id <account-id>
```

#### 12. Secure Streamlit Deployment

If exposing Streamlit publicly:

```bash
# Use authentication
pip install streamlit-authenticator

# Or deploy behind VPN/bastion host
# Or use AWS App Runner with authentication
```

#### 13. PII/GDPR Considerations

**User Data Handling**:
- User names and emails are stored
- Consider if this requires GDPR compliance
- Implement data retention policy
- Add ability to delete user data on request

```sql
-- Data retention: Delete old data
DELETE FROM clockify_detailed_time_entries
WHERE entry_date < NOW() - INTERVAL '2 years';

-- User data deletion (if required)
DELETE FROM clockify_users WHERE email = 'user@example.com';
DELETE FROM clockify_detailed_time_entries WHERE user_name = 'User Name';
```

## Security Checklist

### Development Environment

- [ ] `.env` file has 600 permissions (`chmod 600 .env`)
- [ ] `.env` is in `.gitignore`
- [ ] No credentials in code or comments
- [ ] Database uses strong password
- [ ] Test with least-privilege database user

### Production Deployment

- [ ] Use AWS Secrets Manager or equivalent
- [ ] Enable database SSL/TLS
- [ ] Enable database encryption at rest
- [ ] Configure security groups properly
- [ ] Enable CloudWatch logging
- [ ] Set up CloudWatch alarms for failures
- [ ] Implement database connection pooling
- [ ] Add query timeouts
- [ ] Enable VPC for Lambda (if used)
- [ ] Review IAM roles (least privilege)
- [ ] Enable MFA for AWS account
- [ ] Set up database backups
- [ ] Configure database retention policy

### Ongoing Security

- [ ] Rotate Clockify API keys quarterly
- [ ] Review access logs monthly
- [ ] Update dependencies monthly (`pip list --outdated`)
- [ ] Monitor for SQL injection attempts
- [ ] Review database query logs
- [ ] Audit user access to QuickSight
- [ ] Test disaster recovery annually

## Vulnerability Scanning

### Dependency Scanning

```bash
# Install safety
pip install safety

# Check for known vulnerabilities
safety check

# Update vulnerable packages
pip install --upgrade <package>
```

### Code Scanning

```bash
# Install bandit
pip install bandit

# Scan for security issues
bandit -r src/

# Fix any HIGH or MEDIUM severity issues
```

## Incident Response

If credentials are compromised:

1. **Immediately**:
   - Rotate Clockify API key
   - Change database password
   - Revoke any exposed AWS credentials

2. **Within 1 Hour**:
   - Review access logs for unauthorized access
   - Check database for unauthorized queries
   - Verify data integrity

3. **Within 24 Hours**:
   - Conduct security review
   - Update all passwords/keys
   - Document incident
   - Notify stakeholders if data breach

## Security Contact

For security issues, contact:
- **Internal**: [Your security team]
- **AWS Support**: Create security case
- **Clockify Support**: support@clockify.me

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [Python Security](https://python.readthedocs.io/en/latest/library/security.html)
