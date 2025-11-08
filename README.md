# Warrior API - High-Performance REST API

Qwasar MSCS Engineering Lab - Project 2

A production-ready Flask-based REST API for managing warriors with PostgreSQL, connection pooling, rate limiting, and comprehensive stress testing.

## Performance Achievements

**99.8% success rate** at 107+ req/sec with sub-100ms response times after optimizing for high-concurrency workloads.

| Metric | Initial (DuckDB) | Final (PostgreSQL) | Improvement |
|--------|-----------------|-------------------|-------------|
| Success Rate | 12.6% ❌ | **99.8% ✅** | **+87.2% (8x)** |
| P95 Latency | 12.8s ❌ | **66ms ✅** | **-99.5% (194x faster)** |
| Throughput | 76 req/s | **107 req/s ✅** | **+40%** |

📖 **[Read the full performance journey →](DEBUGGING_REPORT.md)**

## Overview

This project demonstrates a production-ready API with:
- **Flask REST API** for warrior CRUD operations
- **PostgreSQL** with connection pooling for high-concurrency workloads
- **DuckDB support** (kept for analytics and comparative testing)
- **Rate limiting** to protect against abuse
- **Gatling stress testing** with detailed analysis tools

## Features

- **REST API**: Create, read, search, and count warriors
- **High-Performance Database**: PostgreSQL with optimized connection pooling
- **Dual Database Support**: PostgreSQL for production, DuckDB for analytics/testing
- **Connection Pooling**: Handles 100+ concurrent connections efficiently  
- **Rate Limiting**: Nginx + application-level protection
- **Stress Testing**: Gatling-based load testing with analysis tools
- **Comprehensive Documentation**: Performance analysis, migration guides, and lessons learned

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Java (for Gatling stress tests)
brew install openjdk@11

# Install sbt (Scala Build Tool)
brew install sbt
```

### 2. Set Up Database

**Option A: PostgreSQL (Recommended for Production)**

Automated setup with Docker:
```bash
./scripts/setup_postgres.sh
```

Or manually:
```bash
# Start PostgreSQL
docker-compose up -d postgres

# Configure environment
cp .env.example .env
# Edit .env: Set DB_MODE=postgresql
```

**Option B: DuckDB (For Analytics/Testing)**

Create a `.env` file:
```bash
DB_MODE=local
LOCAL_DUCKDB_PATH=./data/app.duckdb
```

**Option C: MotherDuck Cloud (Analytics)**

```bash
DB_MODE=motherduck
MOTHERDUCK_TOKEN=your_token_here
MOTHERDUCK_DATABASE=my_db
```

### 3. Run the API

```bash
python3 limiter.py
```

The API runs on `http://localhost:5001`.

### 4. Test the API

**Basic connectivity test:**
```bash
./scripts/test_rate_limit.sh
```

**Stress test with Gatling:**
```bash
cd api_under_stress/stress-test
./run-test.sh
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check (returns `{"status": "ok"}`) |
| POST | `/warrior` | Create a warrior (returns 201 with Location header) |
| GET | `/warrior/{id}` | Get warrior by UUID (returns 200 or 404) |
| GET | `/warrior?t={term}` | Search warriors (returns array of warriors) |
| GET | `/counting-warriors` | Count total warriors (returns `{"count": N}`) |

### Example: Create a Warrior

```bash
curl -X POST http://localhost:5001/warrior \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Master Yoda",
    "dob": "1970-01-01",
    "fight_skills": ["BJJ", "KungFu", "Judo"]
  }'
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Master Yoda",
  "dob": "1970-01-01",
  "fight_skills": ["BJJ", "KungFu", "Judo"]
}
```

## Testing

### Basic Rate Limit Test

```bash
# Test with default settings (20 requests to /health)
./scripts/test_rate_limit.sh

# Custom endpoint and request count
./scripts/test_rate_limit.sh http://localhost:5001/counting-warriors 50

# Slower requests (not rapid fire)
./scripts/test_rate_limit.sh http://localhost:5001/health 20 slow
```

The script verifies:
- Database connectivity before running tests
- API endpoint availability
- Response times and success rates

### Stress Testing with Gatling

**Requirements:** Nginx container must be running for dual-layer rate limiting.

**Setup (one-time):**

```bash
# 1. Ensure nginx container is running
docker ps | grep nginx

# 2. Deploy local nginx config (no SSL, allows HTTP on port 80)
./scripts/deploy_nginx_config.sh api_stress_test_nginx nginx.conf.local
```

**Run Stress Tests:**

```bash
# Terminal 1: Start Flask with optimized settings
./scripts/start_for_stress_test.sh

# Terminal 2: Run Gatling stress tests (they connect via nginx on port 80)
cd api_under_stress/stress-test
./run-test.sh

