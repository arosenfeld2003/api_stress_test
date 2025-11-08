# PostgreSQL Migration Guide

This guide walks you through migrating from DuckDB to PostgreSQL for high-concurrency workloads.

## Why PostgreSQL?

- ✅ Handles 100+ concurrent writes easily
- ✅ Battle-tested for web APIs
- ✅ Rich ecosystem (monitoring, backups, replication)
- ✅ ACID compliant with proper MVCC
- ✅ Minimal SQL changes from DuckDB

## Prerequisites

### Option 1: Local PostgreSQL (Development)
```bash
# macOS with Homebrew
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb warrior_api

# Verify connection
psql warrior_api -c "SELECT version();"
```

### Option 2: Docker PostgreSQL (Recommended for Testing)
```bash
# Start PostgreSQL container
docker run -d \
  --name warrior-postgres \
  -e POSTGRES_DB=warrior_api \
  -e POSTGRES_USER=warrior \
  -e POSTGRES_PASSWORD=warrior_dev_password \
  -p 5432:5432 \
  postgres:15-alpine

# Verify
docker exec -it warrior-postgres psql -U warrior -d warrior_api -c "SELECT version();"
```

### Option 3: Managed PostgreSQL (Production)
- AWS RDS PostgreSQL
- Google Cloud SQL for PostgreSQL
- Azure Database for PostgreSQL
- DigitalOcean Managed PostgreSQL
- Neon (Serverless PostgreSQL)

## Step-by-Step Migration

### 1. Install Python Dependencies

```bash
# Add to requirements.txt
pip install psycopg2-binary==2.9.9  # or psycopg2 if you have PostgreSQL dev libs
pip install psycopg2-pool==1.1
```

### 2. Create PostgreSQL Schema

The schema is nearly identical to DuckDB:

```sql
-- schema_postgresql.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS warrior (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    dob DATE NOT NULL,
    fight_skills TEXT[] NOT NULL,  -- PostgreSQL native array type
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast searches
CREATE INDEX IF NOT EXISTS idx_warrior_name ON warrior USING gin(to_tsvector('english', name));
CREATE INDEX IF NOT EXISTS idx_warrior_dob ON warrior(dob);
CREATE INDEX IF NOT EXISTS idx_warrior_fight_skills ON warrior USING gin(fight_skills);
CREATE INDEX IF NOT EXISTS idx_warrior_created_at ON warrior(created_at DESC);

-- Full-text search index for combined search
CREATE INDEX IF NOT EXISTS idx_warrior_search ON warrior 
  USING gin(to_tsvector('english', name || ' ' || array_to_string(fight_skills, ' ')));
```

Apply schema:
```bash
psql -U warrior -d warrior_api -f schema_postgresql.sql
```

### 3. Update Connection Module

Create `src/db/connection_postgres.py`:

```python
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

class PostgreSQLConnectionPool:
    _instance: Optional[PostgreSQLConnectionPool] = None
    _pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pool is None:
            self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the connection pool."""
        # Connection parameters
        db_host = os.getenv("POSTGRES_HOST", "localhost")
        db_port = os.getenv("POSTGRES_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", "warrior_api")
        db_user = os.getenv("POSTGRES_USER", "warrior")
        db_password = os.getenv("POSTGRES_PASSWORD", "warrior_dev_password")
        
        # Pool sizing (adjust based on gunicorn workers)
        min_connections = int(os.getenv("DB_POOL_MIN", "10"))
        max_connections = int(os.getenv("DB_POOL_MAX", "100"))

        # Create DSN (connection string)
        dsn = f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"

        # Create threaded connection pool
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_connections,
            maxconn=max_connections,
            dsn=dsn,
            connect_timeout=10,
            options="-c statement_timeout=30000"  # 30 second query timeout
        )

        print(f"PostgreSQL connection pool initialized: {min_connections}-{max_connections} connections")

    @contextmanager
    def get_connection(self) -> Iterator[psycopg2.extensions.connection]:
        """Get a connection from the pool."""
        conn = None
        try:
            conn = self._pool.getconn()
            conn.autocommit = False  # Explicit transaction control
            yield conn
            conn.commit()  # Auto-commit on success
        except Exception as e:
            if conn:
                conn.rollback()  # Auto-rollback on error
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    def close_all(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()

# Global pool instance
_pool: Optional[PostgreSQLConnectionPool] = None

def get_pool() -> PostgreSQLConnectionPool:
    """Get or create the global connection pool."""
    global _pool
    if _pool is None:
        _pool = PostgreSQLConnectionPool()
    return _pool

@contextmanager
def get_pooled_connection() -> Iterator[psycopg2.extensions.connection]:
    """Get a connection from the global pool."""
    pool = get_pool()
    with pool.get_connection() as conn:
        yield conn
```

