# QuickSight Setup Guide

This guide walks you through setting up Amazon QuickSight to connect to your Weekly Reporting PostgreSQL database and create dashboards.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Database Setup](#database-setup)
3. [QuickSight Configuration](#quicksight-configuration)
4. [Creating Datasets](#creating-datasets)
5. [Scheduling SPICE Refreshes](#scheduling-spice-refreshes)
6. [Best Practices](#best-practices)

---

## Prerequisites

### 1. PostgreSQL Database
- Your PostgreSQL database should be accessible from AWS
- Note your connection details:
  - Host/Endpoint
  - Port (default: 5432)
  - Database name
  - Username/Password

### 2. AWS Account
- AWS account with QuickSight enabled
- Appropriate IAM permissions for QuickSight
- QuickSight Enterprise Edition recommended for SPICE scheduling

### 3. Network Access
Ensure QuickSight can reach your database:
- **AWS RDS**: Add QuickSight IP ranges to security group
- **Self-hosted**: Configure firewall rules
- **VPC**: Set up VPC connection in QuickSight

---

## Database Setup

### Step 1: Initialize Database Schema

```bash
# From project root
cd /Users/cdx/weekly-reporting

# Initialize database tables
python src/database/init_db.py

# Create reporting views
python src/database/apply_views.py
```

### Step 2: Run Initial Data Import

```bash
# Import 1 year of historical data
python -c "from src.integrations.import_clockify_data import run_full_import; run_full_import()"
```

Or use the Streamlit UI:
```bash
streamlit run src/app.py
# Navigate to "Data Import" → Select "Initial Load (1 Year)" → Click "Run Import"
```

### Step 3: Verify Database Views

Connect to your PostgreSQL database and verify views were created:

```sql
-- List all views
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'public'
AND table_name LIKE 'vw_%';
```

You should see 10 views:
- `vw_weekly_time_summary`
- `vw_resource_utilization`
- `vw_project_time_tracking`
- `vw_client_time_summary`
- `vw_skill_area_summary`
- `vw_daily_activity_trend`
- `vw_active_resources`
- `vw_import_activity`
- `vw_practice_alignment_performance_12w`
- `vw_monthly_summary` (Enhanced with pod assignment and practice alignment)

---

## Automated Deployment Option

For a faster setup, you can use the automated CloudFormation deployment:

### Quick Start with CloudFormation

```bash
# Deploy all datasets and dashboards automatically
./scripts/deploy_quicksight_dashboards.sh \
  --environment prod \
  --aws-account-id 123456789012 \
  --quicksight-user your-username \
  --vpc-connection arn:aws:quicksight:region:account:vpcConnection/conn-id \
  --database-host your-db-host.region.rds.amazonaws.com \
  --database-pass your-secure-password
```

This will create:
- All 8 datasets with proper SPICE configuration
- Executive Summary Dashboard with pod and practice alignment visuals
- Proper permissions and security settings

See [QUICKSIGHT_DASHBOARD_DEPLOYMENT.md](QUICKSIGHT_DASHBOARD_DEPLOYMENT.md) for detailed instructions.

---

## Manual Setup (Alternative)

### Step 1: Create Data Source

1. **Sign in to QuickSight**
   - Navigate to: https://quicksight.aws.amazon.com/

2. **Create New Data Source**
   - Click "Datasets" → "New dataset"
   - Select "PostgreSQL"

3. **Configure Connection**
   ```
   Data source name: Cloudelligent-Weekly-Reporting
   Database server: [your-database-host]
   Port: 5432
   Database name: [your-database-name]
   Username: [your-username]
   Password: [your-password]
   ```

4. **Test Connection**
   - Click "Validate connection"
   - Fix any network/security issues if validation fails

5. **Enable VPC Connection** (if needed)
   - Go to QuickSight settings → "Manage VPC connections"
   - Create VPC connection if your database is in a VPC

### Step 2: Configure SSL (Recommended)

For production databases, enable SSL:
```
Enable SSL: Yes
```

---

## Creating Datasets

Create one dataset per view for optimal performance. QuickSight SPICE will cache the data.

### Dataset 1: Weekly Time Summary

1. **Create Dataset**
   - Data source: Cloudelligent-Weekly-Reporting
   - Select: `vw_weekly_time_summary`

2. **Import to SPICE**
   - Select "Import to SPICE for quicker analytics"
   - Click "Visualize"

3. **Dataset Settings**
   - Rename to: "Weekly Time Summary"
   - Set refresh schedule (see Scheduling section)

### Dataset 2: Resource Utilization

1. Select view: `vw_resource_utilization`
2. Import to SPICE
3. Rename: "Resource Utilization"

### Dataset 3: Project Time Tracking

1. Select view: `vw_project_time_tracking`
2. Import to SPICE
3. Rename: "Project Time Tracking"

### Recommended Datasets for Weekly Reporting

Create datasets for these views based on your reporting needs:

| View Name | Dataset Name | Primary Use Case |
|-----------|-------------|------------------|
| `vw_weekly_time_summary` | Weekly Time Summary | Executive dashboard, high-level metrics |
| `vw_resource_utilization` | Resource Utilization | Resource planning, capacity management |
| `vw_project_time_tracking` | Project Time Tracking | Project status, client reporting |
| `vw_practice_alignment_performance_12w` | Practice Alignment Performance | Trend analysis, performance tracking |
| `vw_monthly_summary` | Monthly Summary | Historical trends with pod and practice insights |
| `vw_active_resources` | Active Resources | Resource directory, team composition |
| `vw_client_time_summary` | Client Time Summary | Client reporting, billing |
| `vw_skill_area_summary` | Skill Area Summary | Pod and practice distribution by skills |

---

## Scheduling SPICE Refreshes

### Option 1: QuickSight Schedule (Recommended)

1. **Go to Dataset Settings**
   - Datasets → Select dataset → "Refresh" tab

2. **Add Refresh Schedule**
   ```
   Schedule name: Weekly Monday Morning Refresh
   Frequency: Weekly
   Day: Monday
   Time: 02:00 AM (after your scheduled import)
   Time zone: [Your timezone]
   ```

3. **Repeat for All Datasets**

### Option 2: API-Based Refresh

After your scheduled import completes, trigger QuickSight refresh:

```python
import boto3

def refresh_quicksight_datasets():
    """Refresh QuickSight SPICE datasets after data import."""
    client = boto3.client('quicksight', region_name='us-east-1')

    datasets = [
        'weekly-time-summary-id',
        'resource-utilization-id',
        # Add your dataset IDs
    ]

    for dataset_id in datasets:
        client.create_ingestion(
            DataSetId=dataset_id,
            IngestionId=f'ingestion-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
            AwsAccountId='your-account-id'
        )
```

Add to `src/scheduled_import.py` for automatic refresh after import.

### Recommended Schedule

```
Sunday 11:00 PM: Clockify data import (incremental)
Monday 12:00 AM: QuickSight SPICE refresh
Monday 8:00 AM: Weekly reports available
```

---

## Best Practices

### 1. Use SPICE for Performance

- Always import to SPICE for dashboards
- SPICE provides in-memory querying (much faster)
- Schedule refreshes after data imports complete

### 2. Create Calculated Fields in QuickSight

Examples:
```
Utilization %: {actual_hours} / {weekly_capacity} * 100
Billable %: {billable_hours} / {total_hours} * 100
Week Label: concat({week_start_date}, ' - ', {week_end_date})
```

### 3. Set Up Row-Level Security (Optional)

If different users should see different data:
1. Create a security dataset with user/data mappings
2. Apply row-level security to datasets
3. Map QuickSight users to data access

### 4. Monitor Import Logs

Use the `vw_import_activity` view to monitor data freshness:
- Create a simple dashboard showing last import time
- Alert if imports fail or are stale

### 5. Optimize Views for QuickSight

The pre-created views are already optimized with:
- Pre-aggregated data (weekly, monthly summaries)
- Denormalized columns (no joins needed in QuickSight)
- Date truncation for easy time-based filtering

### 6. Create Parameter-Based Dashboards

Use QuickSight parameters for:
- Date range selection
- Service line filtering
- Location filtering

---

## Sample Dashboard Layouts

### Executive Dashboard
**Data Sources**: `vw_weekly_time_summary`, `vw_practice_alignment_performance_12w`, `vw_monthly_summary`

**Visuals**:
1. KPI Cards: Total Hours (this week), Resources Working, Billable %
2. Bar Chart: Hours by Practice Alignment (current week)
3. Pie Chart: Hours Distribution by Pod Assignment
4. Line Chart: Practice Alignment Trend (12 weeks)
5. Donut Chart: Onshore vs Offshore distribution
6. Heat Map: Pod vs Practice Alignment matrix

### Resource Management Dashboard
**Data Sources**: `vw_resource_utilization`, `vw_active_resources`, `vw_monthly_summary`

**Visuals**:
1. Table: Resource utilization % by person, pod, and practice
2. Heatmap: Weekly utilization by resource and pod
3. Bar Chart: Top 10 most utilized resources by pod
4. Gauge: Average team utilization by practice alignment
5. Scatter Plot: Pod performance vs practice alignment

### Project Tracking Dashboard
**Data Sources**: `vw_project_time_tracking`, `vw_client_time_summary`

**Visuals**:
1. Table: Active projects with hours, resources, and practice alignment
2. Tree Map: Hours by client and practice
3. Bar Chart: Top projects by hours and pod assignment
4. Line Chart: Project hours trend over time by practice

---

## Troubleshooting

### Connection Issues

**Problem**: QuickSight can't connect to database

**Solutions**:
- Check security group allows QuickSight IP ranges
- Verify database credentials
- Test database connectivity from EC2 instance in same VPC
- Enable VPC connection in QuickSight if needed

### SPICE Refresh Failures

**Problem**: SPICE refresh fails

**Solutions**:
- Check dataset for schema changes
- Verify database is accessible
- Review QuickSight refresh error logs
- Ensure no long-running queries blocking the view

### Missing Data

**Problem**: Data doesn't appear in QuickSight

**Solutions**:
- Verify data was imported to database
- Check view definitions return data
- Refresh SPICE manually
- Review filter settings in dashboard

---

## Support and Resources

- **AWS QuickSight Documentation**: https://docs.aws.amazon.com/quicksight/
- **QuickSight IP Ranges**: https://docs.aws.amazon.com/quicksight/latest/user/regions.html
- **Community Forums**: https://repost.aws/tags/TA4 KCvoRTkS_avJ_rMHhHw2Q/amazon-quick-sight

---

## Next Steps

1. ✅ Set up database connection
2. ✅ Create initial datasets
3. ✅ Build your first dashboard
4. ✅ Schedule SPICE refreshes
5. ✅ Share dashboards with your team
6. ✅ Set up automated imports (see [AUTOMATION_SETUP.md](AUTOMATION_SETUP.md))
