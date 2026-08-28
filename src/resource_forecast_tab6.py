"""Tab 6 — Resource Forecast dashboard (S04-01)"""
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from datetime import datetime, timedelta


def render(engine):
    """Render Tab 6: Resource Forecast page"""
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with engine.connect() as conn:
        # Get distinct PM names and project names
        pm_names = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT pm_name FROM ps_resource_forecasts WHERE pm_name IS NOT NULL ORDER BY pm_name"
        )).fetchall()]
        
        project_names = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT project_name FROM ps_resource_forecast_v2 WHERE project_name IS NOT NULL ORDER BY project_name"
        )).fetchall()]
    
    with col1:
        selected_pms = st.multiselect("PM", pm_names, key="rf_pm")
    
    with col2:
        selected_projects = st.multiselect("Project", project_names, key="rf_project")
    
    # Week range - default 8 weeks back to current week + 11 weeks forward (12 weeks total)
    current_monday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    current_monday = current_monday - timedelta(days=current_monday.weekday())
    default_start = current_monday - timedelta(weeks=8)
    default_end = current_monday + timedelta(weeks=11)
    
    with col3:
        date_cols = st.columns(2)
        with date_cols[0]:
            start_date = st.date_input("Start", value=default_start.date(), key="rf_start")
        with date_cols[1]:
            end_date = st.date_input("End", value=default_end.date(), key="rf_end")
    
    st.markdown("---")
    
    # Section 1: Dual 12-week bar charts
    st.subheader("Section 1: Dual 12-Week Forecasts")
    
    with engine.connect() as conn:
        pm_forecast_sql = text("""
            SELECT week_start_date AS week_start, project_name, SUM(forecasted_hours) as hours
            FROM ps_resource_forecasts
            WHERE week_start_date BETWEEN :start AND :end
            GROUP BY week_start_date, project_name
            ORDER BY week_start_date, project_name
        """)
        pm_forecast = conn.execute(pm_forecast_sql, {"start": start_date, "end": end_date}).fetchall()
        
        capacity_sql = text("""
            SELECT week_start, project_name, SUM(hours) as total_hours
            FROM ps_resource_forecast_v2
            WHERE is_actual=FALSE AND hours > 0 AND week_start BETWEEN :start AND :end
            GROUP BY week_start, project_name
            ORDER BY week_start, project_name
        """)
        capacity = conn.execute(capacity_sql, {"start": start_date, "end": end_date}).fetchall()
    
    pm_df = pd.DataFrame(pm_forecast, columns=['week_start', 'project_name', 'hours'])
    capacity_df = pd.DataFrame(capacity, columns=['week_start', 'project_name', 'hours'])
    
    col_l, col_r = st.columns(2)
    
    with col_l:
        if not pm_df.empty:
            fig_pm = px.bar(pm_df, x='week_start', y='hours', color='project_name',
                           barmode='stack', title='PM Forecast',
                           labels={'hours': 'Hours', 'week_start': 'Week'})
            st.plotly_chart(fig_pm, use_container_width=True)
        else:
            st.info("No PM forecast data")
    
    with col_r:
        if not capacity_df.empty:
            fig_cap = px.bar(capacity_df, x='week_start', y='hours', color='project_name',
                            barmode='stack', title='Capacity Model',
                            labels={'hours': 'Hours', 'week_start': 'Week'})
            st.plotly_chart(fig_cap, use_container_width=True)
        else:
            st.info("No capacity model data")
    
    st.markdown("---")
    
    # Section 2: Forecast vs Actuals
    st.subheader("Section 2: Forecast vs Actuals")
    
    with engine.connect() as conn:
        fv_sql = text("""
            SELECT week_start, project_name,
              SUM(CASE WHEN source='pm' THEN hours END) pm_hrs,
              SUM(CASE WHEN source='model' THEN hours END) model_hrs,
              SUM(CASE WHEN source='actual' THEN hours END) actual_hrs
            FROM (
              SELECT week_start_date AS week_start, project_name, forecasted_hours hours, 'pm' source 
              FROM ps_resource_forecasts WHERE week_start_date < CURRENT_DATE::DATE
              UNION ALL
              SELECT week_start, project_name, hours, CASE WHEN is_actual THEN 'actual' ELSE 'model' END 
              FROM ps_resource_forecast_v2 WHERE week_start < CURRENT_DATE::DATE
            ) t GROUP BY week_start, project_name
            ORDER BY week_start, project_name
        """)
        fv_data = conn.execute(fv_sql).fetchall()
    
    if fv_data:
        fv_df = pd.DataFrame(fv_data, columns=['week_start', 'project_name', 'pm_hrs', 'model_hrs', 'actual_hrs'])
        # Coerce to float — SUM(CASE WHEN ...) returns NULL when no rows match, causing mixed types
        for col in ['pm_hrs', 'model_hrs', 'actual_hrs']:
            fv_df[col] = pd.to_numeric(fv_df[col], errors='coerce').fillna(0.0)
        fv_agg = fv_df.groupby('week_start')[['pm_hrs', 'model_hrs', 'actual_hrs']].sum().reset_index()
        fv_agg = fv_agg.rename(columns={'pm_hrs': 'PM Forecast', 'model_hrs': 'Model Forecast', 'actual_hrs': 'Actuals'})
        fig_fv = px.line(fv_agg, x='week_start', y=['PM Forecast', 'Model Forecast', 'Actuals'],
                        title='Forecast vs Actuals (All Projects Combined)',
                        labels={'week_start': 'Week', 'value': 'Hours'})
        st.plotly_chart(fig_fv, use_container_width=True)
    else:
        st.info("No forecast vs actual data available")
