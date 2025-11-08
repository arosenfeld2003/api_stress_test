#!/bin/bash
# Complete PostgreSQL setup script for warrior API
# This automates the entire migration from DuckDB to PostgreSQL

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "======================================"
echo "PostgreSQL Setup for Warrior API"
echo "======================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "1. Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "  Install Docker from: https://www.docker.com/get-started"
    exit 1
fi
echo -e "${GREEN}✓ Docker installed${NC}"

# Check docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠ docker-compose not found, trying 'docker compose'${NC}"
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi
echo -e "${GREEN}✓ Docker Compose available${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 installed${NC}"

# Install Python dependencies
echo ""
echo "2. Installing Python dependencies..."
pip install -q psycopg2-binary || pip3 install -q psycopg2-binary
echo -e "${GREEN}✓ psycopg2-binary installed${NC}"

# Stop existing services
echo ""
echo "3. Stopping existing services..."
pkill -f gunicorn || echo "  No gunicorn processes found"
sleep 1

# Start PostgreSQL with Docker
echo ""
echo "4. Starting PostgreSQL container..."
$DOCKER_COMPOSE up -d postgres

# Wait for PostgreSQL to be ready
echo "  Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec warrior-postgres pg_isready -U warrior -d warrior_api &> /dev/null; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ PostgreSQL failed to start${NC}"
        echo "  Check logs with: docker logs warrior-postgres"
        exit 1
    fi
    sleep 1
done

# Schema is auto-initialized by docker-compose
echo ""
echo "5. Verifying schema..."
docker exec warrior-postgres psql -U warrior -d warrior_api -c "\dt warrior" &> /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Schema initialized${NC}"
else
    echo -e "${RED}✗ Schema initialization failed${NC}"
    exit 1
fi

# Migrate data if DuckDB exists
echo ""
echo "6. Checking for existing DuckDB data..."
if [ -f "./data/app.duckdb" ]; then
    echo "  Found DuckDB database, migrating data..."
    
    # Backup DuckDB first
    cp ./data/app.duckdb "./data/app.duckdb.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✓ DuckDB backup created${NC}"
    
    # Run migration
    python3 scripts/migrate_duckdb_to_postgres.py --duckdb-path ./data/app.duckdb
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Data migration complete${NC}"
    else
        echo -e "${YELLOW}⚠ Data migration had issues (see above)${NC}"
    fi
else
    echo "  No existing DuckDB data found (this is fine for new installs)"
fi

# Create/update .env file
echo ""
echo "7. Configuring environment..."
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Database configuration
DB_MODE=postgresql

# PostgreSQL connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=warrior_api
POSTGRES_USER=warrior
POSTGRES_PASSWORD=warrior_dev_password

# Connection pool sizing
DB_POOL_MIN=20
DB_POOL_MAX=100

# Gunicorn configuration
PORT=5001
EOF
    echo -e "${GREEN}✓ Created .env file${NC}"
else
    # Update existing .env to use PostgreSQL
    if grep -q "^DB_MODE=" .env; then
        sed -i.bak 's/^DB_MODE=.*/DB_MODE=postgresql/' .env
        echo -e "${GREEN}✓ Updated .env to use PostgreSQL${NC}"
    else
        echo "DB_MODE=postgresql" >> .env
        echo -e "${GREEN}✓ Added DB_MODE to .env${NC}"
    fi
fi

# Start Flask application
echo ""
echo "8. Starting Flask application..."
export $(cat .env | xargs)
gunicorn -c gunicorn_config.py "limiter:app" --daemon

sleep 3

# Verify application
echo ""
echo "9. Verifying application..."
if curl -s http://localhost:5001/counting-warriors > /dev/null; then
    echo -e "${GREEN}✓ Application is running${NC}"
    
    # Get count
    COUNT=$(curl -s http://localhost:5001/counting-warriors | python3 -c "import sys, json; print(json.load(sys.stdin)['count'])")
    echo "  Current warrior count: $COUNT"
else
    echo -e "${RED}✗ Application failed to start${NC}"
    echo "  Check logs: tail -f /tmp/gunicorn_error.log"
    exit 1
fi

# Display connection info
echo ""
echo "======================================"
echo -e "${GREEN}PostgreSQL Setup Complete!${NC}"
echo "======================================"
echo ""
echo "Services:"
echo "  • Flask API:    http://localhost:5001"
echo "  • PostgreSQL:   localhost:5432 (warrior/warrior_dev_password)"
echo "  • pgAdmin:      http://localhost:5050 (start with: $DOCKER_COMPOSE up -d pgadmin)"
echo ""
echo "Monitoring:"
echo "  • App logs:     tail -f /tmp/gunicorn_error.log"
echo "  • DB logs:      docker logs -f warrior-postgres"
echo "  • DB console:   docker exec -it warrior-postgres psql -U warrior -d warrior_api"
echo ""
echo "Management:"
echo "  • Stop all:     $DOCKER_COMPOSE down"
echo "  • Restart DB:   $DOCKER_COMPOSE restart postgres"
echo "  • Restart app:  pkill gunicorn && gunicorn -c gunicorn_config.py 'limiter:app' --daemon"
echo ""
echo "Next steps:"
echo "  1. Run stress test: cd api_under_stress/stress-test && ../deps/gatling-charts-highcharts-bundle-3.10.5/bin/gatling.sh -s EngLabStressTest"
echo "  2. Compare results with previous DuckDB run"
echo "  3. Check success rate (should be >95% vs previous ~13%)"
echo ""

