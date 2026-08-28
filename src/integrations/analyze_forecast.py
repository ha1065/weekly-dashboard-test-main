"""AI-driven forecast vs actuals analysis using Amazon Bedrock.

Fetches the past N weeks of vw_forecast_vs_actual, aggregates per-user,
computes status programmatically for all users, then calls Bedrock to:
  - Annotate the most notable users (non-on-track) with one-sentence notes
  - Produce overall key observations and recommendations

Stores results in ai_forecast_analysis and ai_forecast_summary tables.
"""

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

import boto3


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _fetch_forecast_data(week_start: date, weeks_back: int) -> List[Dict]:
    """Aggregate vw_forecast_vs_actual per user for the analysis window."""
    from sqlalchemy import create_engine, text

    start_date = week_start - timedelta(weeks=weeks_back)
    engine = create_engine(os.environ['DATABASE_URL'])
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    f.user_name,
                    MAX(u.location)                              AS location,
                    MAX(u.employment_designation)                AS employment_designation,
                    ROUND(SUM(f.forecasted_hours)::numeric, 1)  AS total_forecasted,
                    ROUND(SUM(f.actual_hours)::numeric, 1)       AS total_actual,
                    ROUND((SUM(f.actual_hours) - SUM(f.forecasted_hours))::numeric, 1) AS variance,
                    ROUND(
                        (SUM(f.actual_hours) / NULLIF(SUM(f.forecasted_hours), 0) * 100)::numeric, 1
                    )                                            AS pct_achieved
                FROM vw_forecast_vs_actual f
                LEFT JOIN clockify_users u ON LOWER(u.name) = LOWER(f.user_name)
                WHERE f.week_start_date >= :start
                  AND f.week_start_date < CURRENT_DATE
                GROUP BY f.user_name
                HAVING SUM(f.forecasted_hours) > 0 OR SUM(f.actual_hours) > 0
                ORDER BY (SUM(f.actual_hours) - SUM(f.forecasted_hours)) ASC
            """), {'start': start_date}).fetchall()
    finally:
        engine.dispose()

    return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------------------
# Compute status programmatically
# ---------------------------------------------------------------------------

def _compute_status(fcst: float, act: float, pct) -> str:
    """Classify a user's utilization status from raw numbers."""
    pct_val = float(pct) if pct is not None else None
    if fcst <= 0 and act > 0:
        return 'Unforecasted'
    if fcst > 0 and act <= 0:
        return 'No Actuals'
    if pct_val is None:
        return 'Unknown'
    if pct_val > 120:
        return 'Over'
    if pct_val >= 80:
        return 'On Track'
    if fcst > 10 and pct_val < 50:
        return 'Critical Under'
    return 'Under'


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompt() -> str:
    """Load the FORECAST prompt from ai_analysis_prompts table."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return ''

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT prompt_text
                FROM ai_analysis_prompts
                WHERE category = 'FORECAST' AND is_active = TRUE
                ORDER BY sequence_order
            """)).fetchall()
    finally:
        engine.dispose()

    return '\n\n'.join(r[0] for r in rows)


# ---------------------------------------------------------------------------
# Format notable users for Bedrock annotation
# ---------------------------------------------------------------------------

_JSON_SCHEMA = """\
Return exactly this JSON (no surrounding text, no markdown):
{
  "analysis_period": "YYYY-MM-DD to YYYY-MM-DD",
  "key_observations": [
    "• Observation 1",
    "• Observation 2"
  ],
  "recommendations": [
    "• Recommendation 1",
    "• Recommendation 2"
  ],
  "user_notes": {
    "User Name": "One-sentence note for this user.",
    "Another User": "One-sentence note."
  }
}

Include a note for every user listed in the Notable Resources section above.
key_observations: 3-5 bullet points summarising patterns across the full dataset.
recommendations: 2-3 actionable bullet points for delivery management."""


