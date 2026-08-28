#!/usr/bin/env python3
"""
Pod Performance Analysis Report Generator
Generates a detailed report showing pod performance with trend indicators.
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from database.config import engine
from sqlalchemy import text
import pandas as pd


def generate_pod_performance_report():
    """Generate and display pod performance analysis report."""
    
    print("=" * 80)
    print("🎯 POD PERFORMANCE ANALYSIS REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Query the pod performance analysis view
        query = """
        SELECT 
            pod_name,
            last_week_hours,
            avg_30_day_hours,
            avg_90_day_hours,
            pct_change_vs_30_day,
            pct_change_vs_90_day,
            weekly_trend,
            performance_vs_30_day,
            last_week_billable_pct,
            last_week_resources,
            last_week_date
        FROM vw_pod_performance_analysis
        ORDER BY 
            CASE pod_name 
                WHEN 'Free Agent' THEN 1
                WHEN 'Alpha' THEN 2
                WHEN 'Bravo' THEN 3
                WHEN 'SurePoint' THEN 4
                WHEN 'A2Z' THEN 5
                ELSE 6
            END
        """
        
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
        
        if not rows:
            print("❌ No data found. Please ensure:")
            print("   1. Database views have been created (run: python src/database/apply_views.py)")
            print("   2. Time entry data has been imported")
            return
        
        # Display summary header
        last_week_date = rows[0].last_week_date if rows else None
        if last_week_date:
            week_end = last_week_date + timedelta(days=6)
            print(f"📅 Report Period: Week of {last_week_date.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
        print()
        
        # Display detailed pod analysis
        for row in rows:
            pod_name = row.pod_name
            last_week = row.last_week_hours or 0
            avg_30 = row.avg_30_day_hours or 0
            avg_90 = row.avg_90_day_hours or 0
            pct_30 = row.pct_change_vs_30_day or 0
            pct_90 = row.pct_change_vs_90_day or 0
            trend = row.weekly_trend or 'Unknown'
            performance = row.performance_vs_30_day or 'Unknown'
            billable_pct = row.last_week_billable_pct or 0
            resources = row.last_week_resources or 0
            
            # Determine trend emoji
            trend_emoji = {
                'Upward': '📈',
                'Downward': '📉',
                'Stable': '➡️'
            }.get(trend, '❓')
            
            # Determine performance emoji
            perf_emoji = {
                'Above Average': '🟢',
                'Below Average': '🔴',
                'Average': '🟡'
            }.get(performance, '⚪')
            
            print(f"🏢 {pod_name.upper()}")
            print(f"   Last Week Hours: {last_week:.1f}h ({resources} resources)")
            print(f"   30-Day Average:  {avg_30:.1f}h")
            print(f"   90-Day Average:  {avg_90:.1f}h")
            print(f"   vs 30-Day Avg:   {pct_30:+.1f}% {perf_emoji}")
            print(f"   vs 90-Day Avg:   {pct_90:+.1f}%")
            print(f"   Weekly Trend:    {trend} {trend_emoji}")
            print(f"   Billable Rate:   {billable_pct:.1f}%")
            print()
        
        # Generate summary insights
        print("=" * 80)
        print("📊 KEY INSIGHTS")
        print("=" * 80)
        
        # Find best and worst performers
        pod_data = [(row.pod_name, row.pct_change_vs_30_day or 0, row.weekly_trend) for row in rows if row.pod_name != 'Unassigned']
        
        if pod_data:
            best_pod = max(pod_data, key=lambda x: x[1])
            worst_pod = min(pod_data, key=lambda x: x[1])
            upward_pods = [pod[0] for pod in pod_data if pod[2] == 'Upward']
            downward_pods = [pod[0] for pod in pod_data if pod[2] == 'Downward']
            
            print(f"🏆 Best Performer:     {best_pod[0]} ({best_pod[1]:+.1f}% vs 30-day avg)")
            print(f"⚠️  Needs Attention:   {worst_pod[0]} ({worst_pod[1]:+.1f}% vs 30-day avg)")
            
            if upward_pods:
                print(f"📈 Upward Trends:      {', '.join(upward_pods)}")
            
            if downward_pods:
                print(f"📉 Downward Trends:    {', '.join(downward_pods)}")
        
        # Calculate totals
        total_last_week = sum(row.last_week_hours or 0 for row in rows)
        total_avg_30 = sum(row.avg_30_day_hours or 0 for row in rows)
        total_resources = sum(row.last_week_resources or 0 for row in rows)
        
        print()
        print(f"📈 Total Hours Last Week: {total_last_week:.1f}h")
        print(f"📊 Total 30-Day Average:  {total_avg_30:.1f}h")
        print(f"👥 Total Active Resources: {total_resources}")
        
        if total_avg_30 > 0:
            overall_change = ((total_last_week - total_avg_30) / total_avg_30) * 100
            print(f"🎯 Overall Performance:   {overall_change:+.1f}% vs 30-day average")
        
        print()
        print("=" * 80)
        print("💡 RECOMMENDATIONS")
        print("=" * 80)
        
        # Generate recommendations based on data
        recommendations = []
        
        for row in rows:
            if row.pod_name == 'Unassigned':
                continue
                
            pod = row.pod_name
            pct_change = row.pct_change_vs_30_day or 0
            trend = row.weekly_trend
            
            if pct_change < -20:
                recommendations.append(f"🔴 {pod}: Significant decline (-{abs(pct_change):.1f}%). Investigate capacity issues or project delays.")
            elif pct_change > 20:
                recommendations.append(f"🟢 {pod}: Strong performance (+{pct_change:.1f}%). Consider if sustainable or temporary spike.")
            elif trend == 'Downward' and pct_change < -5:
                recommendations.append(f"🟡 {pod}: Declining trend. Monitor closely and identify root causes.")
            elif trend == 'Upward' and pct_change > 5:
                recommendations.append(f"🟢 {pod}: Positive trend. Good momentum to maintain.")
        
        if not recommendations:
            recommendations.append("✅ All pods performing within normal ranges. Continue monitoring.")
        
        for rec in recommendations:
            print(f"   {rec}")
        
        print()
        print("=" * 80)
        print("🔄 Next Steps:")
        print("   1. Review individual resource utilization within underperforming pods")
        print("   2. Analyze project allocation and capacity planning")
        print("   3. Schedule follow-up review next week")
        print("   4. Deploy QuickSight dashboard for real-time monitoring")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error generating report: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Ensure database connection is configured")
        print("2. Run: python src/database/apply_views.py")
        print("3. Import time entry data if not already done")
        return False
    
    return True


def export_to_csv():
    """Export pod performance data to CSV for further analysis."""
    try:
        query = """
        SELECT * FROM vw_pod_performance_analysis
        ORDER BY 
            CASE pod_name 
                WHEN 'Free Agent' THEN 1
                WHEN 'Alpha' THEN 2
                WHEN 'Bravo' THEN 3
                WHEN 'SurePoint' THEN 4
                WHEN 'A2Z' THEN 5
                ELSE 6
            END
        """
        
        df = pd.read_sql(query, engine)
        
        # Create output filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"pod_performance_report_{timestamp}.csv"
        filepath = Path("data/outputs") / filename
        
        # Ensure output directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Export to CSV
        df.to_csv(filepath, index=False)
        print(f"📄 Report exported to: {filepath}")
        
        return str(filepath)
        
    except Exception as e:
        print(f"❌ Error exporting to CSV: {str(e)}")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Pod Performance Analysis Report')
    parser.add_argument('--export-csv', action='store_true', help='Export data to CSV file')
    parser.add_argument('--quiet', action='store_true', help='Suppress detailed output')
    
    args = parser.parse_args()
    
    if not args.quiet:
        success = generate_pod_performance_report()
    else:
        success = True
    
    if args.export_csv and success:
        export_to_csv()