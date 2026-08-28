# Forecast Model Improvement Plan

## Problem Statement

The current resource forecast model overweights PM estimates (which have low accuracy) and lacks proper integration of historical hours and Jira velocity, causing poor resource predictions.

---

## Current Model Architecture

The model lives in `src/integrations/forecast_resources.py` and uses a **3-signal weighted blend**:

| Signal | Default Weight | Source | Issue |
|--------|---------------|--------|-------|
| Historical hours | 50% | Clockify actuals (8-week lookback) | Simple average — no recency weighting |
| Jira velocity | 30% | Ticket count ÷ weeks | Ignores ticket size (story points) |
| PM forecast | 20% | `ps_resource_forecasts` table | No accuracy feedback — bad PMs still get 20% |

Weights are stored in `forecast_config` table and configurable via Streamlit Admin.

### How the Blend Works

1. Each signal produces a "weeks remaining" estimate for the project
2. Signals are weighted and blended to produce a single `est_completion` date
3. The completion date drives a **decay factor** on per-person hourly forecasts
4. Forecasts are capped by: remaining SOW hours, individual weekly capacity

### Root Causes of Poor Predictions

1. **PM signal has no accuracy discount** — a PM who's consistently 40% wrong still contributes 20% to the blend
2. **Jira velocity is ticket-count-based** — a 1-point bug and an 8-point epic count the same
3. **Historical hours use a flat average** — all 8 weeks weighted equally, so ramp-up/ramp-down is invisible
4. **Weights are globally static** — same weights for a new project (no history) and a mature one (8 weeks of data)
5. **No hours-based burn rate** — the "historical hours" signal is per-person allocation, not project-level burn velocity

---

## Improvement Steps

### Step 1: PM Accuracy Tracking (Feedback Loop)

**Goal:** Automatically discount the PM signal based on historical accuracy.

#### Schema

```sql
CREATE TABLE pm_forecast_accuracy (
    pm_name         VARCHAR(255) NOT NULL,
    client_name     VARCHAR(255) NOT NULL,
    project_name    VARCHAR(255) NOT NULL,
    week_start      DATE NOT NULL,
    forecasted_hrs  NUMERIC(10,2),
    actual_hrs      NUMERIC(10,2),
    error_pct       NUMERIC(10,2),  -- ABS(forecast - actual) / actual * 100
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (pm_name, client_name, project_name, week_start)
);
```

#### Weekly Computation

```python
def compute_pm_accuracy(conn, lookback_weeks=12):
    """Compare PM forecasts from N weeks ago against actual hours."""
    conn.execute(text("""
        INSERT INTO pm_forecast_accuracy (pm_name, client_name, project_name, week_start, forecasted_hrs, actual_hrs, error_pct)
        SELECT
            f.created_by AS pm_name,
            f.client_name,
            f.project_name,
            f.week_start_date,
            f.forecasted_hours,
            COALESCE(a.actual_hours, 0),
            CASE WHEN COALESCE(a.actual_hours, 0) > 0
                 THEN ABS(f.forecasted_hours - a.actual_hours) / a.actual_hours * 100
                 ELSE 100 END
        FROM ps_resource_forecasts f
        LEFT JOIN (
            SELECT client_name, project_name, week_start, SUM(duration_hours) AS actual_hours
            FROM clockify_detailed_time_entries
            GROUP BY client_name, project_name, week_start
        ) a ON a.client_name = f.client_name
           AND a.project_name = f.project_name
           AND a.week_start = f.week_start_date
        WHERE f.week_start_date < CURRENT_DATE - INTERVAL '7 days'
        ON CONFLICT DO NOTHING
    """))
```

#### Dynamic Weight Application

```python
# Per-project PM confidence (last 12 weeks)
pm_accuracy = conn.execute(text("""
    SELECT client_name, project_name, AVG(error_pct) AS avg_error
    FROM pm_forecast_accuracy
    WHERE week_start >= CURRENT_DATE - INTERVAL '12 weeks'
    GROUP BY client_name, project_name
""")).fetchall()

# Convert error % to confidence: 0% error → 1.0, 100% error → 0.0
pm_confidence = {(r.client_name, r.project_name): max(0, 1 - r.avg_error / 100) for r in pm_accuracy}

# In the blend:
effective_pm_weight = weight_pm * pm_confidence.get(proj_key, 0.5)  # 50% default for new projects
```

**Impact:** Directly solves the "PM overweight" problem. Bad PMs auto-correct to near-zero influence.

---

### Step 2: Story-Point Velocity (Not Raw Ticket Count)

**Goal:** Measure Jira velocity in points completed per week, not tickets per week.

#### Modified Jira Query

