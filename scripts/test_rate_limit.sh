#!/bin/bash
# Test rate limiter on Flask app

# Get port from environment variable, default to 5001 to match Flask app default
PORT="${PORT:-5001}"
ENDPOINT="${1:-http://localhost:${PORT}/health}"
REQUESTS="${2:-20}"
MODE="${3:-rapid}"

echo "=========================================="
echo "Rate Limiter Test"
echo "=========================================="
echo "Endpoint: $ENDPOINT"
echo "Requests: $REQUESTS"
echo "Mode: $MODE"
echo ""

# Check database connectivity before running tests
echo "Verifying database connectivity..."
DB_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from src.db.pool import verify_database_health
success, message = verify_database_health()
if success:
    print(message)
    sys.exit(0)
else:
    print(message, file=sys.stderr)
    sys.exit(1)
" 2>&1)

DB_STATUS=$?
if [ $DB_STATUS -ne 0 ]; then
    echo "❌ Database connectivity check failed!"
    echo "$DB_OUTPUT"
    echo ""
    echo "Please ensure:"
    echo "  - Database is properly configured (check DB_MODE, MOTHERDUCK_TOKEN, etc.)"
    echo "  - For local mode: database file is accessible"
    echo "  - For MotherDuck mode: MOTHERDUCK_TOKEN is set and valid"
    echo ""
    echo "Run 'python diagnose_db.py' for detailed diagnostics."
    exit 1
fi

echo "✓ $DB_OUTPUT"
echo ""

# Check if endpoint is reachable
if ! curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT" | grep -q "200\|429\|503"; then
    echo "⚠️  Warning: Cannot reach endpoint. Is the Flask app running?"
    echo "   Start it with: python limiter.py"
    exit 1
fi

SUCCESS=0
FAILED=0
RATE_LIMITED=0
OTHER_ERRORS=0

echo "Sending requests..."
echo ""

START_TIME=$(date +%s.%N)

for i in $(seq 1 $REQUESTS); do
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT" 2>&1)
  TIMESTAMP=$(date +%H:%M:%S.%3N)

  case "$RESPONSE" in
    "200")
      echo "[$TIMESTAMP] Request $i: ✓ 200 OK"
      ((SUCCESS++))
      ;;
    "429")
      echo "[$TIMESTAMP] Request $i: 🚫 429 Too Many Requests (RATE LIMITED)"
      ((RATE_LIMITED++))
      ((FAILED++))
      ;;
    "503")
      echo "[$TIMESTAMP] Request $i: ⚠️  503 Service Unavailable"
      ((OTHER_ERRORS++))
      ((FAILED++))
      ;;
    *)
      echo "[$TIMESTAMP] Request $i: ✗ $RESPONSE (ERROR)"
      ((OTHER_ERRORS++))
      ((FAILED++))
      ;;
  esac

  # Sleep between requests if not in rapid mode
  if [ "$MODE" != "rapid" ]; then
    sleep 0.1
  fi
done

END_TIME=$(date +%s.%N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc)

echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo "Total requests:    $REQUESTS"
echo "Successful (200):  $SUCCESS"
echo "Rate limited (429): $RATE_LIMITED"
echo "Other errors:      $OTHER_ERRORS"
echo "Failed total:      $FAILED"
echo "Duration:          ${DURATION}s"
echo ""

if [ $SUCCESS -gt 0 ]; then
    SUCCESS_RATE=$(echo "scale=2; $SUCCESS * 100 / $REQUESTS" | bc)
    echo "Success rate:      ${SUCCESS_RATE}%"
fi

echo ""
echo "Expected behavior:"
echo "- Flask app: 100 req/min (all should pass for $REQUESTS requests)"
echo "- Nginx: 5 req/s + burst 10 (rapid requests may hit limit)"
