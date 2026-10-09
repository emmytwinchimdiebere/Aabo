CREATE TABLE text_reports (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    channel TEXT NOT NULL,
    sender_hash TEXT NOT NULL,
    recipient TEXT NOT NULL,
    body TEXT NOT NULL,
    language TEXT,
    status TEXT NOT NULL DEFAULT 'received',
    acknowledgement_message_id TEXT,
    acknowledgement_status TEXT,
    failure_code TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_text_reports_status
    ON text_reports(status, created_at DESC);

CREATE INDEX idx_text_reports_acknowledgement
    ON text_reports(acknowledgement_message_id);
