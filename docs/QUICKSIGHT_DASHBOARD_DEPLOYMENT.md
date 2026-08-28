# QuickSight Dashboard Deployment Guide

This guide walks you through deploying comprehensive QuickSight dashboards for your Clockify reporting system, including the new pod assignment and practice alignment features.

## Prerequisites

1. **AWS QuickSight Setup**: Ensure QuickSight is enabled in your AWS account
2. **Database Views**: All database views must be created (run `python src/database/apply_views.py`)
3. **VPC Connection**: QuickSight VPC connection to your RDS database
4. **IAM Permissions**: Appropriate QuickSight permissions for your user

## Dashboard Overview

The CloudFormation template creates:

### Datasets
1. **Time Entries Dataset** - Raw time entry data
2. **Resource Utilization Dataset** - Weekly resource utilization metrics
3. **Weekly Time Summary Dataset** - Weekly aggregated data
4. **Project Tracking Dataset** - Project-level time tracking
5. **Client Summary Dataset** - Client-level summaries
6. **Practice Performance Dataset** - 12-week practice alignment trends
7. **Monthly Summary Dataset** - Monthly trends with pod assignment and practice alignment
8. **Active Resources Dataset** - Current resource directory

### Dashboards
1. **Executive Summary Dashboard** - High-level KPIs and trends
   - Monthly hours by practice alignment
   - Pod assignment distribution
   - Key performance indicators

2. **Pod Performance Analysis Dashboard** - Specialized pod tracking
   - Last week vs 30/90-day averages for each pod
   - Trend indicators (upward/downward/stable)
   - Performance ratings and recommendations
   - Free Agent, Alpha, Bravo, SurePoint, A2Z analysis

## Deployment Steps

### Step 1: Gather Required Parameters

You'll need the following information:

```bash
# AWS Account Details
AWS_ACCOUNT_ID="123456789012"
QUICKSIGHT_USERNAME="your-quicksight-username"

# Database Connection
DATABASE_HOST="your-rds-endpoint.region.rds.amazonaws.com"
DATABASE_NAME="clockify_reporting"
DATABASE_USERNAME="admin"
DATABASE_PASSWORD="your-secure-password"

# QuickSight VPC Connection
VPC_CONNECTION_ARN="arn:aws:quicksight:region:account:vpcConnection/connection-id"
```

### Step 2: Deploy the CloudFormation Stack

```bash
# Deploy to production
aws cloudformation deploy \
  --template-file cloudformation/quicksight-dashboards.yaml \
  --stack-name clockify-quicksight-dashboards-prod \
  --parameter-overrides \
    Environment=prod \
    QuickSightUsername=$QUICKSIGHT_USERNAME \
    AwsAccountId=$AWS_ACCOUNT_ID \
    VpcConnectionArn=$VPC_CONNECTION_ARN \
    DatabaseHost=$DATABASE_HOST \
    DatabaseName=$DATABASE_NAME \
    DatabaseUsername=$DATABASE_USERNAME \
    DatabasePassword=$DATABASE_PASSWORD \
  --capabilities CAPABILITY_IAM
```

### Step 3: Verify Deployment

1. **Check Stack Status**:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name clockify-quicksight-dashboards-prod \
     --query 'Stacks[0].StackStatus'
   ```

2. **Get Dashboard URLs**:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name clockify-quicksight-dashboards-prod \
     --query 'Stacks[0].Outputs'
   ```

### Step 4: Initial Data Load

After deployment, trigger initial data loads for all datasets:

```bash
# This script will trigger SPICE refreshes for all datasets
python scripts/refresh_quicksight_datasets.py --environment prod
```

## Dashboard Features

### Executive Summary Dashboard

**Key Visualizations:**
- **Monthly Hours by Practice Alignment**: Bar chart showing total hours across different practice areas
- **Pod Assignment Distribution**: Pie chart showing how hours are distributed across different pods
- **Billable Hours Trend**: Line chart tracking billable hours over time
- **Resource Utilization KPIs**: Key metrics for resource utilization

**Filters Available:**
- Date range (month/quarter/year)
- Practice alignment
- Pod assignment
- Location
- Billable vs non-billable

### Key Metrics Tracked

1. **Resource Utilization**
   - Average utilization percentage by pod
   - Billable vs non-billable hour ratios
   - Resource capacity vs actual hours

2. **Practice Alignment Performance**
   - Hours distribution across practice areas
   - Billable percentage by practice
   - Resource allocation efficiency

3. **Pod Assignment Analytics**
   - Pod performance comparison
   - Cross-pod collaboration patterns
   - Resource distribution across pods

## Customization Options

### Adding New Visualizations

1. **Modify the CloudFormation template** to add new visuals to existing dashboards
2. **Create calculated fields** in QuickSight for custom metrics
3. **Add filters and parameters** for interactive dashboards

### Creating Custom Dashboards

1. Use the existing datasets as data sources
2. Create new dashboard definitions in the CloudFormation template
3. Deploy updates using the same CloudFormation stack

## Troubleshooting

### Common Issues

1. **VPC Connection Errors**
   - Verify VPC connection is active in QuickSight
   - Check security group rules allow QuickSight access

2. **Permission Errors**
   - Ensure QuickSight user has appropriate permissions
   - Verify IAM roles and policies

3. **Data Loading Issues**
   - Check database connectivity
   - Verify view permissions
   - Review SPICE capacity limits

### Monitoring and Maintenance

1. **Set up automated SPICE refreshes** for daily data updates
2. **Monitor QuickSight usage** and costs
3. **Regular dashboard performance reviews**

## Next Steps

1. **Train users** on dashboard navigation and interpretation
2. **Set up alerts** for key metrics thresholds
3. **Create additional dashboards** for specific use cases
4. **Implement row-level security** if needed for multi-tenant access

## Support

For issues with dashboard deployment or customization:
1. Check CloudFormation stack events for deployment errors
2. Review QuickSight logs for data loading issues
3. Consult AWS QuickSight documentation for advanced features