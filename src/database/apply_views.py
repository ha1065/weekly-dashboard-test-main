"""Apply database views for QuickSight reporting."""

from pathlib import Path
from sqlalchemy import text
from src.database.config import engine


def apply_views():
    """Create or replace all reporting views."""
    print("=" * 60)
    print("🔨 Creating QuickSight Reporting Views")
    print("=" * 60)

    # Read the SQL file
    sql_file = Path(__file__).parent / "create_views.sql"

    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()

        # Split by statement and execute each
        # Note: We can't simply split by ';' because comments might have them
        # Instead, execute the whole file as one transaction
        with engine.begin() as connection:
            connection.execute(text(sql_content))

        print("\n✅ Successfully created all reporting views!")
        print("\nCreated views:")
        print("  1. vw_weekly_time_summary - Weekly aggregates by service line and location")
        print("  2. vw_resource_utilization - Resource utilization and billability")
        print("  3. vw_project_time_tracking - Project-level time tracking")
        print("  4. vw_client_time_summary - Client-level summaries")
        print("  5. vw_skill_area_summary - Skill area distribution")
        print("  6. vw_daily_activity_trend - Daily activity patterns")
        print("  7. vw_active_resources - Active resource directory")
        print("  8. vw_import_activity - Data import history")
        print("  9. vw_practice_alignment_performance_12w - 12-week practice alignment trends")
        print(" 10. vw_monthly_summary - Monthly historical trends with pod assignment and practice alignment")
        print(" 11. vw_missing_time_submissions - Users missing time for prior week")
        print(" 12. vw_pod_performance_summary - POD performance metrics")
        print(" 13. vw_contractor_weekly_trend - Contractor hours 5-week trend")
        print(" 14. vw_contractor_time_summary - Contractor last week vs 4-week average")
        print(" 15. vw_forecast_pivot - Forecast data for pivot table (Client/Project/PM/User by Week)")
        print(" 16. vw_forecast_summary_by_client - Forecast summary aggregated by client/week")
        print(" 17. vw_forecast_over_40_hours - Users with >40 hours forecasted per week")
        print(" 18. vw_ps_project_status - PS project status with actual hours")
        print(" 19. vw_data_freshness - Last import timestamps per category")

        print("\n" + "=" * 60)
        print("📊 Ready for QuickSight integration!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Failed to create views: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    apply_views()
