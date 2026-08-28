# Pod Performance Analysis Dashboard

This dashboard provides comprehensive analysis of pod performance with trend indicators, comparing last week's performance against 30-day and 90-day averages for Free Agent, Alpha, Bravo, SurePoint, and A2Z pods.

## Overview

The Pod Performance Dashboard answers key questions:
- How did each pod perform last week compared to historical averages?
- Which pods are trending upward or downward?
- Are there performance outliers that need attention?
- What's the overall team capacity and utilization?

## Key Metrics

### Primary Metrics
- **Last Week Hours**: Total hours logged by each pod in the most recent complete week
- **30-Day Average**: Average weekly hours over the past 30 days
- **90-Day Average**: Average weekly hours over the past 90 days
- **Percentage Change**: Performance variance against historical averages
- **Trend Indicator**: Upward, Downward, or Stable trend based on week-over-week comparison

### Secondary Metrics
- **Billable Percentage**: Percentage of billable vs non-billable hours
- **Resource Count**: Number of active resources in each pod
- **Performance Rating**: Above Average, Average, or Below Average classification

## Dashboard Components

### 1. Pod Performance Summary Table
**Purpose**: Comprehensive overview of all pod metrics in a single view

**Columns**:
- Pod Name
- Last Week Hours
- 30-Day Average
- 90-Day Average
- % Change vs 30-Day
- Weekly Trend
- Performance Rating

**Key Features**:
- Color-coded performance indicators
- Sortable columns for easy analysis
- Trend arrows for quick visual assessment

### 2. Hours Comparison Chart
**Purpose**: Visual comparison of current performance vs historical averages

**Chart Type**: Grouped Bar Chart
**Data**: 
- Last Week Hours (blue bars)
- 30-Day Average (orange bars)
- 90-Day Average (gray bars)

**Benefits**:
- Easy visual comparison across pods
- Identifies over/under-performing pods at a glance
- Shows relative pod sizes

### 3. Individual Pod KPIs
**Purpose**: Focused metrics for each major pod

**KPI Cards for**:
- Free Agent
- Alpha
- Bravo
- SurePoint
- A2Z

**Each KPI Shows**:
- Current week hours
- Target (30-day average)
- Percentage variance
- Color-coded performance indicator

### 4. Trend Indicators Gauge
**Purpose**: Visual representation of trend momentum

**Gauge Metrics**:
- 30-day trend percentage
- 90-day trend percentage
- Performance momentum indicator

## Data Source

### Database View: `vw_pod_performance_analysis`

This view automatically calculates:
- Weekly aggregations by pod
- Rolling averages for 30 and 90 days
- Trend calculations
- Performance classifications

**Refresh Schedule**: Updates automatically when time entry data is imported

## Using the Dashboard

### Daily Monitoring
1. **Check KPI Cards** for immediate pod status
2. **Review Trend Indicators** for momentum assessment
3. **Identify Outliers** using the performance table

### Weekly Analysis
1. **Compare Current vs Historical** using the bar chart
2. **Analyze Trend Patterns** across multiple weeks
3. **Generate Action Items** for underperforming pods

### Monthly Reviews
1. **Track Long-term Trends** using 90-day comparisons
2. **Assess Pod Effectiveness** and resource allocation
3. **Plan Capacity Adjustments** based on performance data

## Interpretation Guide

### Performance Indicators

**🟢 Above Average (Green)**
- Last week hours > 110% of 30-day average
- Strong performance, sustainable practices
- Consider if temporary spike or new normal

**🟡 Average (Yellow)**
- Last week hours within 90-110% of 30-day average
- Normal performance range
- Monitor for emerging trends

**🔴 Below Average (Red)**
- Last week hours < 90% of 30-day average
- Potential capacity or allocation issues
- Requires investigation and action

### Trend Indicators

**📈 Upward Trend**
- Current week > previous week
- Positive momentum
- Monitor sustainability

**📉 Downward Trend**
- Current week < previous week
- Declining performance
- Investigate root causes

**➡️ Stable Trend**
- Current week ≈ previous week
- Consistent performance
- Maintain current practices

### Alert Thresholds

**Critical Attention Required**:
- Performance < 80% of 30-day average
- Downward trend for 2+ consecutive weeks
- Zero hours logged (inactive pod)

