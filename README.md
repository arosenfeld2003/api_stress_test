# API Stress Test - Warrior API

Qwasar MSCS Engineering Lab - Project 2

A Flask-based REST API for managing warriors with comprehensive rate limiting at both the application and reverse proxy levels. Includes stress testing capabilities using Gatling.

## Overview

This project implements a production-ready API with:

- **Flask REST API** with warrior CRUD operations
- **Dual-layer rate limiting**: Flask application (100 req/min) + Nginx reverse proxy (5 req/s)
- **DuckDB** database for persistence (local or MotherDuck)
- **Nginx reverse proxy** via GHCR container with SSL/TLS and security headers
- **Gatling stress tests** for performance and rate limit validation

## Architecture

```
┌─────────────────┐
│   Client/Test   │
└────────┬────────┘
         │ HTTPS (443)
         ▼
┌─────────────────┐
│  Nginx Proxy    │  ← Rate limit: 5 req/s (burst 10)
│  (GHCR Container│  ← SSL/TLS termination
└────────┬────────┘  ← Security headers
         │ HTTP (5001)
         ▼
┌─────────────────┐
│  Flask App      │  ← Rate limit: 100 req/min per IP
│  (limiter.py)   │  ← Warrior API routes
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   DuckDB        │  ← Local file or MotherDuck
│   Database      │
└─────────────────┘
```

### Components

1. **Flask Application** (`limiter.py`)
   - REST API endpoints for warrior management
   - Application-level rate limiting (100 requests/minute per IP)
   - Automatic database schema initialization
   - Graceful shutdown handling

2. **Nginx Reverse Proxy** (GHCR Container)
   - SSL/TLS termination with Let's Encrypt certificates
   - Proxy-level rate limiting (5 requests/second with burst of 10)
   - Connection limits (20 concurrent per IP)
   - Security headers (HSTS, X-Frame-Options, etc.)
   - Timeout protection against slowloris attacks

3. **Database Layer** (`src/db/`)
   - DuckDB for local file-based storage
   - Optional MotherDuck cloud integration
   - Schema management via SQL scripts

## API Endpoints

### Health Check
- **GET** `/health`
  - Returns: `{"status": "ok"}`
  - Status: 200

### Warrior Management

#### Create Warrior
- **POST** `/warrior`
  - **Request Body:**
    ```json
    {
      "name": "Master Yoda",
      "dob": "1970-01-01",
      "fight_skills": ["BJJ", "KungFu", "Judo"]
    }
    ```
  - **Response:** 201 Created
  - **Headers:** `Location: /warrior/{uuid}`
  - **Body:** Created warrior object with generated UUID

#### Get Warrior by ID
- **GET** `/warrior/{id}`
  - **Response:** 200 OK (warrior found) or 404 Not Found
  - **Body:** Warrior object with UUID, name, dob, fight_skills

#### Search Warriors
- **GET** `/warrior?t={search_term}`
  - **Query Parameter:** `t` (required) - search term
  - **Response:** 200 OK with array of warriors (max 50 results)
  - **Error:** 400 Bad Request if `t` parameter is missing
  - Searches across name, date of birth, and fight skills

#### Count Warriors
- **GET** `/counting-warriors`
  - **Response:** 200 OK
  - **Body:** `{"count": 42}`

## Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)
- **Docker** (for nginx container)
- **Java JDK 8+** (for Gatling stress tests)
- **sbt** (Scala Build Tool, for Gatling)

## Setup

### 1. Python Environment

```bash
# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Database Configuration

The app uses DuckDB by default (local file storage). No additional setup required.

**Optional: MotherDuck Cloud Database**

Create a `.env` file in the project root:

```bash
DB_MODE=motherduck
MOTHERDUCK_TOKEN=your_token_here
MOTHERDUCK_DATABASE=api_stress_test  # optional
```

### 3. Initialize Database Schema

The database schema is automatically initialized when the Flask app starts. To manually initialize:

```bash
python -c "from src.db.connection import get_connection; \
    with get_connection(read_only=False, apply_schema=True) as con: pass"