```python
# Fetch remaining tickets WITH story points
remaining_resp = requests.post(
    f"{base_url}/rest/api/3/search/jql",
    json={
        'jql': f'project={project_key} AND status!=Done AND issuetype in (Story,Task,Bug)',
        'maxResults': 100,
        'fields': ['customfield_10016']  # story_points field ID (configurable)
    },
    auth=auth, timeout=15
)

# Sum remaining story points (default 1 if unestimated)
remaining_points = sum(
    issue['fields'].get('customfield_10016', 1) or 1
    for issue in remaining_resp.json().get('issues', [])
)

# Resolved points in lookback window
resolved_points = sum(
    issue['fields'].get('customfield_10016', 1) or 1
    for issue in resolved_resp.json().get('issues', [])
)

velocity_points_per_week = resolved_points / lookback_weeks
weeks_remaining = remaining_points / velocity_points_per_week if velocity_points_per_week > 0 else 99
```

#### Config Addition

```sql
INSERT INTO forecast_config (key, value, description) VALUES
    ('jira_story_points_field', 10016, 'Custom field ID for story points in Jira')
ON CONFLICT (key) DO NOTHING;
```

**Impact:** Projects with mixed ticket sizes get accurate velocity. A project with 5 remaining 8-point epics correctly shows more work than 5 remaining 1-point bugs.

---

### Step 3: Recency-Weighted Historical Average (EWMA)

**Goal:** Give recent weeks more influence in the per-person hourly average.

#### Implementation

```python
def weighted_average(hours_list, alpha=0.3):
    """Exponentially weighted moving average — recent weeks count more.
    
    alpha=0.3 means:
    - Most recent week: ~30% influence
    - 2 weeks ago: ~21%
    - 3 weeks ago: ~15%
    - 4 weeks ago: ~10%
    - Older: diminishing
    """
    if not hours_list:
        return 0
    # hours_list ordered oldest → newest
    weights = [(1 - alpha) ** (len(hours_list) - 1 - i) for i in range(len(hours_list))]
    total_weight = sum(weights)
    return sum(h * w for h, w in zip(hours_list, weights)) / total_weight
```

#### Change in `forecast_resources.py`

```python
# BEFORE (flat average):
person_project_avg[key] = sum(hours_list) / len(hours_list)

# AFTER (recency-weighted):
# Sort hours_list by week (oldest first)
sorted_hours = [h for _, h in sorted(zip(week_dates, hours_list))]
person_project_avg[key] = weighted_average(sorted_hours, alpha=0.3)
```

#### Config Addition

```sql
INSERT INTO forecast_config (key, value, description) VALUES
    ('ewma_alpha', 0.30, 'EWMA decay factor for historical hours (0.1=slow decay, 0.5=fast decay)')
ON CONFLICT (key) DO NOTHING;
```

**Impact:** Ramp-down is immediately reflected. A person who worked 40h/week for 6 weeks then 5h/week for 2 weeks will forecast ~10h (weighted toward recent), not 31h (flat average).

---

### Step 4: Adaptive Weights by Project Maturity

**Goal:** Use different signal weights depending on available data quality.

```python
def compute_adaptive_weights(project_age_weeks, has_jira_board, pm_confidence_score):
    """
    New project (< 4 weeks history): rely more on PM estimate (discounted)
    Mature project with Jira board: rely more on actuals + velocity
    PM with poor track record: reduce PM weight automatically
    """
    if project_age_weeks < 4:
        # New project — PM is primary signal (but discounted by accuracy)
        base = {'hours': 0.20, 'jira': 0.20, 'pm': 0.60}
    elif has_jira_board:
        # Mature project with board — full 3-signal blend
        base = {'hours': 0.50, 'jira': 0.35, 'pm': 0.15}
    else:
        # Mature but no Jira board — hours-heavy
        base = {'hours': 0.70, 'jira': 0.0, 'pm': 0.30}
    
    # Apply PM confidence discount
    base['pm'] *= pm_confidence_score
    
    # Re-normalize
    total = sum(base.values())
    return {k: v / total for k, v in base.items()} if total > 0 else base
```

#### Determining Project Age

```python
# How many weeks of Clockify history exist for this project?
project_age_weeks = len(person_project_hours.get((uid, client, project), []))
```

**Impact:** New projects aren't penalized by missing historical data. Mature projects don't give undeserved weight to inaccurate PM estimates.

---

### Step 5: Hours-Based Burn Rate (Independent of PM/Jira)

**Goal:** Compute a pure hours velocity signal that works even without a Jira board.

