#!/bin/bash

# Setup script for stress testing
# Installs dependencies and verifies the environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Stress Test Setup ==="
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    echo "Error: Python 3.8+ is required"
    exit 1
fi
echo "✓ Python version OK"
echo ""

# Check for virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Virtual environment detected: $VIRTUAL_ENV"
    echo "✓ Using virtual environment"
else
    echo "No virtual environment detected"
    read -p "Do you want to create one? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Creating virtual environment..."
        python3 -m venv .venv
        echo "Virtual environment created at .venv"
        echo "Activate it with: source .venv/bin/activate"
        echo ""
        read -p "Do you want to activate it now? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            source .venv/bin/activate
            echo "✓ Virtual environment activated"
        fi
    fi
fi
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
cd "$PROJECT_ROOT"
pip3 install --upgrade pip
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi
echo "✓ Python dependencies installed"
echo ""

# Verify dependencies
echo "Verifying dependencies..."
python3 -c "import flask; print(f'  Flask {flask.__version__}')" || exit 1
python3 -c "import flask_limiter; print(f'  Flask-Limiter installed')" || exit 1
python3 -c "import duckdb; print(f'  DuckDB {duckdb.__version__}')" || exit 1
python3 -c "import dotenv; print(f'  python-dotenv installed')" || exit 1
echo "✓ All dependencies verified"
echo ""

# Check Java (for Gatling)
echo "Checking Java..."
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -n 1)
    echo "Found: $JAVA_VERSION"
    
    # Check Java version (basic check)
    if java -version 2>&1 | grep -qE "(version \"(1\.[89]|[2-9]|[1-9][0-9]))|version \"([8-9]|[1-9][0-9]))"; then
        echo "✓ Java version is compatible (8+)"
    else
        echo "⚠ Java version may be too old (Gatling requires Java 8+)"
    fi
else
    echo "✗ Java not found - Gatling requires Java 8+"
    echo ""
    echo "Install Java with one of these methods:"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  macOS (Homebrew):"
        echo "    brew install openjdk@11"
        echo "    brew install openjdk@17"
        echo ""
        echo "  macOS (Direct download):"
        echo "    Visit: https://www.oracle.com/java/technologies/downloads/"
        echo "    Or: https://adoptium.net/"
    else
        echo "  Linux:"
        echo "    sudo apt-get install openjdk-11-jdk  # Ubuntu/Debian"
        echo "    sudo yum install java-11-openjdk-devel  # CentOS/RHEL"
        echo ""
        echo "  Or download from: https://adoptium.net/"
    fi
    echo ""
fi
echo ""

# Check Gatling
API_STRESS_DIR="$PROJECT_ROOT/api_under_stress"
if [ -d "$API_STRESS_DIR/deps/gatling-charts-highcharts-bundle-3.10.5" ]; then
    echo "✓ Gatling found in api_under_stress/deps/"
else
    echo "⚠ Gatling not found - download and extract to api_under_stress/deps/"
fi
echo ""

# Initialize database
echo "Initializing database..."
python3 -c "from src.db.connection import get_connection; \
    with get_connection(read_only=False, apply_schema=True) as con: \
    print('✓ Database initialized')" || {
    echo "⚠ Database initialization failed (may already exist)"
}
echo ""

echo "=== Setup Complete ==="
echo ""
echo "You can now run stress tests with:"
echo "  ./scripts/run_stress_test.sh"
echo ""

