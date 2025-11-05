-- Schema for API stress test logging and metrics

-- Request/response log
CREATE TABLE IF NOT EXISTS request_log (
    id TEXT PRIMARY KEY,
    ts TIMESTAMP DEFAULT now(),
    method TEXT,
    path TEXT,
    status INTEGER,
    latency_ms DOUBLE,
    client_ip TEXT,
    user_agent TEXT,
    payload_bytes BIGINT,
    error TEXT
);

-- Useful indexes for time-window queries
CREATE INDEX IF NOT EXISTS idx_request_log_ts ON request_log(ts);
CREATE INDEX IF NOT EXISTS idx_request_log_path ON request_log(path);
CREATE INDEX IF NOT EXISTS idx_request_log_method ON request_log(method);

-- Optional: pre-aggregated rollups (to be populated by background jobs)
CREATE TABLE IF NOT EXISTS metric_rollup (
    window_start TIMESTAMP,
    window_label TEXT, -- e.g. '1m', '5m'
    path TEXT,
    method TEXT,
    count BIGINT,
    p50_ms DOUBLE,
    p90_ms DOUBLE,
    p99_ms DOUBLE,
    error_rate DOUBLE,
    PRIMARY KEY (window_start, window_label, path, method)
);

-- Warriors domain data (for future API routes)
CREATE TABLE IF NOT EXISTS warrior (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    dob DATE NOT NULL,
    fight_skills TEXT[] NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_warrior_name ON warrior(name);
CREATE INDEX IF NOT EXISTS idx_warrior_dob ON warrior(dob);

-- Composite index for search queries (name, dob)
CREATE INDEX IF NOT EXISTS idx_warrior_name_dob ON warrior(name, dob);

-- GIN index for array search on fight_skills (DuckDB supports this)
-- This will help with ILIKE searches on array elements
