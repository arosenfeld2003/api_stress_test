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

This application **must** be run through the GHCR nginx container to enable dual-layer rate limiting (nginx + Flask). Direct access to the Flask app bypasses the nginx rate limiter and is not supported for testing.

### 1. Pull and Run Nginx Container from GHCR

```bash
# Pull nginx container
docker pull ghcr.io/your-org/api-stress-test-nginx:latest

# Run container
docker run -d \
  --name api_stress_test_nginx \
  -p 443:443 \
  -p 80:80 \
  --network host \
  ghcr.io/your-org/api-stress-test-nginx:latest
```

**Note:** The `--network host` flag allows nginx to connect to Flask on `localhost:5001`. For production deployments, use a Docker network instead.

### 2. Deploy Nginx Configuration

```bash
# Deploy nginx.conf to container
./scripts/deploy_nginx_config.sh api_stress_test_nginx
```

This script:
- Copies `nginx.conf` to the container
- Validates the configuration
- Reloads nginx gracefully

### 3. Start Flask Application

```bash
python limiter.py
```

The Flask app will run on `localhost:5001` (internal, accessed only by nginx).

### 4. Access API Through Nginx

The API is accessible through nginx:

- **HTTP:** `http://localhost:80` (for local testing)
- **HTTPS:** `https://localhost:443` (requires SSL certificates)

**For local testing without SSL certificates**, you can:
- Use HTTP on port 80, or
- Modify `nginx.conf` to remove SSL requirements, or
- Generate self-signed certificates for testing

The nginx container acts as a reverse proxy and rate limiter, forwarding requests to the Flask app on port 5001.

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

**Important:** All testing must go through the nginx proxy to validate both nginx and Flask rate limiting. Direct access to Flask (port 5001) bypasses the nginx rate limiter.

### Quick API Test

All requests go through nginx on port 80 (or 443 for HTTPS):

```bash
# Health check (through nginx)
curl http://localhost:80/health

# Create a warrior
curl -X POST http://localhost:80/warrior \
  -H "Content-Type: application/json" \
  -d '{"name": "Master Yoda", "dob": "1970-01-01", "fight_skills": ["BJJ", "KungFu"]}'

# Get warrior (use UUID from previous response)
curl http://localhost:80/warrior/{uuid}

# Search warriors
curl "http://localhost:80/warrior?t=Yoda"

# Count warriors
curl http://localhost:80/counting-warriors
```

### Rate Limiter Tests

All tests go through nginx to validate **both** nginx (5 req/s) and Flask (100 req/min) rate limiters.

#### Option 1: Simple Bash Script

```bash
# Basic test (20 requests) - uses nginx endpoint
./scripts/test_rate_limit.sh http://localhost:80/health 20

# Custom endpoint and requests
./scripts/test_rate_limit.sh http://localhost:80/counting-warriors 50

# Slower requests (not rapid mode)
./scripts/test_rate_limit.sh http://localhost:80/health 20 slow
```

#### Option 2: Python Test Suite

```bash
python test_rate_limiter.py
```

**Note:** The test suite is configured to use `http://localhost:80` by default (nginx proxy).

This comprehensive test suite includes:
- Rapid sequential requests (110 requests to test Flask limit)
- Concurrent requests (50 requests, 10 threads) - **will hit nginx 5 req/s limit**
- Sustained rate testing (2 req/s for 10s)

**Expected Results:**
- **Nginx limit (5 req/s):** Requests exceeding 5/s will get 429 errors from nginx
- **Flask limit (100 req/min):** Requests within nginx limits but exceeding 100/min will get 429 errors from Flask
- Nginx rate limiting is evaluated **first**, so high-rate requests (>5/s) will be blocked before reaching Flask

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

All load testing must go through nginx:

#### Apache Bench

```bash
# Test through nginx (will hit 5 req/s limit)
ab -n 120 -c 10 http://localhost:80/health

# Or test specific endpoint
ab -n 120 -c 10 http://localhost:80/counting-warriors
```

#### wrk

```bash
# Test through nginx
wrk -t2 -c10 -d30s http://localhost:80/health
```

**Note:** These tools send high-concurrency requests that will trigger nginx rate limiting (5 req/s). Adjust test parameters accordingly.

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

## GHCR Nginx Component (Required)

The nginx container from GitHub Container Registry (GHCR) is **required** for all deployments and testing. It provides the first layer of rate limiting and security features.

### Why Nginx is Required

- **Dual-layer rate limiting:** Nginx (5 req/s) + Flask (100 req/min)
- **Production-ready security:** SSL/TLS, security headers, connection limits
- **Reverse proxy:** Protects Flask app and provides proper HTTP handling
- **Rate limit testing:** Both limiters must be tested together

### Container Setup

1. **Pull nginx container from GHCR:**
   ```bash
   docker pull ghcr.io/your-org/api-stress-test-nginx:latest
   ```

2. **Deploy configuration:**
   ```bash
   ./scripts/deploy_nginx_config.sh api_stress_test_nginx
   ```

The nginx container provides:
- **Rate limiting:** 5 req/s with burst of 10 (first defense)
- **Connection limits:** Maximum 20 concurrent connections per IP
- **SSL/TLS termination:** HTTPS support with security headers
- **Security headers:** HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- **Reverse proxy:** Forwards requests to Flask app on port 5001
- **Timeouts:** Protection against slowloris attacks
- **Body size limit:** 2MB maximum request body size
- **HTTP/2 support:** Enabled for better performance

### Nginx Configuration Details

The `nginx.conf` file configures:
- **Rate Limiting:** `limit_req_zone` with 5 req/s and burst of 10
- **Connection Limits:** Maximum 20 concurrent connections per IP via `limit_conn_zone`
- **Security Headers:** All security headers applied to responses
- **Proxy Settings:** Proper headers forwarded to Flask (X-Real-IP, X-Forwarded-For)

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

### Nginx Container Issues

**Container not starting:**
```bash
# Check container logs
docker logs api_stress_test_nginx

# Check if container is running
docker ps -a | grep api_stress_test_nginx

# Verify nginx config syntax
docker exec api_stress_test_nginx nginx -t
```

**Container can't connect to Flask:**
- Ensure Flask app is running on `localhost:5001`
- Use `--network host` flag when running container, or configure Docker network
- Check nginx config has correct `proxy_pass http://127.0.0.1:5001`

**SSL certificate errors (for HTTPS):**
- For local testing, use HTTP on port 80 instead
- Or modify `nginx.conf` to remove SSL requirements
- Or generate self-signed certificates:
  ```bash
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /path/to/key.pem -out /path/to/cert.pem
  ```

### Rate Limiting Not Working

**Nginx rate limiting:**
- Verify `nginx.conf` is deployed correctly: `docker exec api_stress_test_nginx nginx -t`
- Test with >5 req/s to trigger nginx limit (e.g., `ab -n 10 -c 10 http://localhost:80/health`)
- Check nginx logs: `docker logs api_stress_test_nginx`

**Flask rate limiting:**
- Check that `flask-limiter` is properly installed
- Verify Flask app is receiving requests (check Flask logs)
- Test with >100 requests/min within nginx limits

**Both limiters:**
- Always test through nginx (`http://localhost:80`), not directly to Flask
- Nginx limits are checked first, then Flask limits

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
