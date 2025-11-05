# IP Blocking and Abuse Detection

This document describes the IP blocking system that automatically detects and blocks IP addresses sending illegitimate requests.

## Overview

The IP blocking system tracks request patterns per IP address and automatically blocks IPs that demonstrate abusive behavior. This complements the existing rate limiting (nginx: 5 req/s, Flask: 100 req/min) by identifying and blocking persistent abusers.

## How It Works

### Request Tracking

The system tracks the following metrics per IP address over a rolling time window (default: 60 seconds):

- **Total requests**: Number of requests in the time window
- **Failed requests**: Count of 4xx/5xx responses (excluding 429 rate limits)
- **Rate-limited requests**: Count of 429 responses
- **Failure rate**: Percentage of failed requests
- **Rate-limit rate**: Percentage of rate-limited requests  
- **Requests per second**: Average request rate

### Abuse Detection

An IP is automatically blocked if it demonstrates any of these patterns:

1. **Excessive Request Rate**: More than 60,000 requests/minute (1000 req/s, default)
   - Indicates automated attacks or bot traffic
   
2. **High Failure Rate**: More than 50% of requests fail (default)
   - Indicates probing, scanning, or invalid requests
   
3. **Persistent Rate Limit Violations**: More than 90% of requests are rate-limited (default)
   - Indicates an IP that continues sending requests despite rate limits

### Blocking Behavior

- **Block Duration**: 5 minutes (300 seconds) by default
- **Minimum Requests**: At least 20 requests needed before judging abuse (default)
- **Automatic Unblocking**: Blocks expire automatically after the duration
- **Whitelisting**: Certain IPs can be whitelisted (never blocked)

## Configuration

Configure the IP blocker using environment variables:

```bash
# Time window for tracking metrics (seconds)
IP_BLOCKER_WINDOW_SECONDS=60

# Maximum requests per minute before blocking (default: 60000 = 1000 req/s)
IP_BLOCKER_MAX_RPM=60000

# Maximum failure rate (%) before blocking
IP_BLOCKER_MAX_FAILURE_RATE=50.0

# Maximum rate-limit rate (%) before blocking
IP_BLOCKER_MAX_RATE_LIMIT_RATE=90.0

# Block duration in seconds
IP_BLOCKER_DURATION_SECONDS=300

# Minimum requests needed to judge abuse
IP_BLOCKER_MIN_REQUESTS=20

# Whitelist localhost (for stress testing)
IP_BLOCKER_WHITELIST_LOCALHOST=true
```

## Whitelisting

### Localhost (Default)

By default, localhost IPs are whitelisted for stress testing:
- `127.0.0.1`
- `::1` (IPv6)
- `localhost`

To disable localhost whitelisting:
```bash
IP_BLOCKER_WHITELIST_LOCALHOST=false
```

### Programmatic Whitelisting

You can whitelist IPs programmatically in the Flask app:

```python
from src.security import IPBlocker

# Whitelist an IP
ip_blocker.whitelist_ip('192.168.1.100')

# Remove from whitelist
ip_blocker.remove_from_whitelist('192.168.1.100')
```

## Response Codes

### Blocked IP (403 Forbidden)

When an IP is blocked, it receives:

```json
{
  "error": "IP address blocked",
  "message": "Your IP address has been temporarily blocked due to abusive behavior. Unblock in 245 seconds.",
  "unblock_in_seconds": 245
}
```

Status code: **403 Forbidden**

## Admin Endpoints

### Check IP Status

Check the status and metrics for any IP:

```bash
# Check your own IP
curl http://localhost:5001/admin/ip-status

# Check specific IP
curl http://localhost:5001/admin/ip-status?ip=192.168.1.100
```

Response for active IP:
```json
{
  "ip": "192.168.1.100",
  "status": "active",
  "metrics": {
    "total_requests": 15,
    "failed_requests": 2,
    "rate_limited": 0,
    "failure_rate": 13.33,
    "rate_limit_rate": 0.0,
    "requests_per_second": 0.25
  }
}
```

