#!/usr/bin/env python3
"""Seed ps_profitability_rates with confirmed placeholder values.

Rates: onshore=$150/hr, offshore=$35/hr, contractor=$120/hr, billable=$150/hr
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from src.database.config import engine
from sqlalchemy import text

with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO ps_profitability_rates (id, onshore_rate, offshore_rate, contractor_rate, billable_rate, updated_by)
        VALUES (1, 150.00, 35.00, 120.00, 150.00, 'seeded-2026-06-10')
        ON CONFLICT (id) DO UPDATE SET
            onshore_rate    = 150.00,
            offshore_rate   = 35.00,
            contractor_rate = 120.00,
            billable_rate   = 150.00,
            updated_at      = NOW(),
            updated_by      = 'seeded-2026-06-10'
    """))

print("✅ ps_profitability_rates seeded: onshore=$150, offshore=$35, contractor=$120, billable=$150")