### 4. Update Warrior Data Access Layer

Modify `src/db/warrior_postgres.py`:

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

def create_warrior(
    con: psycopg2.extensions.connection,
    *,
    id: str,
    name: str,
    dob: str,
    fight_skills: List[str],
) -> None:
    """Insert a new warrior."""
    with con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO warrior (id, name, dob, fight_skills)
            VALUES (%s, %s, %s, %s)
            """,
            (id, name, dob, fight_skills)
        )
    # Connection context manager handles commit

def get_warrior(
    con: psycopg2.extensions.connection, 
    *, 
    id: str
) -> Optional[Dict[str, Any]]:
    """Get warrior by ID."""
    with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT 
                id::TEXT,
                name,
                dob::TEXT,
                fight_skills,
                created_at
            FROM warrior
            WHERE id = %s::UUID
            """,
            (id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

def search_warriors(
    con: psycopg2.extensions.connection, 
    *, 
    term: str, 
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Search warriors by term (optimized with full-text search)."""
    with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Use PostgreSQL's powerful full-text search
        cur.execute(
            """
            SELECT 
                id::TEXT,
                name,
                dob::TEXT,
                fight_skills
            FROM warrior
            WHERE 
                name ILIKE %s
                OR dob::TEXT ILIKE %s
                OR %s = ANY(fight_skills)
                OR EXISTS (
                    SELECT 1 FROM unnest(fight_skills) AS skill
                    WHERE skill ILIKE %s
                )
            ORDER BY 
                CASE 
                    WHEN name ILIKE %s THEN 1
                    WHEN dob::TEXT ILIKE %s THEN 2
                    ELSE 3 
                END,
                name
            LIMIT %s
            """,
            (
                f'%{term}%',  # name search
                f'%{term}%',  # dob search
                term,         # exact skill match
                f'%{term}%',  # skill substring match
                f'%{term}%',  # order by name match
                f'%{term}%',  # order by dob match
                limit
            )
        )
        return [dict(row) for row in cur.fetchall()]

def count_warriors(con: psycopg2.extensions.connection) -> int:
    """Count all warriors."""
    with con.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM warrior")
        return cur.fetchone()[0]
```

### 5. Update Environment Variables

Create/update `.env`:

```bash
# Database mode
DB_MODE=postgresql

# PostgreSQL connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=warrior_api
POSTGRES_USER=warrior
POSTGRES_PASSWORD=warrior_dev_password

# Connection pool sizing (adjust based on load)
DB_POOL_MIN=20
DB_POOL_MAX=100

# Gunicorn can now use more workers!
GUNICORN_WORKERS=auto  # Will use (CPU * 2 + 1)
```

### 6. Update Routes (Minimal Changes)

The route code needs minimal changes - just import the new connection module:

```python
# src/routes/warrior_routes.py
from src.db.connection_postgres import get_pooled_connection  # Changed import
from src.db.warrior_postgres import (  # Changed import
    create_warrior,
    get_warrior,
    search_warriors,
    count_warriors,
)

# Rest of the code stays the same!
```

### 7. Migrate Data (If Needed)

If you have existing data in DuckDB:

```python
# scripts/migrate_duckdb_to_postgres.py
import duckdb
import psycopg2
from src.db.connection_postgres import get_pooled_connection

def migrate():
    # Read from DuckDB
    duck_con = duckdb.connect('./data/app.duckdb')
    warriors = duck_con.execute("""
        SELECT 
            CAST(id AS TEXT) as id,
            name,
            strftime(dob, '%Y-%m-%d') as dob,
            fight_skills
        FROM warrior
    """).fetchall()
    
    # Write to PostgreSQL
    with get_pooled_connection() as pg_con:
        with pg_con.cursor() as cur:
            for warrior in warriors:
                cur.execute("""
                    INSERT INTO warrior (id, name, dob, fight_skills)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, warrior)
        pg_con.commit()
    
    print(f"Migrated {len(warriors)} warriors")

if __name__ == "__main__":
    migrate()
```

### 8. Update Gunicorn Config

Restore full worker count:

```python
# gunicorn_config.py
workers = multiprocessing.cpu_count() * 2 + 1  # Can handle it now!
timeout = 30  # Can reduce back to 30s
```

### 9. Test the Migration

```bash
# 1. Start PostgreSQL (if not already running)
docker start warrior-postgres  # or brew services start postgresql@15

# 2. Apply schema
psql -U warrior -d warrior_api -f schema_postgresql.sql

# 3. Migrate data (if needed)
python scripts/migrate_duckdb_to_postgres.py

# 4. Update environment
export DB_MODE=postgresql

# 5. Restart app
pkill gunicorn
gunicorn -c gunicorn_config.py "limiter:app"

# 6. Test basic operations
curl -X POST http://localhost:5001/warrior \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","dob":"1990-01-01","fight_skills":["sword"]}'

curl http://localhost:5001/counting-warriors

# 7. Run stress test
cd api_under_stress/stress-test
../deps/gatling-charts-highcharts-bundle-3.10.5/bin/gatling.sh -s EngLabStressTest
```

## Expected Performance Improvements

After migration:

| Metric | DuckDB | PostgreSQL |
|--------|--------|------------|
| Concurrent writes | ~2 | 100+ |
| Success rate @ 200 req/s | 13% | 95%+ |
| P95 latency | 21.9s | < 1s |
| P99 latency | 25.5s | < 2s |
| Worker timeouts | Common | Rare |
| 503 errors | 87% | < 1% |

## Production Considerations

### Connection Pooling
- Use PgBouncer for connection pooling between app and database
- Reduces connection overhead
- Allows more app connections than database connections

### Monitoring
```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity;

-- Long-running queries
SELECT pid, age(clock_timestamp(), query_start), usename, query 
FROM pg_stat_activity 
WHERE query != '<IDLE>' AND query NOT ILIKE '%pg_stat_activity%' 
ORDER BY query_start desc;

-- Cache hit rate (should be > 99%)
SELECT 
  sum(heap_blks_read) as heap_read,
  sum(heap_blks_hit)  as heap_hit,
  sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
FROM pg_statio_user_tables;
```

### Tuning
```sql
-- postgresql.conf adjustments for high concurrency
shared_buffers = 256MB              # 25% of RAM (for dedicated server)
effective_cache_size = 1GB          # 50-75% of RAM
work_mem = 4MB                       # Per operation
maintenance_work_mem = 64MB
max_connections = 200                # Adjust based on load
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1              # For SSD
effective_io_concurrency = 200      # For SSD
```

## Rollback Plan

If you need to rollback to DuckDB:

```bash
# 1. Stop application
pkill gunicorn

# 2. Export data from PostgreSQL
pg_dump -U warrior warrior_api --data-only --table=warrior > backup.sql

# 3. Change DB_MODE back to local
export DB_MODE=local

# 4. Restart with old config
gunicorn -c gunicorn_config_reduced.py "limiter:app"
```

## Summary

- ✅ PostgreSQL solves the core concurrency issue
- ✅ Minimal code changes required
- ✅ Can keep same API behavior
- ✅ Proven at scale
- ✅ Better tooling and monitoring
- ✅ Migration is straightforward

**Next Steps**: Start with Docker PostgreSQL locally, run stress tests, compare results, then proceed with production migration.