# View results (HTML reports generated in user-files/results/)
```

**Architecture:** `Gatling` → `Nginx:80` (1000 req/s limit) → `Flask:5001` (10,000 req/s limit)

The optimized startup script sets:
- **Connection Pool**: 50 connections (max 100)
- **Rate Limit**: 600,000 req/min (10,000 req/s)
- **Threading**: Enabled for better concurrency
- **IP Blocking**: Localhost whitelisted

The Gatling simulation tests:
- All warrior API endpoints through nginx
- Dual-layer rate limiting validation (nginx + Flask)
- Multiple load scenarios (warm-up, ramp-up to 100 users/sec)
- Response time analysis under load
- Concurrent user simulation (~3 minute test duration)

## Database Configuration

### Local DuckDB (Default)

No configuration needed. The database file is created at `./data/app.duckdb`.

### MotherDuck Cloud

Set environment variables in `.env` file:

```bash
# Database mode
DB_MODE=motherduck

# MotherDuck authentication
MOTHERDUCK_TOKEN=your_token_here

# Database name (optional, uses default if not set)
MOTHERDUCK_DATABASE=my_db

# Connection pool settings (optional)
DB_POOL_SIZE=20
DB_MAX_CONNECTIONS=40
```

### Database Health Check

The application automatically verifies database connectivity on startup:
- Tests connection pool initialization
- Executes test query to verify database works
- Exits with clear error if database is unavailable

Manual diagnostic:
```bash
python diagnose_db.py
```

## Rate Limiting

Configurable via environment variable:

```bash
# Set rate limit (requests per minute)
FLASK_RATE_LIMIT=120000  # 2000 req/s

# Run the app
python limiter.py
```

Default: 120,000 requests per minute (2000 req/s) per IP address.

When rate limit is exceeded, the API returns:
- **Status**: 429 Too Many Requests
- **Body**: `{"error": "Rate limit exceeded", "message": "..."}`

## Project Structure

```
api_stress_test/
├── README.md                            # This file
├── limiter.py                           # Flask app entry point
├── requirements.txt                     # Python dependencies  
├── docker-compose.yml                   # PostgreSQL + pgAdmin setup
├── schema_postgresql.sql                # PostgreSQL schema with indexes
├── .env                                 # Environment config (create this)
│
├── Documentation/
│   ├── DEBUGGING_REPORT.md              # Performance analysis & problem diagnosis
│   ├── POSTGRESQL_MIGRATION.md          # Complete PostgreSQL migration guide
│   ├── PERFORMANCE_TUNING_SUMMARY.md    # Full comparison & lessons learned
│   └── QUICK_START.md                   # Quick reference guide
│
├── src/
│   ├── db/
│   │   ├── adapter.py                   # Universal DB adapter (switches DB based on mode)
│   │   ├── connection_postgres.py       # PostgreSQL connection pool (production)
│   │   ├── warrior_postgres.py          # PostgreSQL data access (production)
│   │   ├── connection.py                # DuckDB connection (analytics/testing)
│   │   ├── pool.py                      # DuckDB pool (analytics/testing)
│   │   ├── warrior.py                   # DuckDB data access (analytics/testing)
│   │   └── schema.sql                   # DuckDB schema
│   ├── routes/
│   │   └── warrior_routes.py            # API endpoints
│   └── security/
│       └── ip_blocker.py                # IP blocking/abuse detection
│
├── scripts/
│   ├── setup_postgres.sh                # Automated PostgreSQL setup
│   ├── migrate_duckdb_to_postgres.py    # Data migration tool
│   ├── analyze_stress_test.py           # Stress test analysis & comparison
│   ├── quick_fix_test.sh                # Quick DuckDB fixes (temporary)
│   ├── test_rate_limit.sh               # Basic API test script
│   └── deploy_nginx_config.sh           # Nginx deployment script
│
├── api_under_stress/                    # Git submodule (Gatling stress tests)
│   └── stress-test/
│       ├── run-test.sh                  # Run Gatling tests
│       └── user-files/
│           ├── simulations/             # Test scenarios
│           ├── resources/               # Test data
│           └── results/                 # Test results with HTML reports
│
└── data/
    └── app.duckdb                       # Local DuckDB file (kept for analytics)
```

## Troubleshooting

**Port already in use:**
```bash
lsof -i :5001  # Find process using port
# Kill process or change PORT env variable
```

**Database connection fails:**
```bash
# Run diagnostic
python diagnose_db.py

# Check environment variables
cat .env

