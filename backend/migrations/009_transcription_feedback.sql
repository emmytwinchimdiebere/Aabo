ALTER TABLE incidents ADD COLUMN training_consent INTEGER NOT NULL DEFAULT 0;
ALTER TABLE incidents ADD COLUMN training_review_status TEXT NOT NULL DEFAULT 'not_requested';

CREATE INDEX idx_incidents_training_feedback
    ON incidents(training_consent, training_review_status, created_at DESC);
