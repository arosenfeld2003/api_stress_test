#!/bin/bash

# Script to run the Gatling stress tests
# This script:
# 1. Generates test resources (warriors-payloads.tsv and search-terms.tsv)
# 2. Starts the Flask app on port 9999
# 3. Runs the Gatling stress tests
# 4. Shows the results

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_STRESS_DIR="$PROJECT_ROOT/api_under_stress"

echo "=== API Stress Test Runner ==="
echo ""

# Check Python dependencies
echo "Checking Python dependencies..."
cd "$PROJECT_ROOT"
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Error: Flask is not installed"
    echo "Installing dependencies from requirements.txt..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
    echo "✓ Dependencies installed"
else
    echo "✓ Python dependencies OK"
fi
echo ""

# Check if api_under_stress directory exists
if [ ! -d "$API_STRESS_DIR" ]; then
    echo "Error: api_under_stress directory not found at $API_STRESS_DIR"
    exit 1
fi

# Step 1: Generate test resources
echo "Step 1: Generating test resources..."
cd "$API_STRESS_DIR"
python3 stress-test/generate_resources.py
if [ $? -ne 0 ]; then
    echo "Error: Failed to generate test resources"
    exit 1
fi
echo "✓ Test resources generated"
echo ""

# Step 2: Check if Flask app is already running
echo "Step 2: Checking if Flask app is running on port 9999..."
if lsof -Pi :9999 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠ Flask app is already running on port 9999"
    read -p "Do you want to stop it and restart? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing Flask app..."
        pkill -f "limiter.py" || true
        sleep 2
    else
        echo "Using existing Flask app instance"
    fi
else
    echo "Starting Flask app on port 9999..."
    cd "$PROJECT_ROOT"
    
    # Verify Python can import Flask before starting
    if ! python3 -c "import flask; import flask_limiter; import duckdb" 2>/dev/null; then
        echo "Error: Required Python packages are not installed"
        echo "Please run: pip3 install -r requirements.txt"
        exit 1
    fi
    
    PORT=9999 FLASK_THREADED=true python3 limiter.py &
    FLASK_PID=$!
    echo "Flask app started with PID $FLASK_PID"
    
    # Wait for Flask to be ready
    echo "Waiting for Flask app to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:9999/health > /dev/null 2>&1; then
            echo "✓ Flask app is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Error: Flask app did not start within 30 seconds"
            kill $FLASK_PID 2>/dev/null || true
            exit 1
        fi
        sleep 1
    done
fi
echo ""

# Step 3: Run Gatling stress tests
echo "Step 3: Running Gatling stress tests..."
cd "$API_STRESS_DIR"

# Check for Java
if ! command -v java &> /dev/null; then
    echo "Error: Java is not installed or not in PATH"
    echo ""
    echo "Gatling requires Java 8 or higher."
    echo "Install Java with one of these methods:"
    echo ""
    echo "  macOS (Homebrew):"
    echo "    brew install openjdk@11"
    echo "    brew install openjdk@17"
    echo ""
    echo "  macOS (Direct download):"
    echo "    Visit: https://www.oracle.com/java/technologies/downloads/"
    echo "    Or: https://adoptium.net/"
    echo ""
    echo "  After installing, verify with: java -version"
    exit 1
fi

# Verify Java version
JAVA_VERSION=$(java -version 2>&1 | head -n 1)
echo "Found Java: $JAVA_VERSION"

# Check if Java version is 8 or higher (basic check)
if ! java -version 2>&1 | grep -qE "(version \"(1\.[89]|[2-9]|[1-9][0-9]))|version \"([8-9]|[1-9][0-9]))"; then
    echo "Warning: Java 8 or higher is recommended for Gatling"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

GATLING_BIN_DIR="./deps/gatling-charts-highcharts-bundle-3.10.5/bin"
WORKSPACE="$PWD/stress-test"

if [ ! -f "$GATLING_BIN_DIR/gatling.sh" ]; then
    echo "Error: Gatling not found at $GATLING_BIN_DIR"
    echo "Please ensure Gatling is installed in api_under_stress/deps/"
    exit 1
fi

echo "Running EngLabStressTest simulation..."
sh "$GATLING_BIN_DIR/gatling.sh" -rm local -s EngLabStressTest \
    -rd "Stress Test Run" \
    -rf "$WORKSPACE/user-files/results" \
    -sf "$WORKSPACE/user-files/simulations" \
    -rsf "$WORKSPACE/user-files/resources"

echo ""
echo "=== Stress Test Complete ==="
echo ""

# Step 4: Show results
LATEST_RESULT=$(find "$WORKSPACE/user-files/results" -name "englabstresstest-*" -type d | sort -r | head -1)
if [ -n "$LATEST_RESULT" ] && [ -f "$LATEST_RESULT/index.html" ]; then
    echo "Results available at:"
    echo "  file://$LATEST_RESULT/index.html"
    echo ""
    echo "Open in browser with:"
    echo "  open '$LATEST_RESULT/index.html'"
    echo ""
fi

# Step 5: Test counting endpoint
echo "Step 5: Testing counting endpoint..."
sleep 3
curl -s "http://localhost:9999/counting-warriors" | python3 -m json.tool || echo "Failed to get count"
echo ""

# Cleanup: Kill Flask app if we started it
if [ -n "$FLASK_PID" ]; then
    echo "Flask app is still running (PID $FLASK_PID)"
    echo "To stop it, run: kill $FLASK_PID"
fi

echo ""
echo "=== Done ==="

