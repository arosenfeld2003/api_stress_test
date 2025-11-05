#!/bin/bash

# Script to run the Gatling stress tests through nginx
# This script:
# 1. Generates test resources (warriors-payloads.tsv and search-terms.tsv)
# 2. Starts/checks nginx container
# 3. Starts the Flask app on port 5001 (nginx backend)
# 4. Deploys nginx configuration
# 5. Runs the Gatling stress tests through nginx (port 80)
# 6. Shows the results

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_STRESS_DIR="$PROJECT_ROOT/api_under_stress"
NGINX_CONTAINER_NAME="${NGINX_CONTAINER_NAME:-api_stress_test_nginx}"

echo "=== API Stress Test Runner (via Nginx) ==="
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

# Step 2: Check/start nginx container
echo "Step 2: Checking nginx container..."
cd "$PROJECT_ROOT"

if docker ps -a --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER_NAME}$"; then
    if docker ps --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER_NAME}$"; then
        echo "✓ Nginx container is running"
    else
        echo "Starting existing nginx container..."
        docker start "$NGINX_CONTAINER_NAME"
        sleep 2
    fi
else
    echo "Nginx container not found. Creating and starting..."
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        echo "Error: Docker is not installed or not in PATH"
        echo "Please install Docker to run nginx container"
        exit 1
    fi
    
    # Build or pull nginx image
    if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "ghcr.io/arosenfeld2003/api-stress-test-nginx:latest"; then
        echo "Using existing nginx image"
    else
        echo "Building nginx image..."
        ./scripts/build_nginx_image.sh || {
            echo "Warning: Could not build nginx image, trying to pull..."
            docker pull ghcr.io/arosenfeld2003/api-stress-test-nginx:latest || {
                echo "Error: Could not build or pull nginx image"
                echo "Please run: ./scripts/build_nginx_image.sh"
                exit 1
            }
        }
    fi
    
    # Run nginx container
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        docker run -d \
          --name "$NGINX_CONTAINER_NAME" \
          --network host \
          -p 80:80 \
          ghcr.io/arosenfeld2003/api-stress-test-nginx:latest
    else
        # macOS/Windows with Docker Desktop
        docker run -d \
          --name "$NGINX_CONTAINER_NAME" \
          -p 80:80 \
          ghcr.io/arosenfeld2003/api-stress-test-nginx:latest
    fi
    
    sleep 2
    echo "✓ Nginx container started"
fi

# Deploy nginx config (use local config for testing)
echo "Deploying nginx configuration..."
if [ -f "$PROJECT_ROOT/nginx.conf.local" ]; then
    # For Linux with --network host, use 127.0.0.1 instead of host.docker.internal
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Create temp config with 127.0.0.1 for Linux
        TEMP_CONFIG="/tmp/nginx.conf.stress_test"
        sed 's/host\.docker\.internal/127.0.0.1/g' "$PROJECT_ROOT/nginx.conf.local" > "$TEMP_CONFIG"
        docker cp "$TEMP_CONFIG" "${NGINX_CONTAINER_NAME}:/etc/nginx/conf.d/default.conf"
        rm -f "$TEMP_CONFIG"
    else
        # macOS/Windows: use host.docker.internal
        docker cp "$PROJECT_ROOT/nginx.conf.local" "${NGINX_CONTAINER_NAME}:/etc/nginx/conf.d/default.conf"
    fi
    
    docker exec "$NGINX_CONTAINER_NAME" nginx -t
    docker exec "$NGINX_CONTAINER_NAME" nginx -s reload
    echo "✓ Nginx configuration deployed"
else
    echo "Warning: nginx.conf.local not found, using default config"
fi
echo ""

