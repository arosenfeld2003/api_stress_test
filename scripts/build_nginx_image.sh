#!/bin/bash
# Build nginx Docker image for API Stress Test

set -e

IMAGE_NAME="${1:-ghcr.io/arosenfeld2003/api-stress-test-nginx:latest}"
BUILD_CONTEXT="$(dirname "$0")/.."

echo "Building nginx Docker image: $IMAGE_NAME"
echo "Build context: $BUILD_CONTEXT"

cd "$BUILD_CONTEXT"

# Build the image
docker build -f Dockerfile.nginx -t "$IMAGE_NAME" .

echo "✓ Image built successfully: $IMAGE_NAME"
echo ""
echo "To run the container:"
echo "  # For macOS/Windows (Docker Desktop):"
echo "  docker run -d --name api_stress_test_nginx -p 443:443 -p 80:80 $IMAGE_NAME"
echo "  # For Linux:"
echo "  docker run -d --name api_stress_test_nginx -p 443:443 -p 80:80 --network host $IMAGE_NAME"
echo ""
echo "To push to GHCR (requires authentication):"
echo "  docker login ghcr.io"
echo "  docker push $IMAGE_NAME"

