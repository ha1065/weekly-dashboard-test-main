# AWS Production Deployment Guide

This guide walks you through deploying the Weekly Reporting application to AWS using CloudFormation.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                            │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │                      VPC                            │    │
│  │                                                     │    │
│  │  ┌──────────────┐      ┌──────────────────────┐   │    │
│  │  │ Public Subnet│      │  Private Subnet      │   │    │
│  │  │              │      │                      │   │    │
│  │  │  NAT Gateway │─────▶│  Lambda Function    │   │    │
│  │  │              │      │  (Import Script)     │   │    │
│  │  └──────────────┘      │         │            │   │    │
│  │                        │         ▼            │   │    │
│  │                        │  RDS PostgreSQL      │   │    │
│  │                        │  (Encrypted)         │   │    │
│  │                        └──────────────────────┘   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────┐    ┌────────────────┐                    │
│  │ EventBridge  │───▶│ Lambda         │                    │
│  │ (Schedule)   │    │ (Weekly Import)│                    │
│  └──────────────┘    └────────────────┘                    │
│                                                              │
│  ┌──────────────┐    ┌────────────────┐                    │
│  │ Secrets      │    │ CloudWatch     │                    │
│  │ Manager      │    │ Logs & Alarms  │                    │
│  └──────────────┘    └────────────────┘                    │
│                                                              │
│  ┌──────────────────────────────────────────┐              │
│  │         Amazon QuickSight                 │              │
│  │  (Connects to RDS for reporting)         │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## What Gets Deployed

### Infrastructure
- **VPC** with public and private subnets across 2 AZs
- **NAT Gateway** for Lambda internet access
- **Security Groups** with least-privilege access
- **RDS PostgreSQL** database (encrypted at rest)
- **Lambda Function** for data imports
- **EventBridge Rule** for scheduled imports
- **Secrets Manager** for credential storage
- **CloudWatch Alarms** for monitoring
- **SNS Topic** for notifications

### Security Features
- Database in private subnet (no public access)
- SSL/TLS encryption in transit
- Encryption at rest for RDS
- Secrets stored in AWS Secrets Manager
- VPC endpoints for AWS services
- CloudWatch logging enabled
- Automated backups (7-day retention)
- Multi-factor deletion protection

## Prerequisites

### 1. AWS Account Setup

```bash
# Install AWS CLI
brew install awscli  # macOS
# or
pip install awscli

# Configure AWS credentials
aws configure
# AWS Access Key ID: <your-key>
# AWS Secret Access Key: <your-secret>
# Default region: us-east-1
# Default output format: json

# Verify access
aws sts get-caller-identity
```

### 2. Required Information

Gather these before deployment:
- [ ] Clockify API Key (from Clockify settings)
- [ ] Clockify Workspace ID
- [ ] Strong database password (16+ characters)
- [ ] Email address for SNS notifications (optional)

### 3. Cost Estimate

**Monthly AWS costs** (approximate):
- RDS db.t3.micro: $15-20/month
- NAT Gateway: $32/month
- Lambda: $0-5/month (free tier eligible)
- Data transfer: $5-10/month
- Total: **~$52-67/month**

For production with larger database:
- RDS db.t3.small: $30-40/month
- Total: **~$67-87/month**

## Deployment Steps

### Step 1: Clone and Prepare

```bash
# Navigate to project
cd /Users/cdx/weekly-reporting

# Install dependencies
pip install -r requirements.txt

# Run security check
./scripts/security_check.sh
```

### Step 2: Deploy Infrastructure

```bash
# Run deployment script
./cloudformation/deploy.sh
```

The script will prompt for:
1. Clockify API Key
2. Clockify Workspace ID
3. Database master password

**Deployment takes ~15-20 minutes** for:
- VPC creation
- RDS database provisioning
- Lambda function deployment
- Network configuration

### Step 3: Initialize Database

After stack creation, connect to initialize:

```bash
# Get database endpoint
aws cloudformation describe-stacks \
  --stack-name weekly-reporting-production \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text

# Option A: Use EC2 bastion host
# Launch EC2 in public subnet, install PostgreSQL client
ssh ec2-user@<bastion-ip>
psql -h <db-endpoint> -U postgres -d postgres

# Option B: Use AWS Systems Manager Session Manager
# (Requires SSM agent on bastion)

# Once connected:
# 1. Create application database user
CREATE USER report_user WITH PASSWORD '<your-password>';
GRANT ALL PRIVILEGES ON DATABASE weekly_reporting TO report_user;

# 2. Connect as report_user
\c weekly_reporting report_user

# 3. Run initialization (from local machine with port forwarding)
python src/database/init_db.py
python src/database/apply_views.py
```

### Step 4: Run Initial Import

```bash
# Trigger full import (1 year of data)
aws lambda invoke \
  --function-name production-clockify-import \
  --payload '{"mode":"full","notify":true}' \
  --region us-east-1 \
  response.json

# Check response
cat response.json

# Monitor logs
aws logs tail /aws/lambda/production-clockify-import --follow
```

### Step 5: Verify Deployment

```bash
# Check database has data
# Connect to database and run:
SELECT COUNT(*) FROM clockify_users;
SELECT COUNT(*) FROM clockify_detailed_time_entries;
SELECT * FROM vw_import_activity ORDER BY completed_at DESC LIMIT 5;

# Verify scheduled import
aws events list-rules --name-prefix production-weekly

# Check CloudWatch alarms
aws cloudwatch describe-alarms --alarm-name-prefix production
```

## Configuration

