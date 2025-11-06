#!/bin/bash

# Helper script to start Flask app for stress testing
# This can be run manually if the automated script has issues

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Check if port 9999 is already in use
if lsof -Pi :9999 -sTCP:LISTEN -t >/dev/null ; then
    echo "Port 9999 is already in use"
    echo "Existing process:"
    lsof -i :9999
    echo ""
    read -p "Kill existing process and restart? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "limiter.py" || true
        sleep 2
    else
        echo "Using existing Flask instance"
        exit 0
    fi
fi

# Verify dependencies
echo "Checking dependencies..."
if ! python3 -c "import flask; import flask_limiter; import duckdb; import gunicorn" 2>/dev/null; then
    echo "Error: Required Python packages are not installed"
    echo "Run: pip3 install -r requirements.txt"
    exit 1
fi
echo "✓ Dependencies OK"
echo ""

# Start Flask app with Gunicorn
echo "Starting Flask app with Gunicorn on port 9999..."
echo "Logs will be written to: /tmp/gunicorn_access.log and /tmp/gunicorn_error.log"
echo ""

PORT=9999 gunicorn -c gunicorn_config.py limiter:app &
FLASK_PID=$!

echo "Flask app started with PID: $FLASK_PID"
echo ""

# Wait for Flask to be ready
echo "Waiting for Flask to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:9999/health > /dev/null 2>&1; then
        HEALTH_RESPONSE=$(curl -s http://localhost:9999/health)
        echo "✓ Flask app is ready!"
        echo "  Health check response: $HEALTH_RESPONSE"
        echo ""
        echo "Flask app is running on http://localhost:9999"
        echo "To stop it, run: kill $FLASK_PID"
        echo "Or: pkill -f 'limiter.py'"
        exit 0
    fi
    
    if ! kill -0 $FLASK_PID 2>/dev/null; then
        echo "Error: Flask app process died"
        echo "Check logs: tail -50 /tmp/flask_stress_test.log"
        exit 1
    fi
    
    sleep 1
done

echo "Error: Flask app did not become ready"
echo "Check logs: tail -50 /tmp/flask_stress_test.log"
kill $FLASK_PID 2>/dev/null || true
exit 1

