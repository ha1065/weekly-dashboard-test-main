# QuickSight Dashboard Creation Guide

## Prerequisites

1. QuickSight Enterprise Edition (required for VPC connectivity)
2. VPC connection configured to RDS database
3. IAM role with QuickSight permissions

## Deploy CloudFormation Template

### Option 1: AWS Console

1. Go to CloudFormation → Create Stack
2. Upload `cloudformation/quicksight-dashboards.yaml`
3. Fill in parameters:
   - **QuickSightUsername**: Your QuickSight username
   - **AwsAccountId**: Your AWS account ID
   - **VpcConnectionArn**: ARN of your QuickSight VPC connection
   - **DatabaseHost**: RDS endpoint
   - **DatabasePassword**: Database password

### Option 2: AWS CLI

```bash
aws cloudformation create-stack \
  --stack-name clockify-quicksight \
  --template-body file://cloudformation/quicksight-dashboards.yaml \
  --parameters \
    ParameterKey=QuickSightUsername,ParameterValue=YOUR_USERNAME \
    ParameterKey=AwsAccountId,ParameterValue=YOUR_ACCOUNT_ID \
    ParameterKey=VpcConnectionArn,ParameterValue=YOUR_VPC_CONNECTION_ARN \
    ParameterKey=DatabaseHost,ParameterValue=YOUR_RDS_ENDPOINT \
    ParameterKey=DatabasePassword,ParameterValue=YOUR_PASSWORD
```

---

## Datasets Created by CloudFormation

| Dataset | Source | Description |
|---------|--------|-------------|
| Clockify Time Entries | `clockify_detailed_time_entries` | Raw time entry data |
| Resource Utilization | `vw_resource_utilization` | Weekly utilization by person |
| Weekly Time Summary | `vw_weekly_time_summary` | Weekly aggregates by practice/location |
| Project Time Tracking | `vw_project_time_tracking` | Project-level tracking |
| Client Time Summary | `vw_client_time_summary` | Client hours and projects |
| Practice Performance | `vw_practice_alignment_performance_12w` | 12-week trends |
| Active Resources | `vw_active_resources` | Resource directory |

---

## Manual Dashboard Creation

After deploying the CloudFormation template, create dashboards manually in QuickSight:

### Dashboard 1: Resource Utilization Dashboard

**Dataset**: Resource Utilization

**Visualizations**:

1. **Weekly Utilization Heatmap**
   - Type: Pivot Table or Heatmap
   - Rows: `user_name`
   - Columns: `week_start_date`
   - Values: `utilization_percent`
   - Color: Gradient (red < 70%, yellow 70-90%, green > 90%)

2. **Utilization Trend Line**
   - Type: Line Chart
   - X-axis: `week_start_date`
   - Y-axis: Average of `utilization_percent`
   - Color: `practice_alignment`

3. **Billable vs Non-Billable Pie Chart**
   - Type: Pie Chart
   - Values: Sum of `billable_hours`, Sum of (`actual_hours` - `billable_hours`)

4. **Top Performers Table**
   - Type: Table
   - Columns: `user_name`, `practice_alignment`, `actual_hours`, `utilization_percent`, `billable_percent`
   - Sort: `utilization_percent` descending

**Filters**:
- `week_start_date` (date range)
- `practice_alignment` (dropdown)
- `location` (dropdown)

---

### Dashboard 2: Practice Alignment Performance

**Dataset**: Practice Performance (12 Weeks)

**Visualizations**:

1. **Hours by Practice (Stacked Bar)**
   - Type: Stacked Bar Chart
   - X-axis: `week_start_date`
   - Y-axis: `total_hours`
   - Color: `practice_alignment`

2. **Billable Percentage Trend**
   - Type: Line Chart
   - X-axis: `week_start_date`
   - Y-axis: `billable_percent`
   - Color: `practice_alignment`

3. **Resource Count by Practice**
   - Type: Bar Chart
   - X-axis: `practice_alignment`
   - Y-axis: `unique_resources`

4. **KPI Cards**
   - Total Hours (sum of `total_hours`)
   - Billable Rate (average of `billable_percent`)
   - Active Projects (sum of `active_projects`)
   - Active Clients (count distinct `active_clients`)

---

### Dashboard 3: Client Analytics

**Dataset**: Client Time Summary

**Visualizations**:

1. **Top Clients by Hours**
   - Type: Horizontal Bar Chart
   - Y-axis: `client_name`
   - X-axis: Sum of `total_hours`
   - Top N: 10

2. **Client Hours Trend**
   - Type: Line Chart
   - X-axis: `week_start_date`
   - Y-axis: `total_hours`
   - Color: `client_name` (top 5)

3. **Resources per Client**
   - Type: Bar Chart
   - X-axis: `client_name`
   - Y-axis: `resources_working`