# Step 3: Check/start Flask app on port 5001
echo "Step 3: Checking Flask app on port 5001..."
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null ; then
    if curl -s http://localhost:5001/health > /dev/null 2>&1; then
        echo "✓ Flask app is already running on port 5001"
        HEALTH_RESPONSE=$(curl -s http://localhost:5001/health)
        echo "  Health check: $HEALTH_RESPONSE"
        FLASK_PID=""
    else
        echo "⚠ Port 5001 is in use but not responding to health checks"
        read -p "Kill existing process and restart Flask? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Stopping existing process..."
            pkill -f "limiter.py" || true
            sleep 2
        else
            echo "Error: Cannot proceed without working Flask app"
            exit 1
        fi
    fi
else
    echo "Starting Flask app on port 5001..."
    cd "$PROJECT_ROOT"
    
    # Verify Python can import Flask before starting
    if ! python3 -c "import flask; import flask_limiter; import duckdb" 2>/dev/null; then
        echo "Error: Required Python packages are not installed"
        echo "Please run: pip3 install -r requirements.txt"
        exit 1
    fi
    
    # Start Flask app in background with high rate limit for stress testing
    PORT=5001 FLASK_THREADED=true FLASK_RATE_LIMIT=120000 USE_DB_POOL=true DB_POOL_SIZE=10 DB_MAX_CONNECTIONS=20 python3 limiter.py > /tmp/flask_stress_test.log 2>&1 &
    FLASK_PID=$!
    echo "Flask app started with PID $FLASK_PID"
    echo "Logs available at: /tmp/flask_stress_test.log"
    
    # Wait for Flask to be ready
    echo "Waiting for Flask app to be ready..."
    MAX_WAIT=30
    for i in $(seq 1 $MAX_WAIT); do
        if curl -s http://localhost:5001/health > /dev/null 2>&1; then
            HEALTH_CHECK=$(curl -s http://localhost:5001/health)
            if echo "$HEALTH_CHECK" | grep -q "ok"; then
                echo "✓ Flask app is ready and responding"
                break
            fi
        fi
        
        if ! kill -0 $FLASK_PID 2>/dev/null; then
            echo "Error: Flask app process died unexpectedly"
            tail -20 /tmp/flask_stress_test.log
            exit 1
        fi
        
        if [ $i -eq $MAX_WAIT ]; then
            echo "Error: Flask app did not become ready within ${MAX_WAIT} seconds"
            tail -20 /tmp/flask_stress_test.log
            kill $FLASK_PID 2>/dev/null || true
            exit 1
        fi
        
        if [ $((i % 5)) -eq 0 ]; then
            echo "  Still waiting... (${i}/${MAX_WAIT}s)"
        fi
        sleep 1
    done
fi
echo ""

# Step 4: Verify nginx can reach Flask
echo "Step 4: Verifying nginx → Flask connection..."
MAX_WAIT=10
for i in $(seq 1 $MAX_WAIT); do
    if curl -s http://localhost:80/health > /dev/null 2>&1; then
        HEALTH_CHECK=$(curl -s http://localhost:80/health)
        if echo "$HEALTH_CHECK" | grep -q "ok"; then
            echo "✓ Nginx is accessible and forwarding to Flask"
            break
        fi
    fi
    
    if [ $i -eq $MAX_WAIT ]; then
        echo "Error: Nginx is not accessible or cannot reach Flask"
        echo "Check nginx logs: docker logs $NGINX_CONTAINER_NAME"
        echo "Check Flask is running on port 5001"
        exit 1
    fi
    
    sleep 1
done
echo ""

# Step 5: Run Gatling stress tests
echo "Step 5: Running Gatling stress tests..."
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

# Step 6: Test counting endpoint through nginx
echo "Step 6: Testing counting endpoint through nginx..."
sleep 3
curl -s "http://localhost:80/counting-warriors" | python3 -m json.tool || echo "Failed to get count"
echo ""

# Cleanup info
echo "=== Services Status ==="
if [ -n "$FLASK_PID" ]; then
    echo "Flask app is running (PID $FLASK_PID)"
    echo "  To stop: kill $FLASK_PID"
fi
echo "Nginx container: $NGINX_CONTAINER_NAME"
echo "  To stop: docker stop $NGINX_CONTAINER_NAME"
echo "  To view logs: docker logs $NGINX_CONTAINER_NAME"
echo ""
echo "=== Done ==="

