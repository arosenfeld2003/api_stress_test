# Stress Test Debugging Report

## Problem Summary
**87% error rate (5132 failures out of 5880 requests)** with response times degrading significantly.

## Root Cause Analysis

### 1. **All failures are 503 Service Unavailable errors**
```
REQUEST		creation	1762622560252	1762622560255	KO	status.find.in(201,422,400), but actually found 503
REQUEST		valid look up	1762622560351	1762622560354	KO	status.find.in([200, 209], 304), found 503
```

This means requests aren't even reaching your Flask application - they're being rejected upstream.

### 2. **Worker Timeouts and Connection Pool Exhaustion**
From `gunicorn_error.log`:
```
[2025-11-06 20:52:16 -0800] [58139] [CRITICAL] WORKER TIMEOUT (pid:58170)
File "/Users/alexrosenfeld/qwasar_mscs_25-26/api_stress_test/src/db/pool.py", line 68, in get_connection
    conn = self.pool.get(timeout=timeout)
```

Workers are timing out (30 second timeout) waiting for database connections from the pool.

### 3. **Out of Memory Kill**
```
[2025-11-06 21:54:53 -0800] [58139] [ERROR] Worker (pid:58755) was sent SIGKILL! Perhaps out of memory?
```

### 4. **DuckDB Write Contention - THE CORE ISSUE**

**DuckDB is a single-file embedded database with limited write concurrency.** Here's why it's failing:

1. **29 Gunicorn workers** (CPU count * 2 + 1) all trying to write simultaneously
2. **Each write operation calls `con.commit()`** which blocks (line 34 in `warrior.py`)
3. **DuckDB's WAL mode** doesn't provide true concurrent write access like PostgreSQL
4. **Connection pool has 40 max connections**, but DuckDB can only handle ~1-2 concurrent writers effectively
5. Workers pile up waiting for the write lock → timeout → 503 errors

## Key Metrics from Test

- **Load**: Ramping to 100 req/sec creates + 80 req/sec searches + 50 req/sec invalid
- **Peak concurrent load**: ~230 requests/second
- **Workers**: 29 sync workers (likely on a 10-14 core machine)
- **Database**: Single DuckDB file with WAL mode

## Why DuckDB Fails at Scale

DuckDB is designed for:
- Analytics workloads (OLAP)
- Single-process or low-concurrency scenarios
- Embedded applications

DuckDB is NOT designed for:
- High-concurrency transactional workloads (OLTP)
- Multiple processes writing simultaneously
- Web API backends under stress

From the DuckDB documentation:
> "DuckDB uses a optimistic concurrency control (MVCC) mechanism... Write-write conflicts will cause transactions to abort."

## Solutions (Ranked by Effectiveness)

### ✅ Solution 1: Switch to PostgreSQL (Recommended)
**Why**: Built for concurrent writes, proven at scale, battle-tested for web APIs

**Changes needed**:
```python
# Replace DuckDB with PostgreSQL + psycopg2 or asyncpg
# Use connection pooling (pgbouncer or built-in)
# Minimal code changes - same SQL queries mostly work
```

**Pros**:
- Handles hundreds of concurrent writes easily
- ACID compliance
- Rich indexing for fast searches
- Production-ready monitoring tools
- Familiar to most engineers

**Cons**:
- Need to run PostgreSQL server
- Slightly more complex setup

### ✅ Solution 2: Use Async Workers + Queue (Moderate)
**Why**: Decouple write operations from request handling

**Architecture**:
```
Client Request → Flask → Queue (Redis/RabbitMQ) → Background Worker → DuckDB
                    ↓
                Return 202 Accepted
```

**Changes needed**:
- Add Redis or RabbitMQ
- Use Celery or RQ for background tasks
- Change POST endpoints to return 202 (Accepted) instead of 201
- Add job status endpoint

**Pros**:
- Can keep DuckDB
- Better resilience
- Can batch writes

**Cons**:
- More complex architecture
- Eventual consistency (clients need to poll for status)
- Additional infrastructure

### ✅ Solution 3: Batch Writes + Write-Behind Cache (Complex)
**Why**: Reduce write frequency to DuckDB

