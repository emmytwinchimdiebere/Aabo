CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    phone_hash TEXT NOT NULL,
    language TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    language TEXT,
    language_confidence REAL,
    emergency_type TEXT,
    emergency_confidence REAL,
    gps_lat REAL,
    gps_lon REAL,
    gps_accuracy REAL,
    postcode TEXT,
    formatted_address TEXT,
    spoken_location TEXT,
    location_match TEXT,
    presence_score REAL,
    spoof_score REAL,
    spoof_signals TEXT,
    risk_level TEXT,
    transcript TEXT,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    dispatcher_status TEXT NOT NULL DEFAULT 'pending',
    confirmed_by TEXT,
    confirmed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS postcodes_cache (
    code TEXT PRIMARY KEY,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    state TEXT,
    lga TEXT,
    formatted_address TEXT,
    cached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_postcodes_geo ON postcodes_cache(lat, lon);
CREATE INDEX IF NOT EXISTS idx_incidents_status
    ON incidents(dispatcher_status, created_at DESC);

