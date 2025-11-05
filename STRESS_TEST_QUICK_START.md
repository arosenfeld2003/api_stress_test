# Quick Start for Stress Tests

## Before Running Tests

**Always start Flask first!** The stress tests require Flask to be running on port 9999.

### Start Flask (Required)

```bash
./scripts/start_flask_for_stress_test.sh
```

This will:
- Check if Flask is already running
- Start Flask on port 9999 if needed
- Wait for Flask to be ready
- Show you the PID so you can stop it later

### Verify Flask is Running

```bash
curl http://localhost:9999/health
# Should return: {"status":"ok"}
```

## Run Stress Tests

### Option 1: Automated (Recommended)
```bash
./scripts/run_stress_test.sh
```

This script will:
1. Check/install dependencies
2. Generate test resources
3. Start Flask if not running
4. Run Gatling stress tests
5. Show results location

### Option 2: Manual
```bash
# Terminal 1: Start Flask
./scripts/start_flask_for_stress_test.sh

# Terminal 2: Run Gatling tests
cd api_under_stress
./stress-test/run-test.sh
```

## Stop Flask

When you're done with stress tests:

```bash
# Option 1: Kill by PID (shown when Flask starts)
kill <PID>

# Option 2: Kill by process name
pkill -f "limiter.py"
```

## Troubleshooting

### "Connection refused" errors

This means Flask isn't running. Start it:

```bash
./scripts/start_flask_for_stress_test.sh
```

### Flask won't start

```bash
# Check for errors
tail -50 /tmp/flask_stress_test.log

# Check if port is in use
lsof -i :9999

# Kill existing process
pkill -f "limiter.py"
```

### Tests timing out

- Make sure Flask is running: `curl http://localhost:9999/health`
- Check Flask logs: `tail -f /tmp/flask_stress_test.log`
- Verify database is accessible: `ls -la data/app.duckdb`

## Common Workflow

```bash
# 1. Start Flask (in background or separate terminal)
./scripts/start_flask_for_stress_test.sh

# 2. Verify it's working
curl http://localhost:9999/health

# 3. Run stress tests
./scripts/run_stress_test.sh

# 4. View results (browser will open automatically)
# Results are in: api_under_stress/stress-test/user-files/results/

# 5. Stop Flask when done
pkill -f "limiter.py"
```

