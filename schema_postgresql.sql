-- PostgreSQL Schema for Warrior API
-- High-performance schema optimized for concurrent reads and writes

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main warrior table
CREATE TABLE IF NOT EXISTS warrior (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    dob DATE NOT NULL,
    fight_skills TEXT[] NOT NULL,  -- PostgreSQL native array type
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast searches
-- GIN index for full-text search on name
CREATE INDEX IF NOT EXISTS idx_warrior_name_trgm 
    ON warrior USING gin(name gin_trgm_ops);

-- B-tree index for date searches and sorting
CREATE INDEX IF NOT EXISTS idx_warrior_dob 
    ON warrior(dob);

-- GIN index for array containment searches on fight_skills
CREATE INDEX IF NOT EXISTS idx_warrior_fight_skills 
    ON warrior USING gin(fight_skills);

-- Compound index for recent warriors
CREATE INDEX IF NOT EXISTS idx_warrior_created_at 
    ON warrior(created_at DESC);

-- Enable pg_trgm extension for fuzzy text search (if not already enabled)
-- This significantly improves ILIKE performance
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Grant permissions (adjust user as needed)
-- GRANT ALL PRIVILEGES ON TABLE warrior TO warrior;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO warrior;

-- Performance settings recommendations (add to postgresql.conf):
-- shared_buffers = 256MB              # 25% of RAM for dedicated server
-- effective_cache_size = 1GB          # 50-75% of RAM
-- work_mem = 4MB                      # Per operation
-- maintenance_work_mem = 64MB         # For index creation/vacuum
-- max_connections = 200               # Adjust based on load
-- checkpoint_completion_target = 0.9
-- wal_buffers = 16MB
-- default_statistics_target = 100
-- random_page_cost = 1.1             # For SSD (default is 4 for HDD)
-- effective_io_concurrency = 200     # For SSD (default is 1)

-- Vacuum and analyze for optimal performance
VACUUM ANALYZE warrior;

-- Display table info
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE tablename = 'warrior';

