# Rate Limiter Testing Guide

This guide explains how to test the rate limiter for the Flask API.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the Flask app:**
   ```bash
   python limiter.py
   ```
   
   The app will run on `http://localhost:5000` by default.
   
   **Note:** If port 5000 is already in use (common on macOS due to AirPlay), you can modify `limiter.py` to use a different port.

## Testing Methods

### Option 1: Bash Script (Simple)

Run the bash test script:

```bash
# Basic test (20 requests)
./scripts/test_rate_limit.sh

# Custom endpoint and number of requests
./scripts/test_rate_limit.sh http://localhost:5000/health 50

# With slower requests (not rapid mode)
./scripts/test_rate_limit.sh http://localhost:5000/health 20 slow
```

**Expected Results:**
- Flask limit: 100 requests per minute
- For 20-50 requests sent rapidly, all should succeed
- For 100+ requests, you should see 429 (Too Many Requests) errors after ~100 requests

### Option 2: Python Test Suite (Comprehensive)

Run the comprehensive Python test suite:

```bash
python test_rate_limiter.py
```

This runs three test scenarios:
1. **Rapid Sequential Requests** (110 requests) - Tests when rate limiting kicks in
2. **Concurrent Requests** (50 requests, 10 threads) - Tests concurrent access
3. **Sustained Rate** (2 req/s for 10s) - Tests normal usage pattern

**Features:**
- Detailed statistics (success rate, response times, etc.)
- Clear visual indicators (✓, 🚫, ✗)
- Response time analysis
- Automatic endpoint checking

## Understanding the Results

### Status Codes:
- **200 OK**: Request succeeded (within rate limit)
- **429 Too Many Requests**: Rate limit exceeded
- **503 Service Unavailable**: Service error (not rate limiting)

### Flask Rate Limiter:
- Current limit: **100 requests per minute per IP**
- Uses `flask-limiter` with `get_remote_address` as the key function
- Stored in memory (resets on app restart)

### Nginx Rate Limiter (if configured):
- Limit: **5 requests/second with burst of 10**
- Would trigger at the nginx level before Flask
- Currently configured but may not be active depending on deployment

## Troubleshooting

### Flask app won't start:
- Check if port 5000 is in use: `lsof -i :5000`
- Try a different port in `limiter.py`: `app.run(host="0.0.0.0", port=5001)`
- Make sure dependencies are installed: `pip install -r requirements.txt`

### No rate limiting detected:
- For small numbers of requests (<100), this is normal
- Try sending 110+ requests rapidly to see rate limiting
- Check that `flask-limiter` is properly imported and configured

### Connection errors:
- Make sure the Flask app is running
- Check the endpoint URL matches where the app is running
- Verify firewall/network settings

## Advanced Testing

### Test with Apache Bench (ab):
```bash
# Install ab if needed (macOS: already available, Linux: apt-get install apache2-utils)
ab -n 120 -c 10 http://localhost:5000/health
```

### Test with wrk:
```bash
# Install wrk if needed: brew install wrk (macOS) or apt-get install wrk (Linux)
wrk -t2 -c10 -d30s http://localhost:5000/health
```

### Monitor rate limiting in real-time:
```bash
# In one terminal: watch the Flask logs
python limiter.py

# In another terminal: run tests
python test_rate_limiter.py
```

## Next Steps

- Configure Redis backend for distributed rate limiting across multiple instances
- Add rate limit headers to responses
- Implement different limits for different endpoints
- Add rate limit information to API responses

