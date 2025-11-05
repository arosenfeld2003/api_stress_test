# Stress Testing Guide

This guide explains how to run and interpret the Gatling stress tests for the Warrior API.

## Overview

The stress tests are located in the `api_under_stress` subdirectory and use Gatling to simulate high load scenarios. The tests verify:

- API response times under load
- Rate limiting behavior
- Database performance under concurrent requests
- Error handling (422, 400, 429 status codes)
- Overall system stability

## Prerequisites

1. **Python 3.8+** - For the Flask API
2. **Java JDK 8+** - For running Gatling (required)
3. **Gatling** - Already included in `api_under_stress/deps/`

### Installing Java

Gatling requires Java 8 or higher. If you see "Unable to locate a Java Runtime", install Java:

**macOS (Homebrew):**
```bash
brew install openjdk@11
# Or for Java 17:
brew install openjdk@17

# Add to PATH (add to ~/.zshrc or ~/.bash_profile)
export PATH="/opt/homebrew/opt/openjdk@11/bin:$PATH"
```

**macOS (Direct Download):**
- Visit [Oracle Java Downloads](https://www.oracle.com/java/technologies/downloads/)
- Or [Adoptium (OpenJDK)](https://adoptium.net/)
- Download and install the macOS installer

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install openjdk-11-jdk

# CentOS/RHEL
sudo yum install java-11-openjdk-devel

# Verify installation
java -version
```

**Verify Java Installation:**
```bash
java -version
# Should show version 1.8+ or 8+
```

## Setup

Before running stress tests, ensure your environment is set up:

```bash
# Run the setup script to install dependencies and verify environment
./scripts/setup_stress_test.sh
```

Or manually install dependencies:

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Verify installation
python3 -c "import flask; import flask_limiter; import duckdb; print('OK')"
```

## Quick Start

### Option 1: Automated Script (Recommended)

```bash
# Run the complete stress test suite
# This will check dependencies and install them if needed
./scripts/run_stress_test.sh
```

This script will:
1. Generate test resources (100,000 warrior payloads, 5,000 search terms)
2. Start the Flask app on port 9999
3. Run the Gatling stress tests
4. Display results location

### Option 2: Manual Steps

1. **Generate test resources:**
   ```bash
   ./scripts/generate_stress_resources.sh
   # Or manually:
   cd api_under_stress
   python3 stress-test/generate_resources.py
   ```

2. **Start Flask app on port 9999:**
   ```bash
   # Option A: Use helper script (recommended)
   ./scripts/start_flask_for_stress_test.sh
   
   # Option B: Start manually
   PORT=9999 FLASK_THREADED=true python3 limiter.py
   
   # Verify it's running:
   curl http://localhost:9999/health
   ```

3. **Run Gatling tests (in another terminal):**
   ```bash
   cd api_under_stress
   ./stress-test/run-test.sh
   ```

## Test Scenarios

The `EngLabStressTest.scala` simulation includes:

### 1. Creation and Lookup for Warriors
- **Phase 1:** 2 users/sec for 10 seconds
- **Phase 2:** 5 users/sec (randomized) for 15 seconds
- **Phase 3:** Ramp from 4 to 1000 users/sec over 5 minutes
- **Behavior:** Creates warriors and immediately looks them up

### 2. Valid Warrior Lookup (Search)
- **Phase 1:** 10 users/sec for 75 seconds
- **Phase 2:** Ramp from 8 to 1000 users/sec over 10 minutes
- **Behavior:** Searches warriors using terms from `search-terms.tsv`

### 3. Invalid Warrior Lookup
- **Phase 1:** 8 users/sec for 45 seconds
- **Phase 2:** Ramp from 6 to 400 users/sec over 5 minutes
- **Behavior:** Tests GET `/warrior` without query parameter (expects 400)

## Expected Results

### Success Criteria

- **Response Times:**
  - Mean response time: < 1000ms
  - 95th percentile: < 2000ms
  - Max response time: < 5000ms

- **Error Rates:**
  - Less than 10% failures (excluding intentional rate limit tests)
  - 422 status codes for validation errors (expected)
  - 429 status codes for rate limiting (expected at high load)

- **Throughput:**
  - Should handle at least 100 requests/second
  - Database queries should remain fast under load

### Status Codes

The API should return:
- **201 Created** - Successful warrior creation
- **200 OK** - Successful GET requests
- **400 Bad Request** - Invalid requests (missing params, invalid JSON)
- **422 Unprocessable Entity** - Validation errors (invalid data format)
- **429 Too Many Requests** - Rate limit exceeded
- **404 Not Found** - Warrior not found

## Performance Optimizations

The codebase has been optimized for stress testing:

1. **Database Connection Optimization:**
   - Multi-threaded query execution
   - Optimized indexes on warrior table
   - Efficient search queries

2. **Flask Configuration:**
   - Threaded mode enabled for stress testing (`FLASK_THREADED=true`)
   - Proper error handling with correct status codes
   - Request logging for performance monitoring

3. **Query Performance:**
   - Composite indexes on name and dob
   - Optimized ILIKE patterns for search
   - Efficient array search for fight_skills

## Interpreting Results

After tests complete, open the HTML report:

```bash
# Find the latest result directory
LATEST=$(find api_under_stress/stress-test/user-files/results -name "englabstresstest-*" -type d | sort -r | head -1)

# Open in browser (macOS)
open "$LATEST/index.html"

# Or open in browser (Linux)
xdg-open "$LATEST/index.html"
```

### Key Metrics to Review

1. **Response Time Distribution:**
   - Check percentiles (50th, 75th, 95th, 99th)
   - Identify any spikes or degradation

2. **Request Statistics:**
   - Total requests vs successful requests
   - Error breakdown by status code
   - Throughput (requests/second)

3. **Response Time Over Time:**
   - Look for performance degradation
   - Check if system recovers after peak load

4. **Error Analysis:**
   - 422 errors are expected (validation failures)
   - 429 errors are expected (rate limiting)
   - 500 errors indicate issues needing investigation

## Troubleshooting

### ModuleNotFoundError: No module named 'flask'

If you see this error, it means Flask or other dependencies are not installed:

```bash
# Install all dependencies
pip3 install -r requirements.txt

# Or use the setup script
./scripts/setup_stress_test.sh

# Verify installation
python3 -c "import flask; import flask_limiter; import duckdb; print('OK')"
```

**If using a virtual environment:**
```bash
# Activate virtual environment first
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Then install dependencies
pip install -r requirements.txt
```

**If using system Python:**
```bash
# May need sudo on some systems
pip3 install --user -r requirements.txt
```

### Connection Refused Errors

If you see `j.n.ConnectException: Connection refused` in Gatling, the Flask app isn't reachable:

```bash
# 1. Check if Flask is running
curl http://localhost:9999/health

# 2. If not responding, check if process is running
ps aux | grep limiter.py

# 3. Check if port 9999 is in use
lsof -i :9999

# 4. Start Flask app manually
./scripts/start_flask_for_stress_test.sh

# Or start manually:
PORT=9999 FLASK_THREADED=true python3 limiter.py

# 5. Verify it's working
curl http://localhost:9999/health
# Should return: {"status":"ok"}
```

**Common causes:**
- Flask app not started
- Flask app crashed (check logs)
- Port 9999 blocked by firewall
- Flask app started but not ready yet (wait a few seconds)

### Flask App Not Starting

```bash
# Check if port 9999 is already in use
lsof -i :9999

# Kill existing process
pkill -f "limiter.py"

# Verify dependencies before starting
python3 -c "import flask; import flask_limiter; import duckdb"

# Start Flask app with logging
PORT=9999 FLASK_THREADED=true python3 limiter.py > /tmp/flask.log 2>&1 &

# Check logs if it fails
tail -50 /tmp/flask.log
```

**If Flask crashes on startup:**
- Check database permissions: `ls -la data/app.duckdb`
- Verify database schema: `python3 -c "from src.db.connection import get_connection; with get_connection(read_only=False, apply_schema=True) as con: pass"`
- Check for import errors: `python3 -c "from limiter import app; print('OK')"`

### Java Not Found / Gatling Won't Start

If you see "Unable to locate a Java Runtime":

```bash
# Check if Java is installed
java -version

# If not found, install Java (see Prerequisites section above)
# macOS with Homebrew:
brew install openjdk@11

# Then verify
java -version
```

**macOS specific:** If Java is installed but not found:
```bash
# Set JAVA_HOME (macOS)
export JAVA_HOME=$(/usr/libexec/java_home)

# Or add to ~/.zshrc or ~/.bash_profile:
export JAVA_HOME=$(/usr/libexec/java_home)
export PATH="$JAVA_HOME/bin:$PATH"
```

### Gatling Tests Failing

1. **Check Flask app is running:**
   ```bash
   curl http://localhost:9999/health
   ```

2. **Check Java is available:**
   ```bash
   java -version
   ```

3. **Check test resources exist:**
   ```bash
   ls -lh api_under_stress/stress-test/user-files/resources/
   ```

4. **Verify Gatling installation:**
   ```bash
   ls api_under_stress/deps/gatling-charts-highcharts-bundle-3.10.5/bin/
   ```

### Database Performance Issues

1. **Check database file size:**
   ```bash
   ls -lh data/app.duckdb
   ```

2. **Recreate database if needed:**
   ```bash
   rm data/app.duckdb
   python3 -c "from src.db.connection import get_connection; \
       with get_connection(read_only=False, apply_schema=True) as con: pass"
   ```

3. **Monitor database during tests:**
   ```bash
   # In another terminal
   watch -n 1 'ls -lh data/app.duckdb'
   ```

## Running Custom Tests

To modify test scenarios, edit:
```
api_under_stress/stress-test/user-files/simulations/englabstresstest/EngLabStressTest.scala
```

Common modifications:
- Adjust user injection rates
- Change test duration
- Modify payload sizes
- Add new scenarios

After modifying, regenerate resources if needed and rerun tests.

## Best Practices

1. **Run tests on a dedicated machine** - Avoid interference from other processes
2. **Monitor system resources** - Watch CPU, memory, and disk I/O
3. **Start with lower load** - Gradually increase to find breaking points
4. **Document results** - Keep track of performance changes over time
5. **Test after code changes** - Ensure optimizations don't regress performance

## Next Steps

After stress testing:
1. Review performance bottlenecks
2. Optimize slow queries
3. Adjust rate limits if needed
4. Consider database connection pooling for higher loads
5. Add caching for read-heavy operations