### Update Import Schedule

```bash
# Edit schedule (default: Monday 3am UTC)
aws events put-rule \
  --name production-weekly-import-schedule \
  --schedule-expression "cron(0 2 ? * SUN *)" \
  --state ENABLED
```

### Add SNS Email Notifications

```bash
# Subscribe to SNS topic
TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name weekly-reporting-production \
  --query 'Stacks[0].Outputs[?OutputKey==`NotificationTopicARN`].OutputValue' \
  --output text)

aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com

# Confirm subscription via email
```

### Scale Database

```bash
# Update stack with larger instance
aws cloudformation update-stack \
  --stack-name weekly-reporting-production \
  --use-previous-template \
  --parameters \
    ParameterKey=DBInstanceClass,ParameterValue=db.t3.small \
  --capabilities CAPABILITY_NAMED_IAM
```

## QuickSight Setup

### Step 1: Create VPC Connection

```bash
# Get security group and subnet IDs
aws cloudformation describe-stacks \
  --stack-name weekly-reporting-production \
  --query 'Stacks[0].Outputs'

# In QuickSight console:
# 1. Go to Manage QuickSight → Manage VPC connections
# 2. Add VPC connection:
#    - VPC: weekly-reporting VPC
#    - Subnet: Private subnet
#    - Security group: Database security group
```

### Step 2: Create Data Source

```bash
# Get connection details
DB_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name weekly-reporting-production \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text)

# In QuickSight:
# 1. New data source → PostgreSQL
# 2. Connection:
#    - Host: $DB_ENDPOINT
#    - Port: 5432
#    - Database: weekly_reporting
#    - Username: report_user
#    - Password: <from Secrets Manager>
# 3. Use VPC connection created above
```

### Step 3: Create Datasets

Import these views to SPICE:
- `vw_weekly_time_summary`
- `vw_resource_utilization`
- `vw_project_time_tracking`
- `vw_service_line_performance_12w`

See [QUICKSIGHT_SETUP.md](QUICKSIGHT_SETUP.md) for detailed instructions.

## Monitoring and Maintenance

### CloudWatch Dashboards

```bash
# View Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=production-clockify-import \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum
```

### View Logs

```bash
# Lambda logs
aws logs tail /aws/lambda/production-clockify-import --follow

# RDS logs
aws rds download-db-log-file-portion \
  --db-instance-identifier production-weekly-reporting \
  --log-file-name error/postgresql.log.2024-01-19-00
```

### Backup and Recovery

```bash
# Manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier production-weekly-reporting \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d)

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier restored-database \
  --db-snapshot-identifier manual-backup-20240119
```

## Troubleshooting

### Lambda Can't Connect to Database

**Check**:
```bash
# Verify Lambda is in VPC
aws lambda get-function-configuration \
  --function-name production-clockify-import \
  --query 'VpcConfig'

# Check security groups
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=*database*"
```

**Fix**: Ensure Lambda security group is allowed in database security group

### Import Fails with Timeout

**Check logs**:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/production-clockify-import \
  --filter-pattern "Task timed out"
```

**Fix**: Increase Lambda timeout in CloudFormation template

### Database Connection Refused

**Check**:
- Database is in available state
- Security groups allow Lambda → Database on port 5432
- Secrets Manager has correct credentials

### High Database CPU

**Monitor**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=production-weekly-reporting \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

**Fix**: Scale up to db.t3.small or optimize queries

## Updating the Application

### Update Lambda Code

```bash
# Update code and redeploy
./cloudformation/deploy.sh

# Or update just Lambda
aws lambda update-function-code \
  --function-name production-clockify-import \
  --zip-file fileb://lambda-deployment-package.zip
```

### Update Database Schema

```bash
# Connect to database
# Run migration scripts

# Or use Alembic
alembic upgrade head
```

## Security Checklist

- [ ] RDS in private subnet (no public IP)
- [ ] SSL enabled for database connections
- [ ] Encryption at rest enabled
- [ ] Secrets in Secrets Manager (not environment variables)
- [ ] Security groups follow least privilege
- [ ] CloudWatch logging enabled
- [ ] Automated backups enabled (7 days)
- [ ] MFA enabled on AWS account
- [ ] IAM roles use least privilege
- [ ] SNS notifications configured

## Cleanup

To delete all resources:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name weekly-reporting-production

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name weekly-reporting-production

# Delete S3 deployment bucket
aws s3 rb s3://weekly-reporting-production-deployments-<account-id> --force

# Delete log groups
aws logs delete-log-group --log-group-name /aws/lambda/production-clockify-import
```

**Note**: Database snapshots are retained. Delete manually if not needed.

## Cost Optimization

### Reduce Costs

1. **Use smaller RDS instance** (db.t3.micro sufficient for <50 users)
2. **Reduce NAT Gateway** (share across multiple workloads)
3. **Use Aurora Serverless** (for variable workloads)
4. **Enable RDS auto-pause** (for development)
5. **Use Lambda reserved concurrency** (predictable workloads)

### Cost Monitoring

```bash
# Get cost estimate
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '1 month ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

## Support

- **AWS Support**: Create support case in AWS Console
- **Documentation**: See [docs/](../docs/) directory
- **CloudFormation**: [template.yaml](template.yaml)

## Next Steps

1. ✅ Deploy infrastructure
2. ✅ Initialize database
3. ✅ Run initial import
4. ✅ Set up QuickSight
5. ✅ Configure SNS notifications
6. ✅ Create dashboards
7. ✅ Train team on system