def _format_notable_for_bedrock(
    all_rows: List[Dict],
    notable: List[Dict],
    start_date: date,
    end_date: date,
) -> str:
    """Build Bedrock prompt context: summary stats + notable users table."""
    total = len(all_rows)
    status_counts: Dict[str, int] = {}
    for r in all_rows:
        s = _compute_status(
            float(r.get('total_forecasted') or 0),
            float(r.get('total_actual') or 0),
            r.get('pct_achieved'),
        )
        status_counts[s] = status_counts.get(s, 0) + 1

    summary_lines = [
        f"Analysis period: {start_date} to {end_date}",
        f"Total resources: {total}",
        "Status distribution:",
    ]
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        summary_lines.append(f"  {status}: {count}")

    summary_lines += ["", "Notable Resources (non-on-track, requiring annotation):"]
    summary_lines.append(
        f"{'User':<30} {'Location':<12} {'Type':<12} {'Fcst':>7} {'Actual':>7} {'Var':>7} {'%':>6}  Status"
    )
    summary_lines.append("-" * 95)

    for r in notable:
        fcst = float(r.get('total_forecasted') or 0)
        act = float(r.get('total_actual') or 0)
        var = float(r.get('variance') or 0)
        pct = r.get('pct_achieved')
        # Cap displayed % at 200 — very high values (e.g. 2837%) occur when
        # a resource had a near-zero forecast but logged significant actuals,
        # making the raw % misleading for narrative observations.
        if pct is not None:
            pct_display = min(float(pct), 200.0)
            pct_str = f"{pct_display:.1f}%{'+' if float(pct) > 200 else ''}"
        else:
            pct_str = "N/A"
        status = _compute_status(fcst, act, pct)
        loc = (r.get('location') or 'Unknown')[:12]
        emp = (r.get('employment_designation') or 'FTE')[:12]
        summary_lines.append(
            f"{str(r['user_name']):<30} {loc:<12} {emp:<12} {fcst:>7.1f} {act:>7.1f} {var:>+7.1f} {pct_str:>6}  {status}"
        )

    return '\n'.join(summary_lines)


# ---------------------------------------------------------------------------
# Bedrock call
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a resource planning analyst for a professional services firm.
Analyse the forecast vs actual hours data provided.
When writing observations and notes, refer to absolute hour figures (e.g. "logged 45h against a 10h forecast") \
rather than citing raw percentages — high percentages are often an artefact of a near-zero forecast \
and are not meaningful on their own.
Return ONLY valid JSON — no markdown, no prose outside the JSON structure.\
"""


def _call_bedrock(user_message: str) -> str:
    """Invoke Bedrock Converse API and return raw text response."""
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    region = os.environ.get('AWS_REGION', 'us-east-1')

    bedrock = boto3.client('bedrock-runtime', region_name=region)
    response = bedrock.converse(
        modelId=model_id,
        system=[{'text': _SYSTEM_PROMPT}],
        messages=[{'role': 'user', 'content': [{'text': user_message}]}],
        inferenceConfig={'maxTokens': 4096, 'temperature': 0.1},
    )
    return response['output']['message']['content'][0]['text']


def _parse_json(raw: str) -> Dict:
    """Extract and parse the JSON object from a Bedrock response."""
    raw = raw.strip()
    m = re.search(r'```(?:json)?\s*([\s\S]+?)```', raw)
    if m:
        raw = m.group(1).strip()
    start = raw.find('{')
    if start > 0:
        raw = raw[start:]
    return json.loads(raw)


# ---------------------------------------------------------------------------
# PM forecast accuracy
# ---------------------------------------------------------------------------

_PM_NARRATIVE_SCHEMA = """\
Return exactly this JSON (no surrounding text, no markdown):
{
  "pm_narratives": {
    "PM Name": "One-sentence narrative.",
    "Another PM": "One-sentence narrative."
  }
}

Include an entry for every PM listed above.
Each narrative must be one sentence (max 25 words) describing the PM's forecasting accuracy pattern."""


