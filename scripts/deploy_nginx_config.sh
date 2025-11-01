#!/bin/bash
# Deploy nginx config to GHCR container

set -e

CONTAINER_NAME="${1:-api_stress_test_nginx}"
CONFIG_PATH="$(dirname "$0")/../nginx.conf"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: nginx.conf not found at $CONFIG_PATH"
    exit 1
fi

echo "Deploying nginx config to container: $CONTAINER_NAME"

# Copy config to container
docker cp "$CONFIG_PATH" "$CONTAINER_NAME:/etc/nginx/conf.d/default.conf"

# Test nginx config
echo "Testing nginx configuration..."
docker exec "$CONTAINER_NAME" nginx -t

# Reload nginx (graceful reload without dropping connections)
echo "Reloading nginx..."
docker exec "$CONTAINER_NAME" nginx -s reload

echo "✓ Nginx config deployed and reloaded successfully"