```python
# Project-level burn rate from Clockify (last 4 weeks)
burn_rates = conn.execute(text("""
    SELECT
        te.client_name,
        te.project_name,
        SUM(te.duration_hours) / COUNT(DISTINCT te.week_start) AS hrs_per_week,
        COUNT(DISTINCT te.week_start) AS weeks_with_data
    FROM clockify_detailed_time_entries te
    JOIN clockify_projects cp ON te.clockify_project_id = cp.clockify_project_id
    WHERE te.week_start >= :cutoff
      AND cp.project_type = 'Professional Services'
      AND te.duration_hours > 0
    GROUP BY te.client_name, te.project_name
"""), {'cutoff': current_monday - timedelta(weeks=4)}).fetchall()

# Compute hours-based weeks remaining
for rate in burn_rates:
    proj_key = (rate.client_name, rate.project_name)
    if proj_key in project_map and rate.hrs_per_week > 0:
        remaining_sow = project_map[proj_key]['remaining_sow']
        hours_weeks_remaining = remaining_sow / rate.hrs_per_week
        project_map[proj_key]['hours_velocity_weeks'] = hours_weeks_remaining
```

This replaces/strengthens the "historical hours" signal in the blend — instead of just using per-person averages, the model also knows how fast the project is consuming its SOW budget at the aggregate level.

**Impact:** Projects that are burning hot (many people, high hours) get shorter completion estimates regardless of what the PM says.

---

### Step 6: Forecast Accuracy Dashboard

**Goal:** Track and surface model accuracy over time to build trust and enable tuning.

#### Schema

```sql
CREATE TABLE forecast_accuracy_log (
    week_start       DATE NOT NULL,
    client_name      VARCHAR(255),
    project_name     VARCHAR(255),
    signal_used      VARCHAR(50),  -- 'historical', 'jira', 'pm', 'blended'
    forecasted_hrs   NUMERIC(10,2),
    actual_hrs       NUMERIC(10,2),
    error_pct        NUMERIC(10,2),
    captured_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (week_start, client_name, project_name)
);
```

#### Weekly Backtest

After each import, compare forecasts generated 1-4 weeks ago against today's actuals:

```python
def log_forecast_accuracy(conn, current_monday):
    """Compare forecasts from 1-4 weeks ago against actuals."""
    for weeks_ago in [1, 2, 3, 4]:
        target_week = current_monday - timedelta(weeks=weeks_ago)
        conn.execute(text("""
            INSERT INTO forecast_accuracy_log (week_start, client_name, project_name, signal_used, forecasted_hrs, actual_hrs, error_pct)
            SELECT
                f.week_start,
                f.client_name,
                f.project_name,
                'blended',
                f.hours AS forecasted_hrs,
                COALESCE(a.actual_hours, 0),
                CASE WHEN COALESCE(a.actual_hours, 0) > 0
                     THEN ABS(f.hours - a.actual_hours) / a.actual_hours * 100
                     ELSE NULL END
            FROM ps_resource_forecast_v2 f
            LEFT JOIN (
                SELECT client_name, project_name, week_start, SUM(duration_hours) AS actual_hours
                FROM clockify_detailed_time_entries
                WHERE week_start = :target_week
                GROUP BY client_name, project_name, week_start
            ) a ON a.client_name = f.client_name AND a.project_name = f.project_name
            WHERE f.week_start = :target_week AND f.is_actual = FALSE
            ON CONFLICT DO NOTHING
        """), {'target_week': target_week})
```

#### QuickSight KPI

Surface as a "Forecast Accuracy" tile:
- **MAPE** (Mean Absolute Percentage Error) trending over time
- Breakdown by signal type (historical vs Jira vs PM vs blended)
- Per-project accuracy heatmap

**Impact:** Gives leadership visibility into model improvement. Enables data-driven weight tuning.

---

## Implementation Priority

| Step | What | Priority | Effort | Impact |
|------|------|----------|--------|--------|
| 1 | PM accuracy tracking + dynamic weight discount | **High** | Medium | Directly fixes PM overweight problem |
| 3 | Recency-weighted historical average (EWMA) | **High** | Low | Fixes ramp-down prediction failures |
| 5 | Hours-based burn rate velocity | **Medium** | Low | Strengthens historical signal for all projects |
| 4 | Adaptive weights by project maturity | **Medium** | Medium | Handles new vs mature projects differently |
| 2 | Story-point velocity (not ticket count) | **Medium** | Low | More accurate Jira signal |
| 6 | Accuracy log + dashboard | **Low** | Low | Builds trust, enables tuning |

---

## Quick Wins (Can Ship This Week)

1. **EWMA** (Step 3) — single function change, ~20 lines of code
2. **Burn rate** (Step 5) — one SQL query + one comparison in the blend
3. **Reduce PM default weight** from 0.20 → 0.10 in `forecast_config` while accuracy tracking is built

## Medium-Term (1-2 Weeks)

4. **PM accuracy table + computation** (Step 1) — migration + weekly job
5. **Adaptive weights** (Step 4) — refactor the weight section of `forecast_resources.py`

## Longer-Term (Sprint)

6. **Story-point velocity** (Step 2) — requires knowing the story points custom field ID per Jira instance
7. **Accuracy dashboard** (Step 6) — new QuickSight dataset + visuals