def _compute_pm_scores(week_start: date, weeks_back: int) -> List[Dict]:
    """Score each PM based on how accurately their forecasted users hit total hours.

    Joins PM→user assignments from ps_resource_forecasts to the pre-computed
    per-user pct_achieved in ai_forecast_analysis. Avoids project-name matching
    (forecast sheet names often differ from Clockify names); what matters is
    whether each resource worked the total hours they were forecast across all projects.

    Score per user = LEAST(ABS(pct_achieved - 100), 100)  (capped at 100)
    PM score       = GREATEST(0, 100 - AVG(per-user capped deviation))

    PM name normalisation consolidates known variants (Momina / Momina Tasawar Qureshi).
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ['DATABASE_URL'])
    start_date = week_start - timedelta(weeks=weeks_back)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                WITH pm_users AS (
                    SELECT DISTINCT
                        CASE
                            WHEN LOWER(f.pm_name) LIKE '%momina%' THEN 'Momina Tasawar Qureshi'
                            ELSE f.pm_name
                        END AS pm_name,
                        f.user_name
                    FROM ps_resource_forecasts f
                    WHERE f.week_start_date >= :start
                      AND f.week_start_date < :end
                      AND f.pm_name IS NOT NULL AND f.pm_name != ''
                )
                SELECT
                    pm.pm_name,
                    COUNT(DISTINCT pm.user_name)                                               AS resources_forecasted,
                    COUNT(DISTINCT pm.user_name)                                               AS projects_forecasted,
                    ROUND(SUM(a.total_forecasted_hours)::numeric, 1)                           AS total_forecasted,
                    ROUND(SUM(a.total_actual_hours)::numeric, 1)                               AS total_actual,
                    ROUND((SUM(a.total_actual_hours) / NULLIF(SUM(a.total_forecasted_hours), 0) * 100)::numeric, 1) AS overall_pct,
                    ROUND(GREATEST(0, 100 - AVG(
                        LEAST(ABS(COALESCE(a.pct_achieved, 0) - 100), 100)
                    ))::numeric, 1)                                                             AS accuracy_score
                FROM pm_users pm
                JOIN ai_forecast_analysis a
                    ON LOWER(a.user_name) = LOWER(pm.user_name)
                   AND a.week_start = :end
                GROUP BY pm.pm_name
                ORDER BY accuracy_score DESC
            """), {'start': start_date, 'end': week_start}).fetchall()
    finally:
        engine.dispose()

    return [dict(r._mapping) for r in rows]


def _call_bedrock_pm_narratives(pm_rows: List[Dict], start_date: date, week_start: date) -> Dict[str, str]:
    """Call Bedrock to generate a one-sentence narrative for each PM."""
    lines = [
        f"Analysis period: {start_date} to {week_start}",
        "",
        "PM Forecast Accuracy Data:",
        f"{'PM':<28} {'Res':>4} {'Proj':>5} {'Fcst':>8} {'Act':>8} {'Pct%':>7} {'Score':>7}",
        "-" * 75,
    ]
    for r in pm_rows:
        pct_str = f"{float(r['overall_pct']):.1f}%" if r.get('overall_pct') is not None else "N/A"
        lines.append(
            f"{str(r['pm_name']):<28} {int(r['resources_forecasted']):>4} "
            f"{int(r['projects_forecasted']):>5} {float(r['total_forecasted']):>8.1f} "
            f"{float(r['total_actual']):>8.1f} {pct_str:>7} {float(r['accuracy_score']):>7.1f}"
        )

    user_message = (
        "You are a resource planning analyst. "
        "For each project manager below, write a single concise sentence (max 25 words) "
        "describing their forecast accuracy pattern — mention whether they tend to over- or under-forecast, "
        "and whether the variance is consistent or variable across their assignments.\n\n"
        + "\n".join(lines)
        + "\n\n"
        + _PM_NARRATIVE_SCHEMA
    )

    raw = _call_bedrock(user_message)
    try:
        result = _parse_json(raw)
        return result.get('pm_narratives', {})
    except Exception as exc:
        print(f"[FORECAST] PM narrative parse error: {exc}")
        return {}


