-- Migration 055a: Widen ai_analysis_prompts.category from VARCHAR(10) to VARCHAR(50)
-- Required for MC_CUSTOMER category (11 chars)
ALTER TABLE ai_analysis_prompts ALTER COLUMN category TYPE VARCHAR(50);