**Monitor Closely**:
- Performance 80-90% of 30-day average
- Volatile week-to-week changes (>25% variance)
- Consistently low billable percentages

## Action Items by Performance Level

### Above Average Performance
- **Investigate**: Is this sustainable or a temporary spike?
- **Document**: What practices led to strong performance?
- **Scale**: Can successful practices be applied to other pods?
- **Capacity**: Ensure resources aren't overutilized

### Below Average Performance
- **Root Cause Analysis**: Why are hours down?
  - Resource availability issues?
  - Project delays or cancellations?
  - Capacity planning problems?
- **Resource Review**: Are team members properly allocated?
- **Project Pipeline**: Is there sufficient work available?
- **Support Needed**: What assistance can improve performance?

### Trend Analysis
- **Upward Trends**: Validate sustainability and resource health
- **Downward Trends**: Immediate investigation and intervention
- **Stable Trends**: Assess if performance level is optimal

## Automated Reporting

### Command Line Report
Generate instant pod performance reports:

```bash
# Generate detailed console report
python scripts/pod_performance_report.py

# Export to CSV for further analysis
python scripts/pod_performance_report.py --export-csv

# Quiet mode for automated scripts
python scripts/pod_performance_report.py --quiet --export-csv
```

### Scheduled Reports
Integrate with your existing automation:

```bash
# Add to weekly cron job (Monday mornings)
0 8 * * 1 cd /path/to/weekly-reporting && python scripts/pod_performance_report.py --export-csv
```

## Integration with Other Dashboards

### Executive Dashboard
- Pod performance KPIs feed into overall organizational metrics
- Trend indicators inform capacity planning decisions
- Performance outliers trigger deeper analysis

### Resource Management Dashboard
- Individual resource performance within pods
- Utilization rates by pod assignment
- Skill distribution across pods

### Project Dashboard
- Project allocation impact on pod performance
- Client work distribution across pods
- Billable vs non-billable work by pod

## Troubleshooting

### No Data Showing
1. **Check Data Import**: Ensure time entries are being imported
2. **Verify Pod Assignments**: Confirm users have pod_assignment values
3. **Database Views**: Run `python src/database/apply_views.py`
4. **Date Range**: Ensure there's data in the last 90 days

### Incorrect Trends
1. **Data Completeness**: Verify all weeks have complete data
2. **Weekend Entries**: Check if weekend work affects calculations
3. **Holiday Periods**: Consider impact of holidays on averages
4. **Pod Changes**: Account for recent pod reassignments

### Performance Issues
1. **SPICE Refresh**: Ensure QuickSight datasets are refreshing
2. **Query Optimization**: Database view performance
3. **Filter Usage**: Apply appropriate date and pod filters

## Best Practices

### Dashboard Usage
- **Daily Glance**: Quick KPI review each morning
- **Weekly Deep Dive**: Comprehensive analysis every Monday
- **Monthly Trends**: Long-term pattern analysis
- **Quarterly Reviews**: Strategic pod effectiveness assessment

### Data Quality
- **Consistent Pod Assignments**: Ensure all resources have proper pod assignments
- **Complete Time Entry**: Encourage comprehensive time tracking
- **Regular Validation**: Spot-check data accuracy monthly

### Action Planning
- **Document Insights**: Keep notes on performance patterns
- **Track Interventions**: Monitor impact of corrective actions
- **Share Learnings**: Communicate successful practices across pods
- **Continuous Improvement**: Regularly refine metrics and thresholds

## Future Enhancements

### Planned Features
- **Predictive Analytics**: Forecast pod performance trends
- **Resource Optimization**: Suggest optimal pod assignments
- **Comparative Analysis**: Benchmark against industry standards
- **Alert System**: Automated notifications for performance issues

### Custom Metrics
- **Pod Efficiency Ratios**: Hours per deliverable by pod
- **Client Satisfaction Correlation**: Performance vs client feedback
- **Revenue per Pod**: Financial performance metrics
- **Skill Utilization**: Match skills to project requirements

## Support and Feedback

For questions, issues, or enhancement requests:
1. **Technical Issues**: Check troubleshooting section first
2. **Data Questions**: Verify with source systems (Clockify)
3. **Feature Requests**: Document business case and impact
4. **Training Needs**: Schedule dashboard walkthrough sessions