**Architecture**:
```
Write Request → In-Memory Cache → Periodic Batch Flush (every 100ms) → DuckDB
Read Request → Check Cache + DuckDB
```

**Pros**:
- Can keep DuckDB
- Very fast write responses

**Cons**:
- Risk of data loss if cache crashes before flush
- Complex cache invalidation
- Not suitable for strict consistency requirements

### ❌ Solution 4: Multiple DuckDB Files (Not Recommended)
**Why**: Sharding across multiple DB files

**Issues**:
- Complex routing logic
- Cross-shard queries become difficult
- Still limited concurrency per shard
- Maintenance nightmare

## Immediate Quick Fixes (Stop-Gap Measures)

While you decide on the long-term solution, try these:

### A. Reduce Worker Count
```python
# gunicorn_config.py
workers = 4  # Instead of CPU * 2 + 1
worker_class = 'sync'
```
**Impact**: Reduces concurrent write contention, but lowers throughput

### B. Increase Connection Pool Timeout
```python
# src/db/pool.py, line 108
def get_connection(self, timeout: float = 60.0):  # Increased from 30
```
**Impact**: Workers wait longer instead of timing out, but doesn't fix root cause

### C. Remove Explicit Commits for Reads
```python
# src/db/warrior.py - only commit on writes, not reads
def create_warrior(...):
    con.execute(...)
    con.commit()  # Keep this

def get_warrior(...):
    return con.execute(...).fetchone()  # Remove commit if present

def search_warriors(...):
    return con.execute(...).fetchall()  # Remove commit if present
```

### D. Use Read-Only Connections for Reads
```python
# src/routes/warrior_routes.py
@warrior_bp.route('/warrior', methods=['GET'])
def search_warrior_endpoint():
    # Use read-only connection for searches
    with get_pooled_connection(read_only=True) as con:
        warriors = search_warriors(con, term=search_term, limit=50)
    return jsonify(warriors), 200
```

### E. Add Backpressure/Circuit Breaker
Return 503 earlier when system is overloaded instead of timing out:

```python
# Check pool health before processing
if pool.active_connections >= pool.max_connections * 0.9:
    return jsonify(error="Service overloaded"), 503
```

## Recommended Migration Path

### Phase 1: Immediate (Today)
1. Reduce Gunicorn workers to 4
2. Increase connection timeout to 60s
3. Ensure reads don't commit transactions
4. Add monitoring for connection pool utilization

### Phase 2: Short-term (Next Sprint)
1. Set up PostgreSQL (local or managed - RDS, Cloud SQL, etc.)
2. Migrate schema (straightforward, same SQL mostly)
3. Update connection pool to use psycopg2
4. Test under stress load
5. Compare metrics

### Phase 3: Long-term (If Needed)
1. Add Redis for caching hot reads
2. Consider async workers (Celery) for write-heavy endpoints
3. Add connection pooling proxy (PgBouncer)
4. Implement proper observability (Prometheus, Grafana)

## Expected Performance After Migration to PostgreSQL

With PostgreSQL + proper tuning:
- **Target**: 95%+ success rate at 200+ req/sec
- **Response times**: P95 < 100ms, P99 < 200ms
- **Write concurrency**: 100+ concurrent writes easily
- **Read concurrency**: 1000+ concurrent reads

## Testing After Changes

Run stress test and look for:
```bash
# Success rate should be > 95%
# P95 latency should be < 1000ms
# No worker timeouts
# No 503 errors (or < 1%)
```

## Monitoring Checklist

Add these metrics:
- [ ] Connection pool utilization (current/max)
- [ ] Database query duration (P50, P95, P99)
- [ ] Worker queue depth
- [ ] Request rate by endpoint
- [ ] Error rate by status code
- [ ] Database lock wait time

## References

- [DuckDB Concurrency](https://duckdb.org/docs/connect/concurrency)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Gunicorn Worker Types](https://docs.gunicorn.org/en/stable/design.html#async-workers)

---

**Bottom Line**: DuckDB is excellent for analytics but not suitable for high-concurrency web APIs. PostgreSQL is the right tool for this job.

