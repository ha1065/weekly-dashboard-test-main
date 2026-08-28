-- Migration 052: Add clockify_project_type to vw_project_hours_by_assignment
-- Exposes the raw Clockify project type (Professional Services, Managed Cloud, etc.)
-- alongside the derived billing bucket (project_type: Billable/Mixed/etc.)

DROP VIEW IF EXISTS vw_project_hours_by_assignment;
CREATE OR REPLACE VIEW vw_project_hours_by_assignment AS
WITH

-- Tier 1: explicit ps_project_mapping entries
tier1 AS (
    SELECT DISTINCT ON (m.clockify_client_name, COALESCE(m.clockify_project_name, ''))
        m.ps_client_name                                                  AS canonical_client,
        m.clockify_client_name                                            AS cw_client,
        m.clockify_project_name                                           AS cw_project,
        m.category                                                        AS category,
        COALESCE(
            NULLIF(TRIM(COALESCE(m.pod_assignment, '')), ''),
            NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
                COALESCE(cp.pod_assignment,''),'{',''),'}',''),'"',''),'\','')), '')
        )                                                                 AS pod
    FROM ps_project_mapping m
    LEFT JOIN ps_project_status pss
           ON LOWER(pss.client_name) = LOWER(m.ps_client_name)
          AND pss.category = m.category
    LEFT JOIN clockify_projects cp
           ON LOWER(cp.client_name) = LOWER(m.clockify_client_name)
    WHERE m.is_active = TRUE
    ORDER BY m.clockify_client_name,
             COALESCE(m.clockify_project_name, ''),
             (m.ps_project_name IS NULL),
             m.id
),

-- Tier 2: direct client name match (no explicit mapping row)
tier2 AS (
    SELECT
        pss.client_name                                                   AS canonical_client,
        pss.client_name                                                   AS cw_client,
        NULL::TEXT                                                        AS cw_project,
        pss.category                                                      AS category,
        NULLIF(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
            COALESCE(cp.pod_assignment,''),'{',''),'}',''),'"',''),'\','')), '')       AS pod
    FROM ps_project_status pss
    LEFT JOIN clockify_projects cp
           ON LOWER(cp.client_name) = LOWER(pss.client_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM ps_project_mapping m2
        WHERE LOWER(m2.ps_client_name) = LOWER(pss.client_name)
          AND m2.category = pss.category
          AND m2.is_active = TRUE
    )
),

-- Combined mapping lookup
mapping AS (
    SELECT canonical_client, cw_client, cw_project, category, pod FROM tier1
    UNION ALL
    SELECT canonical_client, cw_client, cw_project, category, pod FROM tier2
),

-- Classify each time entry row
classified AS (
    SELECT
        DATE_TRUNC('week', te.entry_date)::DATE                           AS week_start,
        COALESCE(mp.canonical_client, te.client_name)                     AS customer_name,
        COALESCE(mp.category, 'Other')                                    AS category,
        COALESCE(mp.pod, 'N/A')                                           AS pod,
        te.client_name                                                    AS clockify_client,
        te.project_name,
        te.clockify_user_id,
        te.duration_hours,
        te.billable,
        cp.project_type                                                   AS clockify_project_type
    FROM clockify_detailed_time_entries te
    LEFT JOIN clockify_projects cp ON te.clockify_project_id = cp.clockify_project_id
    LEFT JOIN mapping mp
           ON LOWER(te.client_name) = LOWER(mp.cw_client)
          AND (mp.cw_project IS NULL OR LOWER(te.project_name) = LOWER(mp.cw_project))
    WHERE te.client_name IS NOT NULL
      AND te.duration_hours > 0
)

SELECT
    week_start,
    category,
    customer_name,
    pod,
    clockify_client,
    project_name,
    COUNT(DISTINCT clockify_user_id)                                      AS resource_count,
    ROUND(SUM(duration_hours)::NUMERIC, 2)                                AS total_hours,
    ROUND(SUM(CASE WHEN billable  = TRUE  THEN duration_hours ELSE 0 END)::NUMERIC, 2) AS billable_hours,
    ROUND(SUM(CASE WHEN billable  = FALSE THEN duration_hours ELSE 0 END)::NUMERIC, 2) AS non_billable_hours,
    ROUND(SUM(CASE
        WHEN clockify_project_type IN ('Non Bill Productive', 'Overtime', 'Presales') THEN duration_hours
        WHEN clockify_project_type IS NULL AND billable = FALSE AND category <> 'Other' THEN duration_hours
        ELSE 0
    END)::NUMERIC, 2)                                                     AS non_billable_productive_hours,
    ROUND(SUM(CASE
        WHEN clockify_project_type = 'Non Bill Non Productive'                          THEN duration_hours
        WHEN clockify_project_type IS NULL AND billable = FALSE AND category  = 'Other' THEN duration_hours
        ELSE 0
    END)::NUMERIC, 2)                                                     AS non_billable_non_productive_hours,
    -- project_type: dominant billing nature of this project row
    CASE
        WHEN SUM(CASE WHEN billable = TRUE THEN duration_hours ELSE 0 END) > 0
             AND SUM(CASE WHEN billable = FALSE THEN duration_hours ELSE 0 END) = 0
             THEN 'Billable'
        WHEN SUM(CASE
                WHEN clockify_project_type IN ('Non Bill Productive', 'Overtime', 'Presales') THEN duration_hours
                WHEN clockify_project_type IS NULL AND billable = FALSE AND category <> 'Other' THEN duration_hours
                ELSE 0 END) > 0
             AND SUM(CASE WHEN billable = TRUE THEN duration_hours ELSE 0 END) = 0
             THEN 'Non-Billable Productive'
        WHEN SUM(CASE
                WHEN clockify_project_type = 'Non Bill Non Productive'                          THEN duration_hours
                WHEN clockify_project_type IS NULL AND billable = FALSE AND category  = 'Other' THEN duration_hours
                ELSE 0 END) > 0
             AND SUM(CASE WHEN billable = TRUE THEN duration_hours ELSE 0 END) = 0
             THEN 'Non-Billable Non-Productive'
        ELSE 'Mixed'
    END                                                                    AS project_type,
    -- clockify_project_type: raw Clockify project type (Professional Services, Managed Cloud, etc.)
    MAX(clockify_project_type)                                             AS clockify_project_type
FROM classified
GROUP BY
    week_start, category, customer_name, pod, clockify_client, project_name
ORDER BY
    week_start DESC, category, total_hours DESC;
