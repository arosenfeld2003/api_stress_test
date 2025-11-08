#!/bin/bash
# Start Flask app optimized for stress testing
# Run this before starting Gatling tests

echo "Starting Flask app with stress test optimizations..."
echo ""
echo "Settings:"
echo "  - Connection Pool: 50 connections (max 100)"
echo "  - Rate Limit: 600,000 req/min (10,000 req/s)"
echo "  - Threading: Enabled"
echo "  - Port: 5001"
echo ""

# Set environment variables for stress testing
export DB_POOL_SIZE=50
export DB_MAX_CONNECTIONS=100
export FLASK_RATE_LIMIT=600000
export FLASK_THREADED=true
export PORT=5001
export HOST=0.0.0.0

# IP blocker settings (whitelist localhost)
export IP_BLOCKER_WHITELIST_LOCALHOST=true
export IP_BLOCKER_MAX_RPM=1000000

# Start Flask app
python limiter.py

