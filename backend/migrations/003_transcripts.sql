CREATE TABLE transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id),
    status TEXT NOT NULL,
    text TEXT,
    language TEXT,
    confidence REAL,
    provider TEXT,
    model TEXT,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transcripts_status ON transcripts(status, updated_at DESC);

