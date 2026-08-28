"""QuickSight handler module.

Modes handled:
  - refresh_quicksight_only
  - create_quicksight_datasets
  - update_analysis_week_parameter  (also called internally by pipeline)

Internal helpers (also imported by pipeline.py and other modules):
  - get_all_dataset_ids
  - refresh_quicksight_datasets
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

import boto3


# ---------------------------------------------------------------------------
# Internal helpers — shared with pipeline and other handler modules
# ---------------------------------------------------------------------------

def get_all_dataset_ids(environment: str = 'production') -> List[str]:
    """Return all QuickSight SPICE dataset IDs to refresh.

    Includes both CloudFormation-managed datasets (suffixed with 'prod')
    and manually-created datasets (UUIDs or custom IDs).
    """
    return [
        # CloudFormation-managed datasets (use 'prod' suffix)
        'clockify-pod-performance-prod',
        'clockify-missing-time-submissions-prod',
        'time-compliance-current-week-prod',       # vw_weekly_compliance_report (all staff + status)
        # Manually-created datasets (fixed IDs)
        'clockify-missing-time-submissions',
        '7833b3c6-cec4-4956-b02a-2316198187cb',  # vw_contractor_weekly_trend
        'c84d2b1f-de9d-42cd-a389-e425a100c4d4',  # vw_contractor_time_summary
        '3bdc816d-4df6-4db7-b3e6-64e230f28f14',  # vw_forecast_over_40_hours
        '42098a5b-a94f-41d5-8300-396f1fec66bf',  # vw_forecast_summary
        'fc56c886-f0d2-4935-8b32-f0862325d3f0',  # vw_forecast_vs_actual
        '8900f5dc-687e-4d5b-9f91-5efd0cd1daed',  # ps_resource_forecasts
        'ps-project-status-view',                  # ps_project_status
        'data-freshness',                          # data_freshness
        'non-billable-analysis',                   # vw_non_billable_project_analysis
        'free-agent-availability',                 # vw_free_agent_availability
        # AI project health analysis datasets (created manually in QuickSight)
        'ai-ps-analysis-by-user',
        'ai-ps-analysis-by-project',
        'ai-mc-analysis-by-user',
        'ai-mc-analysis-by-project',
        # PS Profitability datasets
        'ps-profitability-2026',
        'ps-profitability-weekly-2026',
        'ps-profitability-chart',
        # MC V2 Audit datasets
        'mc-v2-audit-by-customer',
        'mc-v2-audit-by-phase',
        'mc-v2-audit-grid',
        # Project hours by assignment
        'project-hours-by-assignment',
        # Practice group performance (Project Hours tab)
        'practice-group-performance',
        # AI Forecast Analysis datasets
        'ai-forecast-analysis',
        'ai-forecast-summary',
        'pm-forecast-accuracy',
        # Escalations datasets
        'escalations-detail',
        'escalations-by-customer',
        # PS stage week-over-week trend
        'ps-stage-trend',
        # Productive utilization
        'productive-utilization',
        # Missing time history (weekly compliance + reasons)
        'missing-time-history',
        # Current-week compliance report (all users, compliant + non-compliant)
        'time-compliance-current-week',
        # Project time detail (last 4 weeks, filterable)
        'project-time-detail',
        # Customer status assignments (active Jira queue, resource per row)
        'customer-status-assignments',
        # Project directory (one row per resource per project)
        'project-directory',
        # COO dashboards — new datasets (2026-04)
        'kpi-weekly-snapshots-prod',
        'project-hours-summary-prod',
        'project-hours-current-week-prod',
        'category-hours-summary-prod',
        # MC Service Delivery
        'mc-ticket-activity',
    ]


def refresh_quicksight_datasets(dataset_ids: List[str]):
    """Trigger QuickSight SPICE refresh for datasets.

    Args:
        dataset_ids: List of QuickSight dataset IDs to refresh
    """
    if not dataset_ids:
        return

    quicksight = boto3.client('quicksight')
    account_id = boto3.client('sts').get_caller_identity()['Account']

    results = []
    for dataset_id in dataset_ids:
        try:
            ingestion_id = f"ingestion-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{dataset_id}"
            response = quicksight.create_ingestion(
                DataSetId=dataset_id,
                IngestionId=ingestion_id,
                AwsAccountId=account_id
            )
            results.append({
                'dataset_id': dataset_id,
                'status': 'triggered',
                'ingestion_id': ingestion_id
            })
            print(f"Triggered QuickSight refresh for dataset {dataset_id}")
        except Exception as e:
            print(f"Failed to refresh dataset {dataset_id}: {e}")
            results.append({
                'dataset_id': dataset_id,
                'status': 'failed',
                'error': str(e)
            })

    return results


def update_analysis_week_parameter(week_start_date):
    """Update pWeekStart parameter default in COO analysis to the new week."""
    try:
        import boto3 as _boto3
        qs = _boto3.client('quicksight', region_name='us-east-1')
        account_id = _boto3.client('sts').get_caller_identity()['Account']
        analysis_id = 'coo-operational-analysis-prod'

        resp = qs.describe_analysis_definition(AwsAccountId=account_id, AnalysisId=analysis_id)
        defn = resp['Definition']

        new_default = f'{week_start_date}T00:00:00Z'
        for p in defn.get('ParameterDeclarations', []):
            dtp = p.get('DateTimeParameterDeclaration', {})
            if dtp.get('Name') in ('pWeekStart', 'pWeekEnd'):  # handle both during rename transition
                dtp['DefaultValues']['StaticValues'] = [new_default]
                break

        name = qs.describe_analysis(AwsAccountId=account_id, AnalysisId=analysis_id)['Analysis']['Name']
        theme_arn = f'arn:aws:quicksight:us-east-1:{account_id}:theme/cloudelligent-brand-theme'
        qs.update_analysis(AwsAccountId=account_id, AnalysisId=analysis_id, Name=name,
            ThemeArn=theme_arn, Definition=defn)
        print(f'Updated COO analysis week parameter to {new_default}')
    except Exception as e:
        print(f'Failed to update analysis parameter (non-fatal): {e}')


# ---------------------------------------------------------------------------
# Public handler functions
# ---------------------------------------------------------------------------

def refresh_quicksight_only(event: dict, context: Any, secrets: dict) -> dict:
    """Trigger SPICE refresh for a list of datasets (or all if not specified)."""
    dataset_ids = event.get('quicksight_dataset_ids', [])
    results = refresh_quicksight_datasets(dataset_ids)
    return {
        'statusCode': 200,
        'body': json.dumps({'refreshed': results})
    }


def create_quicksight_datasets(event: dict, context: Any, secrets: dict) -> dict:
    """Create manually-managed QuickSight datasets."""
    qs = boto3.client('quicksight', region_name='us-east-1')
    account_id = boto3.client('sts').get_caller_identity()['Account']
    data_source_arn = f'arn:aws:quicksight:us-east-1:{account_id}:datasource/weekly-reporting-postgres'

    # Grant QuickSight admin users full dataset permissions
    # (list_users requires a permission the Lambda role doesn't have; use known ARNs)
    user_arns = [
        f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AWSAdministratorAccess_ed420cc098d02bac/chris.xenos',
        f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AdministratorAccess_2be0458d4fa377aa/tahir.nisar',
        f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AdministratorAccess_2be0458d4fa377aa/s.furlong',
        f'arn:aws:quicksight:us-east-1:{account_id}:user/default/AWSReservedSSO_AWSAdministratorAccess_ed420cc098d02bac/fatima',
    ]
    permissions = [
        {
            'Principal': arn,
            'Actions': [
                'quicksight:DescribeDataSet',
                'quicksight:DescribeDataSetPermissions',
                'quicksight:PassDataSet',
                'quicksight:DescribeIngestion',
                'quicksight:ListIngestions',
                'quicksight:UpdateDataSet',
                'quicksight:DeleteDataSet',
                'quicksight:CreateIngestion',
                'quicksight:CancelIngestion',
                'quicksight:UpdateDataSetPermissions',
            ]
        }
        for arn in user_arns
    ]

    datasets_to_create = [
        {
            'DataSetId': 'project-hours-by-assignment',
            'Name': 'Project Hours by Assignment',
            'ViewName': 'vw_project_hours_by_assignment',
            'InputColumns': [
                {'Name': 'week_start', 'Type': 'DATETIME'},
                {'Name': 'category', 'Type': 'STRING'},
                {'Name': 'customer_name', 'Type': 'STRING'},
                {'Name': 'pod', 'Type': 'STRING'},
                {'Name': 'clockify_client', 'Type': 'STRING'},
                {'Name': 'project_name', 'Type': 'STRING'},
                {'Name': 'resource_count', 'Type': 'INTEGER'},
                {'Name': 'total_hours', 'Type': 'DECIMAL'},
                {'Name': 'billable_hours', 'Type': 'DECIMAL'},
                {'Name': 'non_billable_hours', 'Type': 'DECIMAL'},
                {'Name': 'non_billable_productive_hours', 'Type': 'DECIMAL'},
            ],
        },
        {
            'DataSetId': 'project-time-detail',
            'Name': 'Project Time Detail',
            'ViewName': 'vw_project_time_detail',
            'InputColumns': [
                {'Name': 'clockify_entry_id', 'Type': 'STRING'},
                {'Name': 'entry_date', 'Type': 'DATETIME'},
                {'Name': 'week_start_date', 'Type': 'DATETIME'},
                {'Name': 'client_name', 'Type': 'STRING'},
                {'Name': 'project_name', 'Type': 'STRING'},
                {'Name': 'project_type', 'Type': 'STRING'},
                {'Name': 'pod_assignment', 'Type': 'STRING'},
                {'Name': 'task_name', 'Type': 'STRING'},
                {'Name': 'description', 'Type': 'STRING'},
                {'Name': 'user_name', 'Type': 'STRING'},
                {'Name': 'billable', 'Type': 'BIT'},
                {'Name': 'duration_hours', 'Type': 'DECIMAL'},
            ],
        },
        {
            'DataSetId': 'project-directory',
            'Name': 'Project Directory',
            'ViewName': 'vw_project_directory',
            'InputColumns': [
                {'Name': 'issue_key', 'Type': 'STRING'},
                {'Name': 'client_name', 'Type': 'STRING'},
                {'Name': 'project_name', 'Type': 'STRING'},
                {'Name': 'category', 'Type': 'STRING'},
                {'Name': 'project_type', 'Type': 'STRING'},
                {'Name': 'status', 'Type': 'STRING'},
                {'Name': 'status_category', 'Type': 'STRING'},
                {'Name': 'health', 'Type': 'STRING'},
                {'Name': 'actual_start_date', 'Type': 'DATETIME'},
                {'Name': 'expected_end_date', 'Type': 'DATETIME'},
                {'Name': 'revised_completion_date', 'Type': 'DATETIME'},
                {'Name': 'budget_hours', 'Type': 'DECIMAL'},
                {'Name': 'jira_board_link', 'Type': 'STRING'},
                {'Name': 'sow_link', 'Type': 'STRING'},
                {'Name': 'role', 'Type': 'STRING'},
                {'Name': 'resource_name', 'Type': 'STRING'},
            ],
        },
        {
            'DataSetId': 'customer-status-assignments',
            'Name': 'Customer Status Assignments',
            'ViewName': 'vw_customer_status_assignments',
            'InputColumns': [
                {'Name': 'issue_key', 'Type': 'STRING'},
                {'Name': 'client_name', 'Type': 'STRING'},
                {'Name': 'project_name', 'Type': 'STRING'},
                {'Name': 'category', 'Type': 'STRING'},
                {'Name': 'project_type', 'Type': 'STRING'},
                {'Name': 'status', 'Type': 'STRING'},
                {'Name': 'status_category', 'Type': 'STRING'},
                {'Name': 'priority', 'Type': 'STRING'},
                {'Name': 'actual_start_date', 'Type': 'DATETIME'},
                {'Name': 'expected_end_date', 'Type': 'DATETIME'},
                {'Name': 'revised_completion_date', 'Type': 'DATETIME'},
                {'Name': 'assignment_role', 'Type': 'STRING'},
                {'Name': 'resource_name', 'Type': 'STRING'},
            ],
        },
    ]

    results = []
    for ds in datasets_to_create:
        try:
            qs.create_data_set(
                AwsAccountId=account_id,
                DataSetId=ds['DataSetId'],
                Name=ds['Name'],
                ImportMode='SPICE',
                PhysicalTableMap={
                    ds['DataSetId']: {
                        'RelationalTable': {
                            'DataSourceArn': data_source_arn,
                            'Schema': 'public',
                            'Name': ds['ViewName'],
                            'InputColumns': ds['InputColumns'],
                        }
                    }
                },
                LogicalTableMap={
                    f"{ds['DataSetId']}-logical": {
                        'Alias': ds['Name'],
                        'Source': {'PhysicalTableId': ds['DataSetId']},
                    }
                },
                Permissions=permissions,
            )
            results.append({'dataset_id': ds['DataSetId'], 'status': 'created'})
            print(f"Created QuickSight dataset: {ds['DataSetId']}")
        except qs.exceptions.ResourceExistsException:
            results.append({'dataset_id': ds['DataSetId'], 'status': 'already_exists'})
            print(f"Dataset already exists: {ds['DataSetId']}")
        except Exception as e:
            results.append({'dataset_id': ds['DataSetId'], 'status': 'error', 'error': str(e)})
            print(f"Error creating dataset {ds['DataSetId']}: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps({'datasets': results})
    }
