# Warrior API - Rate-Limited REST API with MotherDuck

Qwasar MSCS Engineering Lab - Project 2

A Flask-based REST API for managing warriors with connection pooling, rate limiting, and comprehensive stress testing capabilities.

## Overview

This project demonstrates a production-ready API with:
- **Flask REST API** for warrior CRUD operations
- **Connection pooling** with MotherDuck cloud database support
- **Rate limiting** to protect against abuse (configurable)
- **Gatling stress testing** for performance validation

## Features

- **REST API**: Create, read, search, and count warriors
- **Database Connection Pool**: Optimized connection management for high-load scenarios
- **MotherDuck Integration**: Cloud database with local fallback
- **Rate Limiting**: Application-level protection (configurable requests per minute)
- **Stress Testing**: Gatling-based load and rate limit validation
- **Health Checks**: Database connectivity verification on startup

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

### 2. Configure Database

**Option A: Local DuckDB** (default, no configuration needed)

**Option B: MotherDuck Cloud**

Create a `.env` file:
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
├── README.md                   # This file
├── limiter.py                  # Flask app entry point
├── requirements.txt            # Python dependencies
├── diagnose_db.py              # Database diagnostic tool
├── .env                        # Environment config (create this)
│
├── src/
│   ├── db/
│   │   ├── connection.py       # Database connection management
│   │   ├── pool.py             # Connection pool implementation
│   │   ├── warrior.py          # Warrior data access functions
│   │   └── schema.sql          # Database schema
│   ├── routes/
│   │   └── warrior_routes.py   # API endpoints
│   └── security/
│       └── ip_blocker.py       # IP blocking/abuse detection
│
├── scripts/
│   ├── test_rate_limit.sh      # Basic API test script
│   └── deploy_nginx_config.sh  # Nginx deployment script
│
├── api_under_stress/           # Git submodule (Gatling stress tests)
│   └── stress-test/
│       ├── run-test.sh         # Run Gatling tests
│       └── user-files/         # Test scenarios and results
│
└── data/
    └── app.duckdb              # Local database file
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

1. Modify `src/db/schema.sql`
2. Restart Flask app (schema auto-applies on startup)

## License

Qwasar MSCS Engineering Lab - Project 2
