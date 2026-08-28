-- Migration 067: ps_profitability_rates single-row config table
-- Stores hourly billing rates for PS profitability calculations.
-- BLOCKED: Actual rate values must be provided by business stakeholder.
-- Placeholder NULLs inserted until rates are confirmed.

CREATE TABLE IF NOT EXISTS ps_profitability_rates (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    onshore_rate    NUMERIC(10,2),
    offshore_rate   NUMERIC(10,2),
    contractor_rate NUMERIC(10,2),
    billable_rate   NUMERIC(10,2),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_by      VARCHAR(255),
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO ps_profitability_rates (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;
