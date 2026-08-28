#!/usr/bin/env python3
"""
Script to refresh QuickSight datasets for Clockify reporting.
This ensures SPICE data is up-to-date with the latest database information.
"""

import boto3
import argparse
import time
import sys
from datetime import datetime


def get_quicksight_client(profile_name=None, region='us-east-1'):
    """Initialize QuickSight client."""
    session = boto3.Session(profile_name=profile_name, region_name=region)
    return session.client('quicksight')


def get_datasets_for_environment(environment):
    """Get list of dataset IDs for the specified environment.

    These are the 17 import-critical datasets as defined in
    docs/runbooks/spice-refresh-failure.md. IDs are fixed (not
    environment-templated) because QuickSight dataset IDs were created
    with explicit names rather than per-environment suffixes.

    Non-critical datasets (clockify-pod-performance-prod,
    clockify-skill-area-summary-prod, clockify-daily-activity-trend-prod,
    clockify-import-activity-prod) are intentionally excluded — their
    underlying views do not exist in production and they are not used by
    any active dashboard sheet.
    """
    # These dataset IDs are fixed regardless of environment.
    # All active dashboards depend on exactly these 17 datasets.
    _ = environment  # kept for CLI compatibility; IDs are not environment-templated
    return [
        'kpi-weekly-snapshots-prod',
        'ps-project-status-view',
        'productive-utilization',
        'clockify-missing-time-submissions-prod',
        'clockify-missing-time-submissions',
        'escalations-detail',
        'ps-stage-trend',
        'project-hours-summary-prod',
        'project-hours-current-week-prod',
        'mc-ticket-activity',
        'mc-projects-at-risk',
        'ps-projects-at-risk',
        'time-compliance-current-week',
        'missing-time-history',
        # COO Operational Dashboard — added 2026-07-07
        'resource-capacity-plan',
        'utilization-history',
        'time-compliance-history',
    ]


def create_ingestion(client, aws_account_id, dataset_id):
    """Create a new ingestion for the specified dataset."""
    ingestion_id = f"refresh-{int(time.time())}"
    
    try:
        response = client.create_ingestion(
            DataSetId=dataset_id,
            IngestionId=ingestion_id,
            AwsAccountId=aws_account_id
        )
        
        print(f"✅ Started ingestion for dataset {dataset_id}")
        print(f"   Ingestion ID: {ingestion_id}")
        return ingestion_id, response['Status']
        
    except client.exceptions.ResourceExistsException:
        print(f"⚠️  Ingestion already in progress for dataset {dataset_id}")
        return None, 'RUNNING'
        
    except Exception as e:
        print(f"❌ Failed to start ingestion for dataset {dataset_id}: {str(e)}")
        return None, 'FAILED'


def check_ingestion_status(client, aws_account_id, dataset_id, ingestion_id):
    """Check the status of an ingestion."""
    try:
        response = client.describe_ingestion(
            DataSetId=dataset_id,
            IngestionId=ingestion_id,
            AwsAccountId=aws_account_id
        )
        
        ingestion = response['Ingestion']
        return ingestion['IngestionStatus'], ingestion.get('ErrorInfo', {})
        
    except Exception as e:
        print(f"❌ Failed to check ingestion status for {dataset_id}: {str(e)}")
        return 'FAILED', {'ErrorMessage': str(e)}


def wait_for_ingestions(client, aws_account_id, ingestions, timeout_minutes=30):
    """Wait for all ingestions to complete."""
    print(f"\n⏳ Waiting for ingestions to complete (timeout: {timeout_minutes} minutes)...")
    
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    
    while ingestions:
        time.sleep(10)  # Check every 10 seconds
        
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            print(f"⏰ Timeout reached after {timeout_minutes} minutes")
            break
        
        completed_ingestions = []
        
        for dataset_id, ingestion_id in ingestions.items():
            if ingestion_id is None:
                completed_ingestions.append(dataset_id)
                continue
                
            status, error_info = check_ingestion_status(
                client, aws_account_id, dataset_id, ingestion_id
            )
            
            if status == 'COMPLETED':
                print(f"✅ Dataset {dataset_id} refresh completed successfully")
                completed_ingestions.append(dataset_id)
                
            elif status == 'FAILED':
                error_msg = error_info.get('ErrorMessage', 'Unknown error')
                print(f"❌ Dataset {dataset_id} refresh failed: {error_msg}")
                completed_ingestions.append(dataset_id)
                
            elif status == 'CANCELLED':
                print(f"⚠️  Dataset {dataset_id} refresh was cancelled")
                completed_ingestions.append(dataset_id)
        
        # Remove completed ingestions
        for dataset_id in completed_ingestions:
            ingestions.pop(dataset_id, None)
        
        if ingestions:
            remaining = len(ingestions)
            elapsed = int((time.time() - start_time) / 60)
            print(f"   {remaining} ingestions still running... (elapsed: {elapsed}m)")


def main():
    parser = argparse.ArgumentParser(
        description='Refresh QuickSight datasets for Clockify reporting'
    )
    parser.add_argument(
        '--environment', 
        choices=['dev', 'staging', 'prod'], 
        default='prod',
        help='Environment to refresh datasets for'
    )
    parser.add_argument(
        '--aws-account-id',
        required=True,
        help='AWS Account ID'
    )
    parser.add_argument(
        '--profile',
        default=None,
        help='AWS CLI profile name (optional)'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Timeout in minutes for waiting for ingestions to complete'
    )
    parser.add_argument(
        '--dataset',
        help='Refresh only a specific dataset (optional)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"🔄 QuickSight Dataset Refresh - {args.environment.upper()}")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"AWS Account ID: {args.aws_account_id}")
    print(f"Environment: {args.environment}")
    print(f"Region: {args.region}")
    
    # Initialize QuickSight client
    try:
        client = get_quicksight_client(profile_name=args.profile, region=args.region)
        print("✅ QuickSight client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize QuickSight client: {str(e)}")
        sys.exit(1)
    
    # Get datasets to refresh
    if args.dataset:
        datasets = [args.dataset]
        print(f"📊 Refreshing single dataset: {args.dataset}")
    else:
        datasets = get_datasets_for_environment(args.environment)
        print(f"📊 Refreshing {len(datasets)} datasets")
    
    # Start ingestions
    print("\n🚀 Starting dataset ingestions...")
    ingestions = {}
    
    for dataset_id in datasets:
        ingestion_id, status = create_ingestion(client, args.aws_account_id, dataset_id)
        if status not in ['FAILED']:
            ingestions[dataset_id] = ingestion_id
    
    if not ingestions:
        print("❌ No ingestions were started successfully")
        sys.exit(1)
    
    # Wait for completion
    wait_for_ingestions(client, args.aws_account_id, ingestions, args.timeout)
    
    print("\n" + "=" * 60)
    print("🎉 Dataset refresh process completed!")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()