CREATE TABLE IF NOT EXISTS clockify_upload_logs (
    id              SERIAL PRIMARY KEY,
    uploaded_at     TIMESTAMP DEFAULT NOW(),
    uploaded_by     VARCHAR(255),
    file_name       VARCHAR(500),
    file_type       VARCHAR(50),
    records_total   INTEGER,
    records_updated INTEGER,
    records_skipped INTEGER,
    records_failed  INTEGER,
    detail          TEXT
);
