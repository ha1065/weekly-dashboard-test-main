-- Migration 037: AI Forecast Analysis tables
-- Stores Bedrock AI analysis results for forecast vs actuals

CREATE TABLE IF NOT EXISTS ai_forecast_analysis (
    id                      SERIAL PRIMARY KEY,
    week_start              DATE NOT NULL,
    weeks_analyzed          INTEGER NOT NULL,
    user_name               VARCHAR(255) NOT NULL,
    location                VARCHAR(100),
    employment_designation  VARCHAR(100),
    total_forecasted_hours  NUMERIC(8,1),
    total_actual_hours      NUMERIC(8,1),
    variance_hours          NUMERIC(8,1),
    pct_achieved            NUMERIC(6,1),
    status                  VARCHAR(50),
    notes                   TEXT,
    analyzed_at             TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_forecast_analysis_week
    ON ai_forecast_analysis(week_start);

CREATE TABLE IF NOT EXISTS ai_forecast_summary (
    id                      SERIAL PRIMARY KEY,
    week_start              DATE NOT NULL,
    weeks_analyzed          INTEGER NOT NULL,
    total_resources         INTEGER,
    on_track_count          INTEGER,
    over_count              INTEGER,
    under_count             INTEGER,
    critical_under_count    INTEGER,
    no_actuals_count        INTEGER,
    unforecasted_count      INTEGER,
    key_observations        TEXT,
    recommendations         TEXT,
    analyzed_at             TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_forecast_summary_week
    ON ai_forecast_summary(week_start);

-- Seed default prompt
INSERT INTO ai_analysis_prompts (category, sequence_order, prompt_text, is_active)
VALUES (
    'FORECAST', 1,
    'You are a resource planning analyst for a professional services firm.
Review the forecast vs actual hours data below for the specified period.

For each resource: classify their utilization status and provide a one-sentence observation.

Status classifications:
- On Track: 80-120% of forecast achieved
- Over: >120% of forecast
- Under: 50-80% of forecast
- Critical Under: <50% of forecast (only when forecasted_hours > 10)
- No Actuals: forecasted hours exist but zero logged
- Unforecasted: hours logged with no forecast at all

Pay particular attention to:
- Resources with zero actuals despite significant forecasts (time submission or engagement issues)
- Completely unforecasted resources logging full weeks (planning gaps)
- Resources consistently below 50% of forecast (capacity or project issues)

Provide 3-5 key observations and 2-3 actionable recommendations for the delivery management team.
Return ONLY valid JSON matching the schema provided — no prose, no markdown.',
    TRUE
)
ON CONFLICT DO NOTHING;
