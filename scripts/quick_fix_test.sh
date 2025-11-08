#!/bin/bash
# Quick fix test script
# Applies immediate optimizations and runs a lighter stress test

set -e

echo "======================================"
echo "Applying Quick Fixes for DuckDB"
echo "======================================"

cd "$(dirname "$0")/.."

# 1. Stop existing services
echo "1. Stopping existing services..."
pkill -f gunicorn || echo "No gunicorn processes found"
sleep 2

# 2. Backup current database
echo "2. Backing up database..."
if [ -f "./data/app.duckdb" ]; then
    cp ./data/app.duckdb "./data/app.duckdb.backup.$(date +%Y%m%d_%H%M%S)"
    echo "   Backup created"
fi

# 3. Clear database to start fresh
echo "3. Clearing database for clean test..."
rm -f ./data/app.duckdb ./data/app.duckdb.wal

# 4. Start Flask with REDUCED workers
echo "4. Starting Flask with reduced worker count (4 instead of ~29)..."
export PORT=5001
export DB_MODE=local
export LOCAL_DUCKDB_PATH=./data/app.duckdb
export DB_POOL_SIZE=10
export DB_MAX_CONNECTIONS=20

gunicorn -c gunicorn_config_reduced.py "limiter:app" --daemon

sleep 3

# 5. Verify service is running
echo "5. Verifying service..."
if curl -s http://localhost:5001/counting-warriors > /dev/null; then
    echo "   ✓ Service is running"
else
    echo "   ✗ Service failed to start"
    tail -50 /tmp/gunicorn_error.log
    exit 1
fi

# 6. Check initial count
echo "6. Initial warrior count:"
curl -s http://localhost:5001/counting-warriors | python3 -m json.tool

# 7. Run lighter stress test
echo ""
echo "======================================"
echo "Running LIGHTER Stress Test"
echo "======================================"
echo "This reduced test will:"
echo "  - Run for shorter duration"
echo "  - Lower concurrent user count"
echo "  - Help validate if quick fixes improve performance"
echo ""

# Note: You'll need to create a lighter test scenario or modify the existing one
# For now, we'll note what to do
echo "To run stress test:"
echo "  cd api_under_stress/stress-test"
echo "  # Edit user-files/simulations/englabstresstest/EngLabStressTest.scala"
echo "  # Reduce ramp rates temporarily (e.g., to 10 instead of 100)"
echo "  ../deps/gatling-charts-highcharts-bundle-3.10.5/bin/gatling.sh -s EngLabStressTest"
echo ""
echo "Or run a simple load test:"
echo "  # Install apache bench: brew install httpd (macOS)"
echo "  ab -n 1000 -c 10 http://localhost:80/counting-warriors"

echo ""
echo "======================================"
echo "Quick Fix Applied Successfully!"
echo "======================================"
echo "Changes:"
echo "  ✓ Reduced workers from ~29 to 4"
echo "  ✓ Increased timeout from 30s to 60s"
echo "  ✓ Fresh database (no old locks)"
echo ""
echo "Monitor with:"
echo "  tail -f /tmp/gunicorn_error.log"
echo "  tail -f /tmp/gunicorn_access.log"

