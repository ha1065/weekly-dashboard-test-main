#!/bin/bash
# Create all missing QuickSight SPICE datasets from PostgreSQL views
# Uses the existing data source: 2a808ee0-ff4e-40a1-af7c-a968d929b59b

ACCOUNT_ID="604775478093"
DATA_SOURCE_ARN="arn:aws:quicksight:us-east-1:604775478093:datasource/2a808ee0-ff4e-40a1-af7c-a968d929b59b"
PRINCIPAL="arn:aws:quicksight:us-east-1:604775478093:user/default/AWSReservedSSO_AdministratorAccess_9cc259e8fcbce348/haider.ahmed"
REGION="us-east-1"

# Dataset ID -> View Name mapping
declare -A DATASETS
DATASETS["clockify-time-entries-prod"]="vw_weekly_time_summary"
DATASETS["clockify-resource-utilization-prod"]="vw_resource_utilization"
DATASETS["clockify-weekly-summary-prod"]="vw_weekly_time_summary"
DATASETS["clockify-project-tracking-prod"]="vw_project_time_tracking"
DATASETS["clockify-client-summary-prod"]="vw_client_time_summary"
DATASETS["clockify-practice-performance-prod"]="vw_practice_alignment_performance_12w"
DATASETS["clockify-monthly-summary-prod"]="vw_monthly_summary"
DATASETS["clockify-active-resources-prod"]="vw_active_resources"
DATASETS["clockify-pod-performance-prod"]="vw_pod_performance_analysis"
DATASETS["clockify-skill-area-summary-prod"]="vw_skill_area_summary"
DATASETS["clockify-daily-activity-trend-prod"]="vw_daily_activity_trend"
DATASETS["clockify-import-activity-prod"]="vw_import_activity"
DATASETS["clockify-missing-time-submissions-prod"]="vw_missing_time_submissions"
DATASETS["data-freshness"]="vw_data_freshness"
DATASETS["ps-project-status-view"]="vw_ps_project_status"

# Display name mapping
declare -A DISPLAY_NAMES
DISPLAY_NAMES["clockify-time-entries-prod"]="Time Entries"
DISPLAY_NAMES["clockify-resource-utilization-prod"]="Resource Utilization"
DISPLAY_NAMES["clockify-weekly-summary-prod"]="Weekly Summary"
DISPLAY_NAMES["clockify-project-tracking-prod"]="Project Tracking"
DISPLAY_NAMES["clockify-client-summary-prod"]="Client Summary"
DISPLAY_NAMES["clockify-practice-performance-prod"]="Practice Performance"
DISPLAY_NAMES["clockify-monthly-summary-prod"]="Monthly Summary"
DISPLAY_NAMES["clockify-active-resources-prod"]="Active Resources"
DISPLAY_NAMES["clockify-pod-performance-prod"]="Pod Performance"
DISPLAY_NAMES["clockify-skill-area-summary-prod"]="Skill Area Summary"
DISPLAY_NAMES["clockify-daily-activity-trend-prod"]="Daily Activity Trend"
DISPLAY_NAMES["clockify-import-activity-prod"]="Import Activity"
DISPLAY_NAMES["clockify-missing-time-submissions-prod"]="Missing Time Submissions"
DISPLAY_NAMES["data-freshness"]="Data Freshness"
DISPLAY_NAMES["ps-project-status-view"]="PS Project Status"

CREATED=0
FAILED=0

for DATASET_ID in "${!DATASETS[@]}"; do
    VIEW_NAME="${DATASETS[$DATASET_ID]}"
    DISPLAY_NAME="${DISPLAY_NAMES[$DATASET_ID]}"
    
    echo "Creating dataset: $DATASET_ID -> $VIEW_NAME ($DISPLAY_NAME)"
    
    RESULT=$(aws quicksight create-data-set \
        --aws-account-id "$ACCOUNT_ID" \
        --data-set-id "$DATASET_ID" \
        --name "$DISPLAY_NAME" \
        --import-mode "SPICE" \
        --physical-table-map "{
            \"physical-table-1\": {
                \"RelationalTable\": {
                    \"DataSourceArn\": \"$DATA_SOURCE_ARN\",
                    \"Schema\": \"public\",
                    \"Name\": \"$VIEW_NAME\",
                    \"InputColumns\": [{\"Name\": \"_placeholder\", \"Type\": \"STRING\"}]
                }
            }
        }" \
        --permissions "[{
            \"Principal\": \"$PRINCIPAL\",
            \"Actions\": [
                \"quicksight:DeleteDataSet\",
                \"quicksight:UpdateDataSetPermissions\",
                \"quicksight:PutDataSetRefreshProperties\",
                \"quicksight:CreateRefreshSchedule\",
                \"quicksight:CancelIngestion\",
                \"quicksight:PassDataSet\",
                \"quicksight:UpdateRefreshSchedule\",
                \"quicksight:DeleteRefreshSchedule\",
                \"quicksight:ListRefreshSchedules\",
                \"quicksight:DescribeDataSetRefreshProperties\",
                \"quicksight:DescribeDataSet\",
                \"quicksight:CreateIngestion\",
                \"quicksight:DescribeRefreshSchedule\",
                \"quicksight:ListIngestions\",
                \"quicksight:UpdateDataSet\",
                \"quicksight:DescribeDataSetPermissions\",
                \"quicksight:DeleteDataSetRefreshProperties\",
                \"quicksight:DescribeIngestion\"
            ]
        }]" \
        --region "$REGION" 2>&1)
    
    if echo "$RESULT" | grep -q "\"Status\": 201\|\"CreationStatus\": \"CREATION_SUCCESSFUL\""; then
        echo "  ✅ Created successfully"
        ((CREATED++))
    else
        echo "  ❌ Failed: $RESULT"
        ((FAILED++))
    fi
    echo ""
done

echo "================================"
echo "Results: $CREATED created, $FAILED failed"
echo "================================"