```

This creates the `warrior` table and necessary indexes in `./data/app.duckdb`.

## Running the Application

### Option 1: Direct Flask (Development)

```bash
python limiter.py
```

The app will run on `http://localhost:5001`

### Option 2: Through Nginx (Production-like)

1. **Pull and run nginx container from GHCR:**

```bash
# Pull nginx container (adjust image name/path as needed)
docker pull ghcr.io/your-org/api-stress-test-nginx:latest

# Run container (adjust image name as needed)
docker run -d \
  --name api_stress_test_nginx \
  -p 443:443 \
  -p 80:80 \
  ghcr.io/your-org/api-stress-test-nginx:latest
```

2. **Deploy nginx configuration:**

```bash
# Deploy nginx.conf to container
./scripts/deploy_nginx_config.sh api_stress_test_nginx
```

This script:
- Copies `nginx.conf` to the container
- Validates the configuration
- Reloads nginx gracefully

3. **Start Flask app:**

```bash
python limiter.py
```

The API will be accessible through nginx at `https://myapi.example.com` (or `http://localhost` if SSL is not configured for local testing).

**Note:** For local testing without SSL certificates, you may need to modify `nginx.conf` to remove SSL requirements or use a self-signed certificate.

### Environment Variables

Create a `.env` file (optional):

```bash
# Database configuration
DB_MODE=local  # or 'motherduck'
LOCAL_DUCKDB_PATH=./data/app.duckdb

# MotherDuck (if using cloud DB)
MOTHERDUCK_TOKEN=your_token_here
MOTHERDUCK_DATABASE=api_stress_test
```

## Testing

### Quick API Test

```bash
# Health check
curl http://localhost:5001/health

# Create a warrior
curl -X POST http://localhost:5001/warrior \
  -H "Content-Type: application/json" \
  -d '{"name": "Master Yoda", "dob": "1970-01-01", "fight_skills": ["BJJ", "KungFu"]}'

# Get warrior (use UUID from previous response)
curl http://localhost:5001/warrior/{uuid}

# Search warriors
curl "http://localhost:5001/warrior?t=Yoda"

# Count warriors
curl http://localhost:5001/counting-warriors
```

### Rate Limiter Tests

#### Option 1: Simple Bash Script

```bash
# Basic test (20 requests)
./scripts/test_rate_limit.sh

# Custom endpoint and requests
./scripts/test_rate_limit.sh http://localhost:5001/health 50

# Slower requests (not rapid mode)
./scripts/test_rate_limit.sh http://localhost:5001/health 20 slow
```

#### Option 2: Python Test Suite

```bash
python test_rate_limiter.py
```

This comprehensive test suite includes:
- Rapid sequential requests (110 requests to test Flask limit)
- Concurrent requests (50 requests, 10 threads)
- Sustained rate testing (2 req/s for 10s)

**Expected Results:**
- Flask limit (100 req/min): First 100 requests succeed, then 429 errors
- Nginx limit (5 req/s): Requests exceeding 5/s will get 429 errors

### Gatling Stress Tests

Comprehensive performance and rate limit validation tests:

```bash
cd gatling

# Run stress tests
sbt "Gatling / testOnly test.WarriorApiSimulation"

# View results
# Results will be in: gatling/target/gatling/warriorapisimulation-<timestamp>/index.html
```

The Gatling simulation tests:
- All warrior API endpoints
- Multiple load scenarios (warm-up, normal, stress, peak)
- Rate limit validation (intentionally exceeds limits)
- Response time analysis
- Throughput metrics

See `gatling/README.md` for detailed documentation.

### Advanced Testing Tools

#### Apache Bench

```bash
ab -n 120 -c 10 http://localhost:5001/health
```

#### wrk

```bash
wrk -t2 -c10 -d30s http://localhost:5001/health
```

## Rate Limiting Configuration

### Flask Application Level
- **Limit:** 100 requests per minute per IP address
- **Implementation:** `flask-limiter` with `get_remote_address`
- **Storage:** In-memory (resets on restart)
- **Status Code:** 429 Too Many Requests