4. **Client Detail Table**
   - Type: Table
   - Columns: `client_name`, `active_projects`, `resources_working`, `total_hours`, `billable_hours`

**Filters**:
- `week_start_date` (date range)
- `client_name` (dropdown with search)
- `practice_alignment` (dropdown)

---

### Dashboard 4: Project Tracking

**Dataset**: Project Time Tracking

**Visualizations**:

1. **Project Hours Treemap**
   - Type: Treemap
   - Group by: `client_name` → `project_name`
   - Size: `total_hours`
   - Color: `billable_hours`

2. **Active Projects Timeline**
   - Type: Gantt Chart (or horizontal bar)
   - Y-axis: `project_name`
   - Start: `first_entry_date`
   - End: `last_entry_date`

3. **Resources per Project**
   - Type: Bar Chart
   - X-axis: `project_name`
   - Y-axis: `resources_assigned`

4. **Project Detail Table**
   - Type: Table
   - Columns: `project_name`, `client_name`, `total_hours`, `resources_assigned`, `entry_count`

---

### Dashboard 5: Time Entry Analysis

**Dataset**: Clockify Time Entries

**Visualizations**:

1. **Daily Hours Heatmap**
   - Type: Heatmap
   - X-axis: Day of week (calculated from `entry_date`)
   - Y-axis: `user_name`
   - Values: Sum of `duration_hours`

2. **Hours Distribution Histogram**
   - Type: Histogram
   - Values: `duration_hours`
   - Bins: 0-2, 2-4, 4-6, 6-8, 8+

3. **Time by Practice Alignment**
   - Type: Donut Chart
   - Values: Sum of `duration_hours`
   - Group: `practice_alignment`

4. **Detailed Entry Table**
   - Type: Table
   - Columns: `entry_date`, `user_name`, `project_name`, `client_name`, `duration_hours`, `billable`
   - Enable search and export

**Filters**:
- `week_start_date` (date range)
- `user_name` (dropdown)
- `project_name` (dropdown)
- `billable` (boolean)

---

### Dashboard 6: Resource Directory

**Dataset**: Active Resources

**Visualizations**:

1. **Resources by Practice**
   - Type: Pie Chart
   - Values: Count of `clockify_user_id`
   - Group: `practice_alignment`

2. **Resources by Location**
   - Type: Bar Chart
   - X-axis: `location`
   - Y-axis: Count

3. **Resource Activity Table**
   - Type: Table
   - Columns: `name`, `cloudelligent_title`, `practice_alignment`, `skill_area`, `location`, `hours_last_30_days`, `last_time_entry_date`
   - Conditional formatting: Red if `last_time_entry_date` > 7 days ago

4. **Skill Distribution**
   - Type: Word Cloud or Bar Chart
   - Values: `skill_area`

---

## Calculated Fields

Add these calculated fields to enhance your analyses:

### In Resource Utilization Dataset:

```
# Utilization Category
ifelse(
  utilization_percent >= 90, "High",
  ifelse(utilization_percent >= 70, "Normal", "Low")
)

# Hours Variance
actual_hours - weekly_capacity
```

### In Time Entries Dataset:

```
# Day of Week
extract("WD", entry_date)

# Is Weekend
ifelse(extract("WD", entry_date) in (1, 7), "Weekend", "Weekday")

# Hour Category
ifelse(
  duration_hours < 2, "Quick (<2h)",
  ifelse(duration_hours < 4, "Short (2-4h)",
  ifelse(duration_hours < 6, "Medium (4-6h)", "Long (6h+)"))
)
```

---

## SPICE Refresh Schedule

Set up automatic data refresh:

1. Go to each Dataset in QuickSight
2. Click **Schedule refresh**
3. Configure:
   - **Frequency**: Daily
   - **Time**: 6:00 AM (before business hours)
   - **Timezone**: Your timezone

---

## Sharing Dashboards

1. Open your dashboard
2. Click **Share** → **Share dashboard**
3. Options:
   - **Share with users**: Add specific QuickSight users
   - **Share with groups**: Add QuickSight groups
   - **Embed**: Get embed URL for external applications

---

## Best Practices

1. **Use Parameters**: Create parameters for common filters (date range, practice) and link across visuals
2. **Add Drill-downs**: Enable drill-through from summary to detail
3. **Set Default Filters**: Pre-filter to current week/month
4. **Use Conditional Formatting**: Highlight outliers and targets
5. **Add Insights**: Enable QuickSight Q for natural language queries

---

## Troubleshooting

### "No data" in visualizations
- Verify SPICE refresh completed successfully
- Check dataset preview for data
- Verify filters aren't excluding all data

### VPC connection errors
- Ensure security group allows QuickSight ENI to reach RDS on port 5432
- Verify VPC connection status is "AVAILABLE"

### Permission errors
- Verify IAM role has QuickSight permissions
- Check dataset permissions include your user
