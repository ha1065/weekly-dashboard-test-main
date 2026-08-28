#!/usr/bin/env python3
"""Scheduled import script for automated weekly data pulls from Clockify.

This script is designed to be run by a scheduler (cron, AWS EventBridge, etc.)
to automatically pull incremental data from Clockify on a weekly basis.

Usage:
    python src/scheduled_import.py [--mode MODE]

Modes:
    incremental (default) - Import only new data since last successful import
    weekly - Import last 1 week of data
    full - Import last 52 weeks (1 year) of data
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.integrations.import_clockify_data import run_import, run_incremental_import, run_full_import
from src.database.config import SessionLocal
from sqlalchemy import func, text


def send_notification(success: bool, message: str):
    """Send notification about import status.

    In production, this could send to:
    - Email (SES)
    - Slack webhook
    - SNS topic
    - CloudWatch logs
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ SUCCESS" if success else "❌ FAILED"

    log_message = f"""
    ================================================================================
    Scheduled Clockify Import - {status}
    ================================================================================
    Timestamp: {timestamp}
    Message: {message}
    ================================================================================
    """

    print(log_message)

    # TODO: Add actual notification logic here (email, Slack, SNS, etc.)
    # Example:
    # if not success:
    #     send_slack_alert(message)
    #     send_email_alert(message)


def get_import_stats():
    """Get statistics about the import."""
    db = SessionLocal()
    try:
        stats = {}

        # Get counts
        stats['total_users'] = db.execute(text("SELECT COUNT(*) FROM clockify_users")).scalar()
        stats['active_users'] = db.execute(text("SELECT COUNT(*) FROM clockify_users WHERE status = 'active'")).scalar()
        stats['total_projects'] = db.execute(text("SELECT COUNT(*) FROM clockify_projects")).scalar()
        stats['total_entries'] = db.execute(text("SELECT COUNT(*) FROM clockify_detailed_time_entries")).scalar()

        # Get last import info
        last_import = db.execute(text("""
            SELECT import_type, import_category, completed_at, records_imported, records_updated
            FROM import_logs
            WHERE status = 'success'
            ORDER BY completed_at DESC
            LIMIT 1
        """)).fetchone()

        if last_import:
            stats['last_import_type'] = last_import[0]
            stats['last_import_category'] = last_import[1]
            stats['last_import_time'] = last_import[2]
            stats['last_imported'] = last_import[3]
            stats['last_updated'] = last_import[4]

        return stats
    finally:
        db.close()


def main():
    """Main entry point for scheduled imports."""
    parser = argparse.ArgumentParser(description='Scheduled Clockify data import')
    parser.add_argument(
        '--mode',
        choices=['incremental', 'weekly', 'full'],
        default='incremental',
        help='Import mode: incremental (default), weekly, or full'
    )
    parser.add_argument(
        '--notify',
        action='store_true',
        help='Send notifications on completion'
    )

    args = parser.parse_args()

    print(f"\n🕐 Starting scheduled import at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {args.mode}")

    try:
        # Run import based on mode
        if args.mode == 'incremental':
            run_incremental_import()
        elif args.mode == 'weekly':
            run_import(weeks_back=1, incremental=False)
        elif args.mode == 'full':
            run_full_import()

        # Get statistics
        stats = get_import_stats()

        message = f"""
        Import completed successfully!

        Database Statistics:
        - Total Users: {stats.get('total_users', 'N/A')}
        - Active Users: {stats.get('active_users', 'N/A')}
        - Total Projects: {stats.get('total_projects', 'N/A')}
        - Total Time Entries: {stats.get('total_entries', 'N/A')}

        Last Import:
        - Type: {stats.get('last_import_type', 'N/A')}
        - Category: {stats.get('last_import_category', 'N/A')}
        - Records Imported: {stats.get('last_imported', 'N/A')}
        - Records Updated: {stats.get('last_updated', 'N/A')}
        """

        if args.notify:
            send_notification(True, message)
        else:
            print(message)

        return 0

    except Exception as e:
        error_message = f"Import failed: {str(e)}"

        if args.notify:
            send_notification(False, error_message)
        else:
            print(f"\n❌ {error_message}")

        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