Response for blocked IP:
```json
{
  "ip": "192.168.1.100",
  "status": "blocked",
  "blocked": true,
  "unblock_time": 1704067200.0,
  "remaining_seconds": 245,
  "metrics": {
    "total_requests": 250,
    "failed_requests": 180,
    "rate_limited": 50,
    "failure_rate": 72.0,
    "rate_limit_rate": 20.0,
    "requests_per_second": 4.17
  }
}
```

Response for whitelisted IP:
```json
{
  "ip": "127.0.0.1",
  "status": "whitelisted",
  "metrics": {
    "total_requests": 1000,
    "failed_requests": 0,
    "rate_limited": 0,
    "failure_rate": 0.0,
    "rate_limit_rate": 0.0,
    "requests_per_second": 16.67
  }
}
```

## Strategy for Handling Stress Tests

### Problem

Stress tests generate many requests from the same IP, which can trigger:
- Rate limiting (429 responses)
- High failure rates (if rate limits are hit)
- Potential IP blocking

### Solution

1. **Whitelist localhost for testing** (default enabled)
   - Stress tests from `localhost` won't be blocked
   - Allows legitimate load testing

2. **Adjust thresholds for production**
   - Lower `IP_BLOCKER_MAX_RPM` for production
   - Tighten `IP_BLOCKER_MAX_FAILURE_RATE` 
   - Enable localhost whitelisting only in development

3. **Monitor and adjust**
   - Use `/admin/ip-status` to monitor IP behavior
   - Adjust thresholds based on legitimate traffic patterns

## Integration with Existing Rate Limiting

The IP blocking system works alongside existing rate limiting:

1. **Nginx Rate Limiting** (5 req/s, burst 10)
   - First line of defense
   - Blocks excessive requests at proxy level

2. **Flask Rate Limiting** (100 req/min)
   - Second line of defense
   - Application-level rate limiting

3. **IP Blocking** (this system)
   - Third line of defense
   - Identifies persistent abusers
   - Blocks based on behavior patterns, not just rate

### Flow

```
Request → Nginx (5 req/s) → Flask (100 req/min) → IP Blocker Check → Application
                                                         ↓
                                                    [Blocked?]
                                                         ↓
                                                   403 Forbidden
```

## Best Practices

1. **Monitor Blocked IPs**: Check `/admin/ip-status` regularly to identify false positives

2. **Adjust Thresholds**: Tune thresholds based on your actual traffic patterns

3. **Whitelist Legitimate Services**: Add IPs for monitoring, load balancers, etc.

4. **Log Analysis**: Review logs to understand why IPs are being blocked

5. **Gradual Rollout**: Start with conservative thresholds and adjust based on data

## Troubleshooting

### IP Blocked During Legitimate Testing

**Solution**: Whitelist the testing IP or disable IP blocking for testing:

```bash
# Option 1: Whitelist localhost (already default)
IP_BLOCKER_WHITELIST_LOCALHOST=true

# Option 2: Increase thresholds temporarily
IP_BLOCKER_MAX_RPM=1000
IP_BLOCKER_MAX_FAILURE_RATE=80.0
```

### Too Many False Positives

**Solution**: Adjust thresholds:

```bash
# Increase thresholds (for very high-traffic legitimate services)
IP_BLOCKER_MAX_RPM=120000  # 2000 req/s
IP_BLOCKER_MAX_FAILURE_RATE=70.0
IP_BLOCKER_MIN_REQUESTS=50  # Require more requests before judging
```

### IP Not Blocked Despite Abuse

**Solution**: Lower thresholds:

```bash
# Lower thresholds (for stricter abuse detection)
IP_BLOCKER_MAX_RPM=30000  # 500 req/s
IP_BLOCKER_MAX_FAILURE_RATE=30.0
IP_BLOCKER_MIN_REQUESTS=10
```

### Checking Why an IP Was Blocked

Use the admin endpoint to see metrics:

```bash
curl http://localhost:5001/admin/ip-status?ip=192.168.1.100
```

Look at the `metrics` field to see which threshold was exceeded.

