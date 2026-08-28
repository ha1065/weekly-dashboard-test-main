# AWS Deployment Quick Start

## One-Command Deployment

```bash
# Deploy everything to AWS
./cloudformation/deploy.sh
```

This will deploy:
- ✅ Secure VPC with public/private subnets
- ✅ RDS PostgreSQL (encrypted, private subnet)
- ✅ Lambda function for automated imports
- ✅ EventBridge schedule (weekly)
- ✅ Secrets Manager for credentials
- ✅ CloudWatch alarms and logging
- ✅ SNS notifications

**Time**: ~15-20 minutes
**Cost**: ~$52-67/month

---

## Prerequisites

```bash
# 1. Install AWS CLI
brew install awscli  # macOS
pip install awscli   # Other

# 2. Configure credentials
aws configure

# 3. Gather info
# - Clockify API Key
# - Clockify Workspace ID
# - Strong DB password (16+ chars)
```

---

## After Deployment

### 1. Initialize Database

```bash
# Get DB endpoint
aws cloudformation describe-stacks \
  --stack-name weekly-reporting-production \
  --query 'Stacks[0].Outputs'

# Connect via bastion/VPN and run:
python src/database/init_db.py
python src/database/apply_views.py
```

### 2. Run Initial Import

```bash
# Import 1 year of data
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"full"}' \
  response.json
```

### 3. Setup QuickSight

```bash
# In QuickSight console:
# 1. Create VPC connection
# 2. Add PostgreSQL data source
# 3. Import views to SPICE
# 4. Build dashboards
```

See [docs/QUICKSIGHT_SETUP.md](docs/QUICKSIGHT_SETUP.md)

---

## Architecture

```
Internet
    ↓
EventBridge (Schedule)
    ↓
Lambda (VPC)
    ↓
RDS PostgreSQL (Private Subnet, Encrypted)
    ↓
QuickSight (via VPC connection)
```

---

## What's Deployed

| Resource | Details |
|----------|---------|
| **VPC** | 10.0.0.0/16 with 2 AZs |
| **RDS** | PostgreSQL 15.4, encrypted, private |
| **Lambda** | Python 3.11, 512MB, 15min timeout |
| **Schedule** | Monday 3am UTC (configurable) |
| **Backups** | 7-day retention |
| **Monitoring** | CloudWatch alarms for errors/CPU |

---

## Security Features

- ✅ Database in private subnet (no internet access)
- ✅ SSL/TLS encryption required
- ✅ Encryption at rest enabled
- ✅ Secrets in AWS Secrets Manager
- ✅ Security groups: least privilege
- ✅ CloudWatch logging enabled
- ✅ Automated backups
- ✅ Deletion protection

---

## Common Commands

### Check Import Status
```bash
aws logs tail /aws/lambda/production-clockify-import --follow
```

### Manual Import
```bash
# Incremental (new data only)
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"incremental"}' \
  response.json

# Last 4 weeks
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"weekly","weeks_back":4}' \
  response.json
```

### Get Database Credentials
```bash
aws secretsmanager get-secret-value \
  --secret-id production/weekly-reporting/secrets \
  --query SecretString \
  --output text | jq .
```

### Subscribe to Notifications
```bash
TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name weekly-reporting-production \
  --query 'Stacks[0].Outputs[?OutputKey==`NotificationTopicARN`].OutputValue' \
  --output text)

aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com
```

---

## Troubleshooting

### Import Fails
```bash
# Check logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/production-clockify-import \
  --filter-pattern "ERROR"

# Check secrets
aws secretsmanager get-secret-value \
  --secret-id production/weekly-reporting/secrets
```

### Can't Connect to Database
- Verify Lambda is in VPC
- Check security group rules
- Ensure database is "available"

### High Costs
```bash
# Check actual costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

---

## Update Application

```bash
# Update code and redeploy
./cloudformation/deploy.sh

# Or just update Lambda
aws lambda update-function-code \
  --function-name production-clockify-import \
  --zip-file fileb://lambda-deployment-package.zip
```

---

## Cleanup

```bash
# Delete everything
aws cloudformation delete-stack \
  --stack-name weekly-reporting-production

# Verify deletion
aws cloudformation wait stack-delete-complete \
  --stack-name weekly-reporting-production
```

**Note**: Database snapshots are retained. Delete manually if not needed.

---

## Cost Estimate

| Item | Monthly Cost |
|------|--------------|
| RDS db.t3.micro | $15-20 |
| NAT Gateway | $32 |
| Lambda | $0-5 (free tier) |
| Data transfer | $5-10 |
| **Total** | **$52-67** |

---

## Documentation

- **Full deployment guide**: [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)
- **Security guide**: [docs/SECURITY.md](docs/SECURITY.md)
- **QuickSight setup**: [docs/QUICKSIGHT_SETUP.md](docs/QUICKSIGHT_SETUP.md)
- **Getting started**: [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

---

## Support

- CloudFormation template: [cloudformation/template.yaml](cloudformation/template.yaml)
- Deployment script: [cloudformation/deploy.sh](cloudformation/deploy.sh)
- Lambda handler: [src/lambda_handler.py](src/lambda_handler.py)

---

## Next Steps After Deployment

1. ✅ Initialize database
2. ✅ Run initial import (1 year)
3. ✅ Set up QuickSight connection
4. ✅ Create SPICE datasets
5. ✅ Build dashboards
6. ✅ Subscribe to SNS notifications
7. ✅ Schedule QuickSight SPICE refresh
8. ✅ Train team on reports

**Estimated setup time**: 2-3 hours total
