-- Migration 055: MC customer board tickets
-- Stores tickets imported from individual MC customer Jira project boards.
-- These are the actual managed services queue tickets linked from the CST board.
CREATE TABLE IF NOT EXISTS mc_customer_tickets (
    id                  SERIAL PRIMARY KEY,
    jira_issue_id       VARCHAR(50) NOT NULL,
    issue_key           VARCHAR(50) NOT NULL,
    jira_project_key    VARCHAR(50) NOT NULL,
    customer_name       VARCHAR(255),
    summary             VARCHAR(500),
    status              VARCHAR(100),
    status_category     VARCHAR(50),
    issue_type          VARCHAR(100),
    priority            VARCHAR(50),
    assignee_name       VARCHAR(255),
    story_points        NUMERIC(6,1),
    created_date        TIMESTAMP,
    updated_date        TIMESTAMP,
    resolution_date     TIMESTAMP,
    synced_at           TIMESTAMP DEFAULT NOW(),
    UNIQUE (jira_issue_id)
);

CREATE INDEX IF NOT EXISTS idx_mc_tickets_project  ON mc_customer_tickets(jira_project_key);
CREATE INDEX IF NOT EXISTS idx_mc_tickets_customer ON mc_customer_tickets(customer_name);
CREATE INDEX IF NOT EXISTS idx_mc_tickets_updated  ON mc_customer_tickets(updated_date);
CREATE INDEX IF NOT EXISTS idx_mc_tickets_status   ON mc_customer_tickets(status_category);

-- Seed MC_CUSTOMER prompt category if not already present
INSERT INTO ai_analysis_prompts (category, sequence_order, prompt_text, is_active)
VALUES (
    'MC_CUSTOMER',
    1,
    'You are analysing the managed services delivery health for a Cloudelligent MC customer.

You will be given:
1. The CST board health score set by the PM (Green/Amber/Red)
2. Tickets from the customer''s Jira project board this week (updated, closed, open)
3. Clockify hours charged to this customer this week
4. Any open escalations

Assess the customer''s delivery health for the week and provide:
- overall_health: Green / Amber / Red
- tickets_closed: count of tickets moved to Done this week
- tickets_updated: count of tickets with activity this week
- delivery_narrative: 2-3 sentences on delivery status and any risks
- recommendation: one actionable recommendation for the delivery team

Respond in JSON only:
{
  "overall_health": "Green|Amber|Red",
  "tickets_closed": <int>,
  "tickets_updated": <int>,
  "delivery_narrative": "<string>",
  "recommendation": "<string>"
}',
    TRUE
)
ON CONFLICT DO NOTHING;
