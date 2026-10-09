ALTER TABLE incidents ADD COLUMN original_transcript TEXT;
ALTER TABLE incidents ADD COLUMN recording_path TEXT;
ALTER TABLE incidents ADD COLUMN recording_content_type TEXT;
ALTER TABLE incidents ADD COLUMN recording_duration_seconds INTEGER;
