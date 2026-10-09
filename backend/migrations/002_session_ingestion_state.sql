ALTER TABLE sessions ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE sessions ADD COLUMN recording_duration_seconds INTEGER;
ALTER TABLE sessions ADD COLUMN recording_received_at TIMESTAMP;

