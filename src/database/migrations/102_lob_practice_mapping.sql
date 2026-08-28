-- Migration 102: Line of Business to Practice Alignment mapping table
-- Replaces practice_area enum as the LoB classification source.
-- LoB is derived from practice_alignment via this lookup table.
-- Managed by Cloudelligent admins via Streamlit Settings editor.
-- Fallback: any practice_alignment not in this table maps to 'Internal'.
CREATE TABLE IF NOT EXISTS lob_practice_mapping (
    id                  SERIAL PRIMARY KEY,
    practice_alignment  VARCHAR(200) NOT NULL UNIQUE,
    line_of_business    VARCHAR(100) NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lob_practice_alignment
    ON lob_practice_mapping(practice_alignment);

INSERT INTO lob_practice_mapping (practice_alignment, line_of_business) VALUES
    ('AI/ML',                                    'Professional Services'),
    ('App Dev/App Mod',                           'Professional Services'),
    ('Migration,WAFR',                            'Professional Services'),
    ('Migration, WAFR',                           'Professional Services'),
    ('Migration',                                 'Professional Services'),
    ('Project Management',                        'Professional Services'),
    ('FINOPs',                                    'FINOPs'),
    ('Managed Cloud Services',                    'Managed Cloud'),
    ('Managed Cloud Services,Migration,WAFR',     'Managed Cloud'),
    ('Managed Cloud Services, Migration, WAFR',   'Managed Cloud'),
    ('Managed Cloud Services,WAFR',               'Managed Cloud'),
    ('Managed Cloud Services, WAFR',              'Managed Cloud'),
    ('IT',                                        'Managed IT'),
    ('Product',                                   'Product')
ON CONFLICT (practice_alignment) DO UPDATE
    SET line_of_business = EXCLUDED.line_of_business,
        updated_at = NOW();