### Nginx Proxy Level
- **Limit:** 5 requests per second (with burst of 10)
- **Implementation:** `limit_req_zone` and `limit_req` directives
- **Connection Limit:** 20 concurrent connections per IP
- **Status Code:** 429 Too Many Requests

**Rate Limit Behavior:**
- Nginx rate limiting is evaluated **first** (at proxy level)
- Flask rate limiting is evaluated **second** (at application level)
- Requests exceeding nginx limits will never reach Flask
- Requests within nginx limits may still be limited by Flask

## Project Structure

```
api_stress_test/
├── limiter.py              # Flask app entry point with rate limiting
├── nginx.conf              # Nginx reverse proxy configuration
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── TESTING.md             # Detailed testing guide
│
├── src/
│   ├── routes/
│   │   └── warrior_routes.py  # Warrior API endpoints (Blueprint)
│   └── db/
│       ├── connection.py     # DuckDB connection manager
│       ├── warrior.py        # Warrior data access functions
│       └── schema.sql        # Database schema definitions
│
├── scripts/
│   ├── deploy_nginx_config.sh  # Deploy nginx.conf to container
│   └── test_rate_limit.sh      # Simple rate limit test script
│
├── gatling/               # Gatling stress test suite
│   ├── build.sbt
│   ├── README.md
│   └── src/test/scala/
│       └── WarriorApiSimulation.scala
│
├── data/                  # Local DuckDB database files
│   └── app.duckdb
│
├── test_rate_limiter.py   # Python test suite
└── test_connection.py     # Database connection test
```

## GHCR Nginx Component

The nginx configuration is designed to run in a container from GitHub Container Registry (GHCR). 

### Container Setup

1. **Build/pull nginx container** with the configuration
2. **Deploy using the script:**
   ```bash
   ./scripts/deploy_nginx_config.sh [container_name]
   ```

The nginx container provides:
- SSL/TLS termination
- Rate limiting (5 req/s with burst of 10)
- Connection limits
- Security headers
- Reverse proxy to Flask app on port 5001

### Nginx Configuration Features

- **Rate Limiting:** `limit_req_zone` with 5 req/s and burst of 10
- **Connection Limits:** Maximum 20 concurrent connections per IP
- **Security Headers:** HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- **Timeouts:** Protection against slowloris attacks
- **Body Size Limit:** 2MB maximum request body size
- **HTTP/2 Support:** Enabled for better performance

## Troubleshooting

### Flask App Issues

**Port already in use:**
```bash
# Check what's using the port
lsof -i :5001

# Kill the process or change port in limiter.py
```

**Database errors:**
- Ensure `./data/` directory exists and is writable
- Check `.env` file if using MotherDuck
- Verify MOTHERDUCK_TOKEN is set correctly

### Nginx Issues

**Container not starting:**
```bash
# Check container logs
docker logs api_stress_test_nginx

# Verify nginx config syntax
docker exec api_stress_test_nginx nginx -t
```

**SSL certificate errors:**
- For local testing, modify `nginx.conf` to remove SSL requirements
- Or generate self-signed certificates:
  ```bash
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /path/to/key.pem -out /path/to/cert.pem
  ```

### Rate Limiting Not Working

- **Flask:** Check that `flask-limiter` is properly installed
- **Nginx:** Verify `nginx.conf` is deployed correctly to container
- **Testing:** Use 100+ requests for Flask limit, 10+ req/s for nginx limit

## Development

### Adding New Endpoints

1. Add route functions in `src/routes/warrior_routes.py` or create new Blueprint
2. Register Blueprint in `limiter.py`
3. Update tests accordingly

### Database Schema Changes

1. Modify `src/db/schema.sql`
2. Restart Flask app (schema auto-applies on startup)
3. Or manually apply: `python -c "from src.db.connection import get_connection; with get_connection(read_only=False, apply_schema=True) as con: pass"`

## License

Qwasar MSCS Engineering Lab - Project 2
