-- 020_add_ai_analysis_tables.sql
-- Create tables for AI-driven Jira vs Clockify project health analysis

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_analysis_prompts'
    ) THEN
        CREATE TABLE ai_analysis_prompts (
            id              SERIAL PRIMARY KEY,
            category        VARCHAR(10)  NOT NULL,   -- 'PS' or 'MC'
            sequence_order  INTEGER      NOT NULL,
            prompt_text     TEXT         NOT NULL,
            is_active       BOOLEAN      DEFAULT TRUE,
            created_at      TIMESTAMP    DEFAULT NOW(),
            updated_at      TIMESTAMP    DEFAULT NOW()
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_analysis_by_user'
    ) THEN
        CREATE TABLE ai_analysis_by_user (
            id                      SERIAL PRIMARY KEY,
            week_start              DATE         NOT NULL,
            category                VARCHAR(10)  NOT NULL,
            project_name            VARCHAR(255),
            user_name               VARCHAR(255) NOT NULL,
            role                    VARCHAR(255),
            jira_issues             TEXT,
            jira_estimate_hours     FLOAT,
            clockify_actual_hours   FLOAT,
            delta                   FLOAT,
            verdict                 VARCHAR(50),
            notes                   TEXT,
            analyzed_at             TIMESTAMP    DEFAULT NOW()
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_analysis_by_project'
    ) THEN
        CREATE TABLE ai_analysis_by_project (
            id                          SERIAL PRIMARY KEY,
            week_start                  DATE         NOT NULL,
            category                    VARCHAR(10)  NOT NULL,
            project_name                VARCHAR(255) NOT NULL,
            team_size                   INTEGER,
            total_jira_estimate_hours   FLOAT,
            total_clockify_hours        FLOAT,
            total_delta                 FLOAT,
            verdict                     VARCHAR(50),
            notes                       TEXT,
            analyzed_at                 TIMESTAMP    DEFAULT NOW()
        );
    END IF;
END $$;

-- Seed default PS prompts (only if table is empty for PS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ai_analysis_prompts WHERE category = 'PS') THEN
        INSERT INTO ai_analysis_prompts (category, sequence_order, prompt_text) VALUES
        ('PS', 1, 'Review the Jira issues worked on last week across the Professional Services projects listed. For each issue and assignee, estimate the realistic engineering effort it would have taken — as if you are a technically savvy delivery manager who understands cloud infrastructure, application development, and professional services delivery. Base estimates on issue type, summary, complexity signals (story points, sub-tasks, status transitions), and engineering norms.'),
        ('PS', 2, 'Compare your Jira effort estimates against the Clockify time entries provided. Identify for each person: how many hours Jira activity suggests they should have logged, how many hours they actually logged in Clockify, the delta, and an honest assessment of alignment.'),
        ('PS', 3, 'This analysis covers Professional Services projects only. Exclude any entries that relate to Managed Services or Managed Cloud operations — those will be analysed separately. Focus purely on PS delivery work.'),
        ('PS', 4, 'Perform a final validation pass. Check for outliers — people with very high or very low deltas. Consider whether the Clockify entries make sense given the Jira activity. Assign a verdict per person and per project: On Track (within 20%), Over-logged (Clockify > estimate by >20%), Under-logged (Clockify < estimate by >20%), No Jira Activity, or No Clockify Activity.');
    END IF;
END $$;

-- Seed default MC prompts (only if table is empty for MC)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ai_analysis_prompts WHERE category = 'MC') THEN
        INSERT INTO ai_analysis_prompts (category, sequence_order, prompt_text) VALUES
        ('MC', 1, 'Review the Jira issues worked on last week across the Managed Cloud / Managed Services projects listed. For each issue and assignee, estimate the realistic engineering effort it would have taken — considering operational tasks, incident response, change requests, and ongoing managed service delivery work. Be realistic about the nature of operations work versus project delivery.'),
        ('MC', 2, 'Compare your Jira effort estimates against the Clockify time entries provided. Identify for each person: how many hours Jira activity suggests they should have logged, how many hours they actually logged in Clockify, the delta, and an honest assessment of alignment.'),
        ('MC', 3, 'This analysis covers Managed Cloud / Managed Services projects only. Exclude any Professional Services project delivery entries — those are analysed in a separate report. Focus on operational and managed service delivery work.'),
        ('MC', 4, 'Perform a final validation pass. Check for outliers — people with very high or very low deltas. Consider whether Clockify entries make sense given the Jira operational activity. Assign a verdict per person and per project: On Track (within 20%), Over-logged (Clockify > estimate by >20%), Under-logged (Clockify < estimate by >20%), No Jira Activity, or No Clockify Activity.');
    END IF;
END $$;
