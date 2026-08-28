"""Escalations handler module.

Modes handled:
  - run_escalations_import  – DDL + Jira ES board import + QuickSight refresh
"""

import json
import os
from typing import Any


def run_escalations_import(event: dict, context: Any, secrets: dict) -> dict:
    """Create escalations table/views and import ES Jira board data."""
    # Heavy imports inside function — secrets must already be in os.environ
    from sqlalchemy import create_engine, text as sa_text
    from src.integrations.import_escalations import run_escalations_import as _run_esc_import
    from src.handlers.quicksight import refresh_quicksight_datasets

    db_url = os.environ.get('DATABASE_URL')
    engine = create_engine(db_url)
    ddl = """
        CREATE TABLE IF NOT EXISTS escalations (
            id                  SERIAL PRIMARY KEY,
            jira_issue_id       VARCHAR(50) UNIQUE NOT NULL,
            issue_key           VARCHAR(50) NOT NULL,
            customer_name       VARCHAR(255),
            epic_key            VARCHAR(50),
            epic_summary        VARCHAR(500),
            summary             VARCHAR(500),
            status              VARCHAR(100),
            status_category     VARCHAR(50),
            priority            VARCHAR(50),
            assignee_name       VARCHAR(255),
            reporter_name       VARCHAR(255),
            created_date        TIMESTAMP,
            updated_date        TIMESTAMP,
            resolution_date     TIMESTAMP,
            days_open           INTEGER,
            days_to_resolve     INTEGER,
            synced_at           TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_escalations_customer ON escalations(customer_name);
        CREATE INDEX IF NOT EXISTS idx_escalations_status   ON escalations(status_category);
        CREATE INDEX IF NOT EXISTS idx_escalations_created  ON escalations(created_date);
        CREATE OR REPLACE VIEW vw_escalations AS
        SELECT issue_key, customer_name, epic_key, summary, status, status_category,
               priority, assignee_name, reporter_name,
               created_date::date AS created_date, updated_date::date AS updated_date,
               resolution_date::date AS resolution_date,
               days_open, days_to_resolve,
               EXTRACT(YEAR FROM created_date)::int  AS created_year,
               EXTRACT(MONTH FROM created_date)::int AS created_month,
               TO_CHAR(created_date, 'YYYY-MM')      AS created_month_label,
               CASE WHEN status_category = 'Done'        THEN 'Resolved'
                    WHEN status_category = 'In Progress' THEN 'Active'
                    ELSE 'Open' END                   AS escalation_state
        FROM escalations WHERE customer_name IS NOT NULL;
        CREATE OR REPLACE VIEW vw_escalations_by_customer AS
        SELECT customer_name,
               COUNT(*)                                                                  AS total_escalations,
               COUNT(*) FILTER (WHERE status_category != 'Done')                        AS open_escalations,
               COUNT(*) FILTER (WHERE status_category = 'Done')                         AS resolved_escalations,
               COUNT(*) FILTER (WHERE priority IN ('High','Highest'))                   AS high_priority_count,
               ROUND(AVG(days_to_resolve) FILTER (WHERE days_to_resolve IS NOT NULL),1) AS avg_days_to_resolve,
               ROUND(AVG(days_open)       FILTER (WHERE days_open IS NOT NULL),1)       AS avg_days_open,
               MAX(created_date)::date AS most_recent_escalation,
               MIN(created_date)::date AS first_escalation
        FROM escalations WHERE customer_name IS NOT NULL GROUP BY customer_name;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
    """
    with engine.begin() as conn:
        for stmt in [s.strip() for s in ddl.split(';') if s.strip()]:
            conn.execute(sa_text(stmt))
    print("Escalations DDL applied")

    esc_result = _run_esc_import()
    print(f"Escalations import result: {esc_result}")
    refresh_quicksight_datasets(['escalations-detail', 'escalations-by-customer'])

    return {
        'statusCode': 200,
        'body': json.dumps({'escalations': esc_result})
    }
