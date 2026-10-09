CREATE TABLE agent_conversations (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    phase TEXT NOT NULL,
    emergency_text TEXT,
    location_text TEXT,
    location_confidence REAL,
    location_source TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_conversations_phase
    ON agent_conversations(phase, updated_at DESC);
