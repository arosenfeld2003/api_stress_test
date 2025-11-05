#!/bin/bash
# Deploy nginx config to GHCR container

set -e

CONTAINER_NAME="${1:-api_stress_test_nginx}"
SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Determine which config to use
# Priority: 1) nginx.conf.local (for local testing, no SSL), 2) nginx.conf (production with SSL)
if [ -f "$PROJECT_ROOT/nginx.conf.local" ]; then
    CONFIG_PATH="$PROJECT_ROOT/nginx.conf.local"
    echo "Using nginx.conf.local (no SSL required)"
else
    CONFIG_PATH="$PROJECT_ROOT/nginx.conf"
    echo "Using nginx.conf (requires SSL certificates)"
fi

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: nginx config not found at $CONFIG_PATH"
    exit 1
fi

echo "Deploying nginx config to container: $CONTAINER_NAME"

# For Linux with --network host, replace host.docker.internal with 127.0.0.1 before copying
if [[ "$OSTYPE" == "linux-gnu"* ]] && grep -q "host.docker.internal" "$CONFIG_PATH"; then
    echo "Adjusting config for Linux host networking..."
    TEMP_CONFIG="/tmp/nginx.conf.deploy"
    sed 's/host\.docker\.internal/127.0.0.1/g' "$CONFIG_PATH" > "$TEMP_CONFIG"
    docker cp "$TEMP_CONFIG" "$CONTAINER_NAME:/etc/nginx/conf.d/default.conf"
    rm -f "$TEMP_CONFIG"
else
    # Copy config to container
    docker cp "$CONFIG_PATH" "$CONTAINER_NAME:/etc/nginx/conf.d/default.conf"
fi

# Test nginx config
echo "Testing nginx configuration..."
docker exec "$CONTAINER_NAME" nginx -t

# Reload nginx (graceful reload without dropping connections)
echo "Reloading nginx..."
docker exec "$CONTAINER_NAME" nginx -s reload

echo "✓ Nginx config deployed and reloaded successfully"
