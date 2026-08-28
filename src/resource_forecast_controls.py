"""Resource forecast advanced controls (settings, extensions, run forecast, model config)."""
import streamlit as st
from sqlalchemy import text


def _render_settings(engine):
    st.info("Forecast settings — coming in Sprint 3.")


def _render_extensions(engine):
    st.info("Project extensions — coming in Sprint 3.")


def _render_run_forecast(engine):
    import boto3, json
    st.subheader("▶️ Run Capacity Forecast")
    st.caption("Recomputes the resource capacity model using current Clockify actuals, Jira velocity, and PM forecasts. Writes to `ps_resource_forecast_v2` and refreshes QuickSight.")

    if st.button("🚀 Run Forecast Now", type="primary"):
        try:
            lc = boto3.client('lambda', region_name='us-east-1')
            with st.spinner("Running forecast model (30-60 seconds)..."):
                resp = lc.invoke(
                    FunctionName='production-clockify-import',
                    InvocationType='RequestResponse',
                    Payload=json.dumps({"mode": "forecast_resources",
                                        "refresh_quicksight": True,
                                        "quicksight_dataset_ids": ["resource-capacity-plan",
                                                                    "8900f5dc-687e-4d5b-9f91-5efd0cd1daed"]})
                )
            payload = json.loads(resp['Payload'].read())
            if resp.get('StatusCode') == 200 and 'FunctionError' not in resp:
                st.success("✅ Forecast complete. QuickSight refresh triggered.")
                body = json.loads(payload.get('body', '{}'))
                if body.get('rows_written'):
                    st.caption(f"{body['rows_written']} forecast rows written.")
            else:
                st.error(f"Error: {payload.get('errorMessage', payload.get('body', 'Unknown'))}")
        except Exception as e:
            st.error(f"Failed to invoke Lambda: {e}")


def _render_model_config(db):
    """Forecast model weight configuration — rendered in Resource Forecast > Advanced > Model Config."""
    st.subheader("⚖️ Forecast Model Weights")
    st.caption("Controls how the resource forecast blends three signals. Weights are auto-normalised to sum to 1.0.")

    try:
        _cfg_rows = db.execute(text("SELECT key, value FROM forecast_config ORDER BY key")).fetchall()
        _cfg = {r[0]: float(r[1]) for r in _cfg_rows}
    except Exception:
        _cfg = {}

    with st.form("forecast_config_form"):
        st.markdown("**Signal Weights**")
        col1, col2, col3 = st.columns(3)
        with col1:
            w_hours = st.slider("📊 Clockify Actuals", 0.0, 1.0, step=0.05,
                value=_cfg.get('weight_historical_hours', 0.50),
                help="Weight based on historical Clockify hours per person/project")
        with col2:
            w_jira = st.slider("🎫 Jira Velocity", 0.0, 1.0, step=0.05,
                value=_cfg.get('weight_jira_velocity', 0.30),
                help="Weight based on Jira ticket burn rate")
        with col3:
            w_pm = st.slider("📋 PM Forecast", 0.0, 1.0, step=0.05,
                value=_cfg.get('weight_pm_forecast', 0.20),
                help="Weight based on PM-uploaded forecast template")

        total_w = w_hours + w_jira + w_pm
        if total_w > 0:
            st.caption(f"Effective: Actuals={w_hours/total_w:.0%}  Jira={w_jira/total_w:.0%}  PM={w_pm/total_w:.0%}")

        opt1, opt2, opt3 = st.columns(3)
        with opt1:
            seasonal_on = st.toggle("🌡️ Seasonal Correction",
                value=int(_cfg.get('seasonal_correction_enabled', 1)) == 1)
        with opt2:
            decay_weeks = st.number_input("📉 Decay Start (wks before end)",
                min_value=0.5, max_value=8.0, step=0.5,
                value=float(_cfg.get('decay_start_weeks', 2.0)))
        with opt3:
            lookback_val = int(_cfg.get('lookback_weeks', _cfg.get('lookback_weeks_default', 8)))
            if lookback_val not in [4, 6, 8, 12]:
                lookback_val = 8
            lookback = st.selectbox("🔍 Lookback Window", options=[4, 6, 8, 12],
                index=[4, 6, 8, 12].index(lookback_val))

        if st.form_submit_button("💾 Save Config", type="primary"):
            updates = {
                'weight_historical_hours':     w_hours,
                'weight_jira_velocity':        w_jira,
                'weight_pm_forecast':          w_pm,
                'seasonal_correction_enabled': 1 if seasonal_on else 0,
                'decay_start_weeks':           decay_weeks,
                'lookback_weeks':              lookback,
            }
            for k, v in updates.items():
                db.execute(text("""
                    INSERT INTO forecast_config (key, value, updated_at)
                    VALUES (:k, :v, NOW())
                    ON CONFLICT (key) DO UPDATE SET value=:v, updated_at=NOW()
                """), {'k': k, 'v': v})
            db.commit()
            st.success("Config saved. Run the forecast to apply.")
