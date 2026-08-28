# Automation Setup Guide

This guide shows you how to set up automated weekly data imports from Clockify.

## Table of Contents
1. [Overview](#overview)
2. [Local Scheduling (Cron)](#local-scheduling-cron)
3. [AWS EventBridge (Recommended for Production)](#aws-eventbridge-recommended-for-production)
4. [Docker Deployment](#docker-deployment)
5. [Monitoring and Alerts](#monitoring-and-alerts)

---

## Overview

### Import Modes

The application supports three import modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Incremental** | Only import new data since last import | Daily/weekly automation (recommended) |
| **Weekly** | Import last 1 week of data | Ad-hoc updates |
| **Full** | Import last 52 weeks (1 year) | Initial setup only |

### Recommended Schedule

```
Weekly Schedule (Recommended):
- Sunday 11:00 PM: Run incremental import
- Monday 12:00 AM: QuickSight SPICE refresh
- Monday 8:00 AM: Reports available for team

Daily Schedule (Optional):
- Daily 2:00 AM: Run incremental import
- Daily 3:00 AM: QuickSight SPICE refresh
```

---

## Local Scheduling (Cron)

Best for: Development, local servers, or when running on a dedicated machine

### Quick Setup

```bash
# From project root
cd /Users/cdx/weekly-reporting

# Run the setup script
./scripts/setup_cron.sh
```

This will:
- Create a cron job to run every Monday at 1:00 AM
- Set up logging to `logs/scheduled_import.log`
- Use incremental import mode

### Manual Cron Setup

1. **Create logs directory**
   ```bash
   mkdir -p logs
   ```

2. **Open crontab editor**
   ```bash
   crontab -e
   ```

3. **Add cron job**
   ```bash
   # Run incremental import every Monday at 1:00 AM
   0 1 * * 1 cd /Users/cdx/weekly-reporting && /usr/bin/python3 src/scheduled_import.py --mode incremental --notify >> logs/scheduled_import.log 2>&1
   ```

4. **Save and verify**
   ```bash
   crontab -l
   ```

### Cron Schedule Examples

```bash
# Every Monday at 1:00 AM
0 1 * * 1

# Every day at 2:00 AM
0 2 * * *

# Every Sunday at midnight
0 0 * * 0

# Every 6 hours
0 */6 * * *

# Every weekday (Mon-Fri) at 3:00 AM
0 3 * * 1-5
```

### Testing the Scheduled Import

```bash
# Test incremental import manually
python src/scheduled_import.py --mode incremental --notify

# Test weekly import
python src/scheduled_import.py --mode weekly --notify

# View logs
tail -f logs/scheduled_import.log
```

---

## AWS EventBridge (Recommended for Production)

Best for: Production deployments, serverless architecture, AWS-hosted applications

### Architecture

```
EventBridge Rule → Lambda Function → RDS/Database
                       ↓
                QuickSight Refresh API
```

### Option 1: Lambda + RDS

#### Step 1: Package Lambda Deployment

```bash
# Create deployment package
mkdir lambda_package
cd lambda_package

# Copy source code
cp -r ../src .
cp ../requirements.txt .

# Install dependencies
pip install -r requirements.txt -t .

# Create deployment package
zip -r ../clockify_import_lambda.zip .
```

#### Step 2: Create Lambda Function

1. **AWS Console → Lambda → Create Function**
   ```
   Name: clockify-weekly-import
   Runtime: Python 3.11
   Architecture: x86_64
   ```

2. **Upload Code**
   - Upload `clockify_import_lambda.zip`

3. **Configure Lambda**
   ```
   Handler: src.scheduled_import.lambda_handler
   Timeout: 15 minutes
   Memory: 512 MB
   ```

4. **Environment Variables**
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   CLOCKIFY_API_KEY=your_api_key
   CLOCKIFY_WORKSPACE_ID=your_workspace_id
   ```

5. **VPC Configuration** (if database is in VPC)
   - Select VPC, subnets, and security groups

6. **IAM Role Permissions**
   - Add QuickSight refresh permissions (optional):
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "quicksight:CreateIngestion",
       "quicksight:DescribeDataSet"
     ],
     "Resource": "*"
   }
   ```

#### Step 3: Create EventBridge Rule

1. **AWS Console → EventBridge → Rules → Create Rule**
   ```
   Name: clockify-weekly-import-schedule
   Event bus: default
   Rule type: Schedule
   ```

2. **Schedule Pattern**

   For weekly (Sunday 11:00 PM EST):
   ```
   cron(0 3 ? * MON *)
   ```

   For daily (2:00 AM EST):
   ```
   cron(0 6 * * ? *)
   ```

3. **Select Target**
   ```
   Target: Lambda function
   Function: clockify-weekly-import
   ```

4. **Configure Input** (Optional)
   ```json
   {
     "mode": "incremental",
     "notify": true
   }
   ```

#### Step 4: Add Lambda Handler

Create `src/scheduled_import.py` handler for Lambda:

```python
def lambda_handler(event, context):
    """AWS Lambda handler for scheduled imports."""
    import json
    from datetime import datetime

    mode = event.get('mode', 'incremental')

    try:
        if mode == 'incremental':
            run_incremental_import()
        elif mode == 'weekly':
            run_import(weeks_back=1, incremental=False)
        elif mode == 'full':
            run_full_import()

        # Optionally trigger QuickSight refresh
        if event.get('refresh_quicksight', False):
            refresh_quicksight_datasets()

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Import completed successfully',
                'timestamp': datetime.now().isoformat()
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Import failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        }
```

### Option 2: ECS Scheduled Task

For larger workloads or if you prefer containers:

1. **Create Docker image** (see Docker Deployment section)
2. **Push to ECR**
3. **Create ECS Task Definition**
4. **Create EventBridge Rule → ECS Task**

---

## Docker Deployment

Best for: Containerized environments, ECS, Kubernetes

### Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run scheduled import
CMD ["python", "src/scheduled_import.py", "--mode", "incremental", "--notify"]
```

### Build and Run

```bash
# Build image
docker build -t clockify-import .

# Run locally
docker run --env-file .env clockify-import

# Run with custom mode
docker run --env-file .env clockify-import python src/scheduled_import.py --mode weekly
```

### Push to ECR

```bash
# Authenticate
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag image
docker tag clockify-import:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/clockify-import:latest

# Push
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/clockify-import:latest
```

---

## Monitoring and Alerts

### Option 1: CloudWatch Logs (AWS)

Lambda and ECS tasks automatically log to CloudWatch:

```bash
# View logs
aws logs tail /aws/lambda/clockify-weekly-import --follow
```

Create CloudWatch alarms for failures:
```json
{
  "AlarmName": "clockify-import-failures",
  "MetricName": "Errors",
  "Namespace": "AWS/Lambda",
  "Statistic": "Sum",
  "Period": 300,
  "EvaluationPeriods": 1,
  "Threshold": 1,
  "ComparisonOperator": "GreaterThanThreshold"
}
```

### Option 2: Email Notifications

Update `src/scheduled_import.py` to send emails:

```python
import boto3

def send_notification(success: bool, message: str):
    """Send email notification via SES."""
    ses = boto3.client('ses', region_name='us-east-1')

    subject = "✅ Clockify Import Success" if success else "❌ Clockify Import Failed"

    ses.send_email(
        Source='noreply@yourdomain.com',
        Destination={'ToAddresses': ['admin@yourdomain.com']},
        Message={
            'Subject': {'Data': subject},
            'Body': {'Text': {'Data': message}}
        }
    )
```

### Option 3: Slack Notifications

```python
import requests

def send_slack_notification(success: bool, message: str):
    """Send Slack notification."""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')

    color = 'good' if success else 'danger'
    icon = '✅' if success else '❌'

    payload = {
        'attachments': [{
            'color': color,
            'title': f'{icon} Clockify Import {\"Success\" if success else \"Failed\"}',
            'text': message,
            'footer': 'Weekly Reporting System'
        }]
    }

    requests.post(webhook_url, json=payload)
```

### Option 4: Database Monitoring

Query the `vw_import_activity` view to monitor import health:

```sql
-- Check if last import was successful
SELECT *
FROM vw_import_activity
WHERE import_category = 'time_entries'
ORDER BY completed_at DESC
LIMIT 1;

-- Alert if no successful imports in last 48 hours
SELECT
    CASE
        WHEN MAX(completed_at) < NOW() - INTERVAL '48 hours' THEN 'ALERT'
        ELSE 'OK'
    END AS status,
    MAX(completed_at) AS last_import
FROM import_logs
WHERE status = 'success'
  AND import_category = 'time_entries';
```

---

## Testing Your Automation

### 1. Test Import Manually

```bash
# Run incremental import
python src/scheduled_import.py --mode incremental --notify

# Check logs
cat logs/scheduled_import.log
```

### 2. Verify Database

```sql
-- Check import logs
SELECT * FROM vw_import_activity ORDER BY completed_at DESC LIMIT 5;

-- Check data freshness
SELECT MAX(synced_at) FROM clockify_detailed_time_entries;
```

### 3. Test QuickSight Refresh

If you added QuickSight refresh to your automation:

```python
# Test QuickSight refresh
python -c "
from src.scheduled_import import refresh_quicksight_datasets
refresh_quicksight_datasets()
"
```

### 4. Monitor for One Week

- Check logs daily
- Verify data is updating
- Confirm QuickSight dashboards refresh
- Validate no errors in import logs

---

## Troubleshooting

### Import Fails Silently

**Check**:
- Cron job syntax is correct
- Python path is absolute
- Environment variables are set
- Log file is writable

### Database Connection Timeout

**Solutions**:
- Increase Lambda timeout (15 min max)
- Use connection pooling
- Check VPC/security group settings
- Verify database is not overloaded

### Incremental Import Misses Data

**Check**:
- `import_logs` table has correct timestamps
- Time zones are consistent
- Clockify API rate limits not exceeded

---

## Best Practices

1. **Start with Incremental**
   - Use incremental mode for all automated imports
   - Only run full imports when needed

2. **Monitor Import Logs**
   - Set up alerts for import failures
   - Review `vw_import_activity` regularly

3. **Test Before Scheduling**
   - Run manual imports first
   - Verify data accuracy
   - Check QuickSight dashboards

4. **Keep Logs**
   - Rotate log files to prevent disk issues
   - Store import history in database

5. **Plan for Failures**
   - Set up retry logic
   - Send notifications on failure
   - Have manual fallback process

---

## Next Steps

1. ✅ Choose your automation method (cron or EventBridge)
2. ✅ Set up scheduled imports
3. ✅ Configure monitoring and alerts
4. ✅ Test for one week
5. ✅ Document runbook for your team
6. ✅ Schedule QuickSight SPICE refreshes (see [QUICKSIGHT_SETUP.md](QUICKSIGHT_SETUP.md))