def _upsert_pm_scores(
    pm_rows: List[Dict],
    narratives: Dict[str, str],
    week_start: date,
    weeks_analyzed: int,
) -> None:
    """Upsert PM forecast accuracy scores and narratives."""
    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ['DATABASE_URL'])
    now = datetime.now()

    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM ai_pm_forecast_accuracy WHERE week_start = :ws"
        ), {'ws': week_start})

        for r in pm_rows:
            narrative = None
            for key, val in narratives.items():
                if key.lower() == str(r['pm_name']).lower():
                    narrative = val
                    break

            conn.execute(text("""
                INSERT INTO ai_pm_forecast_accuracy
                    (week_start, weeks_analyzed, pm_name,
                     project_resource_combos, resources_forecasted,
                     total_forecasted, total_actual, overall_pct,
                     accuracy_score, narrative, analyzed_at)
                VALUES
                    (:ws, :wa, :pm,
                     :combos, :res,
                     :fcst, :act, :pct,
                     :score, :narrative, :at)
            """), {
                'ws': week_start,
                'wa': weeks_analyzed,
                'pm': r['pm_name'],
                'combos': int(r['projects_forecasted']),
                'res': int(r['resources_forecasted']),
                'fcst': float(r['total_forecasted']),
                'act': float(r['total_actual']),
                'pct': float(r['overall_pct']) if r.get('overall_pct') is not None else None,
                'score': float(r['accuracy_score']),
                'narrative': narrative,
                'at': now,
            })

    engine.dispose()


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def _upsert(
    all_rows: List[Dict],
    bedrock_result: Dict,
    week_start: date,
    weeks_analyzed: int,
) -> None:
    """Delete existing rows for this week_start and insert fresh results."""
    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ['DATABASE_URL'])
    now = datetime.now()

    # Build user_notes lookup from Bedrock response
    user_notes: Dict[str, str] = bedrock_result.get('user_notes', {})
    # Also support old by_user array format as fallback
    for row in bedrock_result.get('by_user', []):
        name = row.get('user_name', '')
        if name and name not in user_notes:
            user_notes[name] = row.get('notes', '')

    status_counts: Dict[str, int] = {}

    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM ai_forecast_analysis WHERE week_start = :ws"
        ), {'ws': week_start})
        conn.execute(text(
            "DELETE FROM ai_forecast_summary WHERE week_start = :ws"
        ), {'ws': week_start})

        for r in all_rows:
            fcst = float(r.get('total_forecasted') or 0)
            act = float(r.get('total_actual') or 0)
            pct = r.get('pct_achieved')
            var = float(r.get('variance') or 0)
            status = _compute_status(fcst, act, pct)
            status_counts[status] = status_counts.get(status, 0) + 1

            # Case-insensitive note lookup
            note = None
            for key, val in user_notes.items():
                if key.lower() == str(r['user_name']).lower():
                    note = val
                    break

            conn.execute(text("""
                INSERT INTO ai_forecast_analysis
                    (week_start, weeks_analyzed, user_name, location, employment_designation,
                     total_forecasted_hours, total_actual_hours, variance_hours,
                     pct_achieved, status, notes, analyzed_at)
                VALUES
                    (:ws, :wa, :user, :loc, :emp,
                     :fcst, :act, :var,
                     :pct, :status, :notes, :at)
            """), {
                'ws': week_start,
                'wa': weeks_analyzed,
                'user': r['user_name'],
                'loc': r.get('location'),
                'emp': r.get('employment_designation'),
                'fcst': fcst,
                'act': act,
                'var': var,
                'pct': float(pct) if pct is not None else None,
                'status': status,
                'notes': note,
                'at': now,
            })

        key_obs = '\n'.join(bedrock_result.get('key_observations', []))
        recs = '\n'.join(bedrock_result.get('recommendations', []))

        conn.execute(text("""
            INSERT INTO ai_forecast_summary
                (week_start, weeks_analyzed, total_resources,
                 on_track_count, over_count, under_count, critical_under_count,
                 no_actuals_count, unforecasted_count,
                 key_observations, recommendations, analyzed_at)
            VALUES
                (:ws, :wa, :total,
                 :on_track, :over, :under, :crit,
                 :no_act, :unfcst,
                 :obs, :recs, :at)
        """), {
            'ws': week_start,
            'wa': weeks_analyzed,
            'total': len(all_rows),
            'on_track': status_counts.get('On Track', 0),
            'over': status_counts.get('Over', 0),
            'under': status_counts.get('Under', 0),
            'crit': status_counts.get('Critical Under', 0),
            'no_act': status_counts.get('No Actuals', 0),
            'unfcst': status_counts.get('Unforecasted', 0),
            'obs': key_obs,
            'recs': recs,
            'at': now,
        })

    engine.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_forecast_analysis(week_start: date = None, weeks_back: int = 4) -> Dict:
    """Run forecast vs actuals analysis and store results.

    Status is computed programmatically for all users. Bedrock is called only
    to annotate notable (non-on-track) users and produce overall observations
    and recommendations.

    Args:
        week_start: Anchor Monday (defaults to last Monday).
        weeks_back: Number of weeks of data to include (default 4 = 1 month).

    Returns:
        Summary dict with row counts and status breakdown.
    """
    if week_start is None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

    start_date = week_start - timedelta(weeks=weeks_back)
    print(f"[FORECAST] Analysing {weeks_back} weeks: {start_date} → {week_start}")

    # 1. Fetch data
    all_rows = _fetch_forecast_data(week_start, weeks_back)
    if not all_rows:
        print("[FORECAST] No forecast data found — skipping")
        return {'skipped': 'no data'}

    print(f"[FORECAST] {len(all_rows)} users to analyse")

    # 2. Load prompt
    prompt = _load_prompt()
    if not prompt:
        print("[FORECAST] No active prompt for category=FORECAST — skipping")
        return {'skipped': 'no prompt configured'}

    # 3. Select notable users for Bedrock annotation (exclude On Track)
    notable = [
        r for r in all_rows
        if _compute_status(
            float(r.get('total_forecasted') or 0),
            float(r.get('total_actual') or 0),
            r.get('pct_achieved'),
        ) != 'On Track'
    ]
    # Cap at 40 to keep prompt manageable
    notable = notable[:40]
    print(f"[FORECAST] {len(notable)} notable users for Bedrock annotation")

    # 4. Format and call Bedrock
    data_block = _format_notable_for_bedrock(all_rows, notable, start_date, week_start)
    user_message = f"""{prompt}

## Dataset Summary

{data_block}

## Output Schema

{_JSON_SCHEMA}"""

    print("[FORECAST] Calling Bedrock...")
    raw = _call_bedrock(user_message)

    # 5. Parse response
    try:
        result = _parse_json(raw)
    except Exception as exc:
        print(f"[FORECAST] JSON parse error: {exc}\nRaw response:\n{raw[:500]}")
        raise

    print(f"[FORECAST] Bedrock returned {len(result.get('user_notes', {}))} user notes, "
          f"{len(result.get('key_observations', []))} observations")

    # 6. Upsert — status computed for ALL users, notes from Bedrock where available
    _upsert(all_rows, result, week_start, weeks_back)
    print(f"[FORECAST] Saved {len(all_rows)} user rows to database")

    # 7. PM forecast accuracy scores + Bedrock narratives
    pm_rows = _compute_pm_scores(week_start, weeks_back)
    print(f"[FORECAST] {len(pm_rows)} PMs for accuracy scoring")
    if pm_rows:
        pm_narratives = _call_bedrock_pm_narratives(pm_rows, start_date, week_start)
        print(f"[FORECAST] Bedrock returned {len(pm_narratives)} PM narratives")
        _upsert_pm_scores(pm_rows, pm_narratives, week_start, weeks_back)
        print(f"[FORECAST] Saved {len(pm_rows)} PM accuracy rows to database")

    # Return summary
    status_counts: Dict[str, int] = {}
    for r in all_rows:
        s = _compute_status(
            float(r.get('total_forecasted') or 0),
            float(r.get('total_actual') or 0),
            r.get('pct_achieved'),
        )
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        'week_start': str(week_start),
        'weeks_analyzed': weeks_back,
        'user_rows': len(all_rows),
        'status_counts': status_counts,
        'observations': len(result.get('key_observations', [])),
        'recommendations': len(result.get('recommendations', [])),
    }
