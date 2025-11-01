# Gatling Stress Test for Warrior API

This directory contains Gatling performance tests for the Warrior API with rate limiting validation.

## Prerequisites

1. **Java JDK 8+** (required for Gatling)
2. **sbt (Scala Build Tool)** - Install via:
   - macOS: `brew install sbt`
   - Linux: Follow instructions at https://www.scala-sbt.org/download.html
   - Or download from https://www.scala-sbt.org/download.html

## Setup

1. Ensure the Flask app is running:
   ```bash
   python limiter.py
   ```

2. (Optional) Start nginx with the configured rate limiting:
   ```bash
   # If using Docker container
   docker run -d --name api_stress_test_nginx \
     -p 443:443 -p 80:80 \
     -v $(pwd)/nginx.conf:/etc/nginx/conf.d/default.conf \
     nginx:latest
   ```

## Running Tests

### Using sbt (Recommended)

```bash
cd gatling
sbt "Gatling / testOnly test.WarriorApiSimulation"
```

### View Results

After running, Gatling will generate an HTML report. The path will be displayed in the console output, typically:
```
gatling/target/gatling/warriorapisimulation-<timestamp>/index.html
```

Open this file in a browser to view detailed results, including:
- Response time distributions
- Request success/failure rates
- Rate limit detection (429 status codes)
- Throughput metrics

## Test Scenarios

The simulation includes multiple test phases:

1. **Warm-up Phase**: Creates 10 warriors over 10 seconds
2. **Normal Load**: Mixed workload with 50 users ramping up, then sustained 5 req/s
3. **Rate Limit Test**: Intentionally exceeds limits (10 req/s, then 15 req/s) to validate rate limiting
4. **Read Operations**: Search and count endpoints with sustained load
5. **Peak Load**: 100 users ramping up with high sustained rate

## Configuration

### Base URL

Edit `WarriorApiSimulation.scala` to change the target URL:
```scala
val httpProtocol = http
  .baseUrl("http://localhost")  // Change to nginx URL if testing through proxy
```

### Rate Limits

The test is configured to validate:
- **Nginx**: 5 requests/second (with burst of 10)
- **Flask**: 100 requests/minute per IP

The test scenarios intentionally exceed these limits to validate rate limiting behavior.

## Understanding Results

### Key Metrics

- **Response Time**: Should remain low (< 1s mean) for successful requests
- **Success Rate**: May be lower during rate limit tests (intentional)
- **429 Status Codes**: Indicates rate limiting is working correctly
- **Throughput**: Requests per second actually processed

### Rate Limit Validation

Look for:
- 429 status codes during high-load phases
- Response time spikes correlating with rate limit responses
- Successful requests dropping below the configured limit during stress phases

## Troubleshooting

### Connection Errors

- Ensure Flask app is running on port 5001
- If testing through nginx, ensure nginx is running and proxying correctly
- Check firewall settings

### Build Errors

- Ensure Java JDK is installed: `java -version`
- Ensure sbt is installed: `sbt --version`
- Try updating Scala version in `build.sbt` if compatibility issues occur

### Test Failures

- Some failures are expected during rate limit stress tests
- Check that the database schema is initialized
- Verify warrior endpoints are working with manual curl tests first

