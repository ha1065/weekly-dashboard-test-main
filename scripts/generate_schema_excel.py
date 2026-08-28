#!/usr/bin/env python3
"""Generate database schema documentation as Excel file from source files."""

import pandas as pd
from pathlib import Path

# Project root
project_root = Path(__file__).parent.parent


def get_table_definitions():
    """Define tables based on SQLAlchemy models."""
    tables = {
        'clockify_users': [
            {'Column': 'user_id', 'Data Type': 'INTEGER', 'Nullable': 'NO', 'Key': 'PRIMARY KEY', 'Description': 'Auto-generated primary key'},
            {'Column': 'clockify_user_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': 'UNIQUE', 'Description': 'Clockify user identifier'},
            {'Column': 'name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'NO', 'Key': '', 'Description': 'User full name'},
            {'Column': 'email', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'User email address'},
            {'Column': 'daily_capacity', 'Data Type': 'FLOAT', 'Nullable': 'YES', 'Key': '', 'Description': 'Daily working hours capacity (default 8.0)'},
            {'Column': 'practice_alignment', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Practice alignment (e.g., Cloud, DevOps)'},
            {'Column': 'skill_area', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Primary skill area'},
            {'Column': 'pod_assignment', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Assigned pod (e.g., Alpha, Bravo)'},
            {'Column': 'cloudelligent_title', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Company job title'},
            {'Column': 'location', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Work location'},
            {'Column': 'employment_designation', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Employment type'},
            {'Column': 'status', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'User status (active/inactive)'},
            {'Column': 'synced_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Last sync from Clockify'},
            {'Column': 'created_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record creation timestamp'},
            {'Column': 'updated_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record update timestamp'},
        ],
        'clockify_projects': [
            {'Column': 'project_id', 'Data Type': 'INTEGER', 'Nullable': 'NO', 'Key': 'PRIMARY KEY', 'Description': 'Auto-generated primary key'},
            {'Column': 'clockify_project_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': 'UNIQUE', 'Description': 'Clockify project identifier'},
            {'Column': 'name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'NO', 'Key': '', 'Description': 'Project name'},
            {'Column': 'client_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Clockify client identifier'},
            {'Column': 'client_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'Client name'},
            {'Column': 'color', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Project color in Clockify'},
            {'Column': 'billable', 'Data Type': 'BOOLEAN', 'Nullable': 'YES', 'Key': '', 'Description': 'Whether project is billable'},
            {'Column': 'archived', 'Data Type': 'BOOLEAN', 'Nullable': 'YES', 'Key': '', 'Description': 'Whether project is archived'},
            {'Column': 'due_date', 'Data Type': 'DATE', 'Nullable': 'YES', 'Key': '', 'Description': 'Project due date'},
            {'Column': 'project_type', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Type of project'},
            {'Column': 'professional_services_type', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'PS type classification'},
            {'Column': 'professional_services_phase', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'PS phase'},
            {'Column': 'synced_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Last sync from Clockify'},
            {'Column': 'created_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record creation timestamp'},
            {'Column': 'updated_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record update timestamp'},
        ],
        'clockify_detailed_time_entries': [
            {'Column': 'entry_id', 'Data Type': 'INTEGER', 'Nullable': 'NO', 'Key': 'PRIMARY KEY', 'Description': 'Auto-generated primary key'},
            {'Column': 'clockify_entry_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': 'UNIQUE', 'Description': 'Clockify entry identifier'},
            {'Column': 'clockify_user_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': '', 'Description': 'Reference to user'},
            {'Column': 'user_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'NO', 'Key': '', 'Description': 'User name (denormalized)'},
            {'Column': 'practice_alignment', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Practice alignment at time of entry'},
            {'Column': 'skill_area', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Skill area at time of entry'},
            {'Column': 'pod_assignment', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Pod assignment at time of entry'},
            {'Column': 'cloudelligent_title', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Job title at time of entry'},
            {'Column': 'location', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Location at time of entry'},
            {'Column': 'employment_designation', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Employment type at time of entry'},
            {'Column': 'clockify_project_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Reference to project'},
            {'Column': 'project_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'Project name (denormalized)'},
            {'Column': 'client_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'Client name (denormalized)'},
            {'Column': 'description', 'Data Type': 'TEXT', 'Nullable': 'YES', 'Key': '', 'Description': 'Time entry description'},
            {'Column': 'billable', 'Data Type': 'BOOLEAN', 'Nullable': 'YES', 'Key': '', 'Description': 'Whether entry is billable'},
            {'Column': 'duration_hours', 'Data Type': 'FLOAT', 'Nullable': 'YES', 'Key': '', 'Description': 'Duration in hours'},
            {'Column': 'start_time', 'Data Type': 'TIMESTAMP', 'Nullable': 'NO', 'Key': '', 'Description': 'Entry start time'},
            {'Column': 'end_time', 'Data Type': 'TIMESTAMP', 'Nullable': 'NO', 'Key': '', 'Description': 'Entry end time'},
            {'Column': 'entry_date', 'Data Type': 'DATE', 'Nullable': 'YES', 'Key': '', 'Description': 'Date of entry (for partitioning)'},
            {'Column': 'synced_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Last sync from Clockify'},
            {'Column': 'created_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record creation timestamp'},
        ],
        'user_skills': [
            {'Column': 'skill_id', 'Data Type': 'INTEGER', 'Nullable': 'NO', 'Key': 'PRIMARY KEY', 'Description': 'Auto-generated primary key'},
            {'Column': 'clockify_user_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': '', 'Description': 'Reference to user'},
            {'Column': 'user_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'NO', 'Key': '', 'Description': 'User name (denormalized)'},
            {'Column': 'skill_category', 'Data Type': 'VARCHAR(100)', 'Nullable': 'NO', 'Key': '', 'Description': 'Category of skill'},
            {'Column': 'skill_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'NO', 'Key': '', 'Description': 'Name of skill'},
            {'Column': 'proficiency_level', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Proficiency level'},
            {'Column': 'years_experience', 'Data Type': 'FLOAT', 'Nullable': 'YES', 'Key': '', 'Description': 'Years of experience'},
            {'Column': 'last_used_date', 'Data Type': 'DATE', 'Nullable': 'YES', 'Key': '', 'Description': 'Last used date'},
            {'Column': 'certification_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'Related certification'},
            {'Column': 'certification_date', 'Data Type': 'DATE', 'Nullable': 'YES', 'Key': '', 'Description': 'Certification date'},
            {'Column': 'certification_expiry', 'Data Type': 'DATE', 'Nullable': 'YES', 'Key': '', 'Description': 'Certification expiry'},
            {'Column': 'added_by', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'Who added the skill'},
            {'Column': 'created_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record creation timestamp'},
            {'Column': 'updated_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record update timestamp'},
        ],
        'ps_resource_forecasts': [
            {'Column': 'forecast_id', 'Data Type': 'INTEGER', 'Nullable': 'NO', 'Key': 'PRIMARY KEY', 'Description': 'Auto-generated primary key'},
            {'Column': 'week_start_date', 'Data Type': 'DATE', 'Nullable': 'NO', 'Key': '', 'Description': 'Forecast week start'},
            {'Column': 'week_end_date', 'Data Type': 'DATE', 'Nullable': 'NO', 'Key': '', 'Description': 'Forecast week end'},
            {'Column': 'clockify_user_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': '', 'Description': 'Reference to user'},
            {'Column': 'user_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'NO', 'Key': '', 'Description': 'User name'},
            {'Column': 'location', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'User location'},
            {'Column': 'project_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'NO', 'Key': '', 'Description': 'Project name'},
            {'Column': 'clockify_project_id', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Reference to project'},
            {'Column': 'client_name', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'Client name'},
            {'Column': 'practice_area', 'Data Type': 'VARCHAR(100)', 'Nullable': 'YES', 'Key': '', 'Description': 'Practice area'},
            {'Column': 'forecasted_hours_per_week', 'Data Type': 'FLOAT', 'Nullable': 'NO', 'Key': '', 'Description': 'Forecasted hours'},
            {'Column': 'notes', 'Data Type': 'TEXT', 'Nullable': 'YES', 'Key': '', 'Description': 'Additional notes'},
            {'Column': 'created_by', 'Data Type': 'VARCHAR(255)', 'Nullable': 'YES', 'Key': '', 'Description': 'Who created the forecast'},
            {'Column': 'created_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record creation timestamp'},
            {'Column': 'updated_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Record update timestamp'},
        ],
        'import_logs': [
            {'Column': 'log_id', 'Data Type': 'INTEGER', 'Nullable': 'NO', 'Key': 'PRIMARY KEY', 'Description': 'Auto-generated primary key'},
            {'Column': 'import_type', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': '', 'Description': 'Type: full, incremental'},
            {'Column': 'import_category', 'Data Type': 'VARCHAR(50)', 'Nullable': 'NO', 'Key': '', 'Description': 'Category: users, projects, time_entries'},
            {'Column': 'start_date', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Import date range start'},
            {'Column': 'end_date', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Import date range end'},
            {'Column': 'records_imported', 'Data Type': 'INTEGER', 'Nullable': 'YES', 'Key': '', 'Description': 'Number of records imported'},
            {'Column': 'records_updated', 'Data Type': 'INTEGER', 'Nullable': 'YES', 'Key': '', 'Description': 'Number of records updated'},
            {'Column': 'records_skipped', 'Data Type': 'INTEGER', 'Nullable': 'YES', 'Key': '', 'Description': 'Number of records skipped'},
            {'Column': 'status', 'Data Type': 'VARCHAR(50)', 'Nullable': 'YES', 'Key': '', 'Description': 'Status: success, failed, partial'},
            {'Column': 'error_message', 'Data Type': 'TEXT', 'Nullable': 'YES', 'Key': '', 'Description': 'Error details if failed'},
            {'Column': 'started_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Import start time'},
            {'Column': 'completed_at', 'Data Type': 'TIMESTAMP', 'Nullable': 'YES', 'Key': '', 'Description': 'Import completion time'},
        ],
    }
    return tables


def get_view_definitions():
    """Define views based on create_views.sql."""
    views = [
        {
            'View Name': 'vw_weekly_time_summary',
            'Purpose': 'Weekly time aggregation by practice alignment and location',
            'Key Columns': 'week_start_date, practice_alignment, location, total_hours, billable_hours',
            'Source Tables': 'clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_resource_utilization',
            'Purpose': 'Resource utilization metrics per user per week',
            'Key Columns': 'week_start_date, user_name, utilization_percent, billable_percent',
            'Source Tables': 'clockify_detailed_time_entries, clockify_users',
        },
        {
            'View Name': 'vw_project_time_tracking',
            'Purpose': 'Time tracking aggregated by project',
            'Key Columns': 'week_start_date, project_name, client_name, total_hours, billable_hours',
            'Source Tables': 'clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_client_time_summary',
            'Purpose': 'Time summary aggregated by client',
            'Key Columns': 'week_start_date, client_name, active_projects, total_hours',
            'Source Tables': 'clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_skill_area_summary',
            'Purpose': 'Time distribution by skill area',
            'Key Columns': 'week_start_date, skill_area, practice_alignment, total_hours',
            'Source Tables': 'clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_daily_activity_trend',
            'Purpose': 'Daily activity patterns and trends',
            'Key Columns': 'entry_date, day_of_week, day_name, active_resources, total_hours',
            'Source Tables': 'clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_active_resources',
            'Purpose': 'Directory of active users with recent activity',
            'Key Columns': 'clockify_user_id, name, pod_assignment, last_time_entry_date, hours_last_30_days',
            'Source Tables': 'clockify_users, clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_import_activity',
            'Purpose': 'History of data import operations',
            'Key Columns': 'import_type, import_category, records_imported, status, duration_seconds',
            'Source Tables': 'import_logs',
        },
        {
            'View Name': 'vw_practice_alignment_performance_12w',
            'Purpose': 'Practice alignment performance over last 12 weeks',
            'Key Columns': 'week_start_date, practice_alignment, total_hours, billable_percent',
            'Source Tables': 'clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_monthly_summary',
            'Purpose': 'Monthly aggregation for historical trending',
            'Key Columns': 'month_start_date, year_month, practice_alignment, pod_assignment, total_hours',
            'Source Tables': 'clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_missing_time_submissions',
            'Purpose': 'Active users who haven\'t submitted time for prior week',
            'Key Columns': 'name, pod_assignment, hours_submitted, submission_status',
            'Source Tables': 'clockify_users, clockify_detailed_time_entries',
        },
        {
            'View Name': 'vw_pod_performance_analysis',
            'Purpose': 'Pod performance with 4-week and 12-week averages and trends',
            'Key Columns': 'pod_name, last_week_hours, avg_4_week_hours, avg_12_week_hours, variance, trend',
            'Source Tables': 'clockify_detailed_time_entries',
        },
    ]
    return views


def main():
    print("Generating database schema documentation...")

    output_path = project_root / 'database_schema.xlsx'

    # Get definitions
    tables = get_table_definitions()
    views = get_view_definitions()

    # Create summary data
    summary_data = {
        'Item': ['Total Tables', 'Total Views', 'Total Columns'],
        'Count': [
            len(tables),
            len(views),
            sum(len(cols) for cols in tables.values())
        ]
    }

    # Table summary
    table_summary = []
    for table_name, columns in tables.items():
        table_summary.append({
            'Table Name': table_name,
            'Column Count': len(columns),
            'Description': {
                'clockify_users': 'User profiles synced from Clockify',
                'clockify_projects': 'Project definitions synced from Clockify',
                'clockify_detailed_time_entries': 'Individual time entries (main fact table)',
                'user_skills': 'User skills and certifications',
                'ps_resource_forecasts': 'Professional services resource forecasts',
                'import_logs': 'Data import history and status',
            }.get(table_name, '')
        })

    # Write to Excel
    print(f"Writing to {output_path}...")
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Summary sheet
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        # Table overview
        pd.DataFrame(table_summary).to_excel(writer, sheet_name='Tables Overview', index=False)

        # All columns combined
        all_columns = []
        for table_name, columns in tables.items():
            for col in columns:
                all_columns.append({
                    'Table': table_name,
                    'Column': col['Column'],
                    'Data Type': col['Data Type'],
                    'Nullable': col['Nullable'],
                    'Key': col['Key'],
                    'Description': col['Description']
                })
        pd.DataFrame(all_columns).to_excel(writer, sheet_name='All Columns', index=False)

        # Individual table sheets
        for table_name, columns in tables.items():
            df = pd.DataFrame(columns)
            # Truncate sheet name to 31 chars (Excel limit)
            sheet_name = table_name[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        # Views sheet
        pd.DataFrame(views).to_excel(writer, sheet_name='Views', index=False)

    print(f"\nSchema exported to: {output_path}")

    # Print summary to console
    print("\n" + "=" * 60)
    print("DATABASE SCHEMA SUMMARY")
    print("=" * 60)

    print(f"\nTables: {len(tables)}")
    for table_name in tables:
        print(f"  - {table_name} ({len(tables[table_name])} columns)")

    print(f"\nViews: {len(views)}")
    for view in views:
        print(f"  - {view['View Name']}: {view['Purpose']}")


if __name__ == "__main__":
    main()