# Verify MotherDuck token (if using cloud DB)
```

**Gatling tests fail:**
- Ensure Flask app is running on port 5001
- Check Java is installed: `java -version`
- Verify sbt is installed: `sbt --version`

## Development

### Adding New Endpoints

1. Add route in `src/routes/warrior_routes.py`
2. Define data access function in `src/db/warrior.py` (if needed)
3. Update tests

### Updating Database Schema

1. Modify `src/db/schema.sql` (DuckDB) or `schema_postgresql.sql` (PostgreSQL)
2. Restart Flask app (schema auto-applies on startup for DuckDB)
3. For PostgreSQL: `docker exec warrior-postgres psql -U warrior -d warrior_api -f schema_postgresql.sql`

## Performance Analysis & Lessons Learned

### The Journey: DuckDB → PostgreSQL

This project started with DuckDB as the embedded database but encountered severe performance issues under stress testing. The migration to PostgreSQL provides valuable lessons about database selection for high-concurrency workloads.

#### Initial Problem: 87% Error Rate

**Symptoms:**
- 12.6% success rate under load (5132 failures / 5880 requests)
- 503 Service Unavailable errors
- Worker timeouts after 30 seconds
- P95 latency of 12.8 seconds

**Root Cause:**
DuckDB is an embedded analytical database (OLAP) designed for single-process analytics, not high-concurrency transactional workloads (OLTP). With 29 Gunicorn workers competing for write access:
- DuckDB can only handle 1-2 concurrent writers
- Workers blocked waiting for database write locks  
- Connection pool exhaustion led to timeouts
- **Fundamental architectural mismatch**

#### Solution: PostgreSQL Migration

**Why PostgreSQL?**
- ✅ Designed for high-concurrency OLTP workloads
- ✅ Handles 100+ concurrent writes easily
- ✅ True MVCC with row-level locking
- ✅ Battle-tested for web APIs
- ✅ Rich tooling ecosystem

**Results:**
- **Success rate: 12.6% → 99.8%** (+87.2%)
- **P95 latency: 12.8s → 66ms** (-99.5%, 194x faster)
- **Throughput: 76 → 107 req/s** (+40%)
- **Worker timeouts: Eliminated**

#### Key Lessons

1. **Choose the Right Tool**: DuckDB excels at analytics but isn't designed for concurrent writes. PostgreSQL is purpose-built for transactional workloads.

2. **Connection Pool Sizing Matters**: With PostgreSQL's 200-connection limit and 29 workers, we set 5 connections/worker (145 total) to avoid exhaustion.

3. **Stress Testing Reveals Architectural Issues**: What works in development can fail dramatically under load. Always stress test before production.

4. **Preserve Comparative Code**: We kept DuckDB code for analytics use cases and as a reference for the dramatic performance difference.

#### Documentation

📚 **Comprehensive guides for this performance journey:**

- **[DEBUGGING_REPORT.md](DEBUGGING_REPORT.md)** - Detailed analysis of the problem with evidence
- **[POSTGRESQL_MIGRATION.md](POSTGRESQL_MIGRATION.md)** - Complete PostgreSQL setup guide
- **[PERFORMANCE_TUNING_SUMMARY.md](PERFORMANCE_TUNING_SUMMARY.md)** - Full comparison & decisions
- **[QUICK_START.md](QUICK_START.md)** - Quick reference guide

#### Database Comparison

| Feature | DuckDB | PostgreSQL |
|---------|--------|------------|
| **Use Case** | Analytics (OLAP) | Transactions (OLTP) |
| **Concurrent Writes** | 1-2 | 100+ |
| **Deployment** | Embedded file | Client-server |
| **Best For** | Data analysis, reporting | Web APIs, high concurrency |
| **Our Success Rate** | 12.6% @ 76 req/s | 99.8% @ 107 req/s |

#### When to Use Each Database

**Use PostgreSQL when:**
- Building web APIs or transactional applications
- Need high write concurrency (multiple users writing simultaneously)
- Require production-grade reliability and monitoring
- This is our **production choice**

**Use DuckDB when:**
- Performing analytics on large datasets
- Running in a single-process context
- Need fast analytical queries
- Generating reports or doing data science
- We keep it for **comparative testing and analytics**

#### Stress Testing Tools

This project includes comprehensive stress testing:

```bash
# Run full stress test
cd api_under_stress/stress-test
./run-test.sh

# Analyze latest results
python3 scripts/analyze_stress_test.py --latest

# Compare two test runs
python3 scripts/analyze_stress_test.py --compare <dir1> <dir2>
```

The analysis tool provides:
- Success/failure rates
- Response time percentiles (P50, P75, P95, P99)
- Throughput metrics
- Error breakdown
- Before/after comparisons

#### Architecture

```
Client Request
    ↓
Nginx (Rate Limiting: 1000 req/s)
    ↓
Gunicorn (29 workers)
    ↓
Flask Application (Database Adapter)
    ↓
PostgreSQL (200 max connections)
    - 5 connections per worker = 145 total
    - Connection pooling prevents exhaustion
    - Optimized for concurrent writes
```

## License

Qwasar MSCS Engineering Lab - Project 2
