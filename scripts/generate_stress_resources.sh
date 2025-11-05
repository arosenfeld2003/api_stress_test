#!/bin/bash

# Script to generate stress test resources
# This is a convenience wrapper around the Python script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_STRESS_DIR="$PROJECT_ROOT/api_under_stress"

if [ ! -d "$API_STRESS_DIR" ]; then
    echo "Error: api_under_stress directory not found at $API_STRESS_DIR"
    exit 1
fi

echo "Generating stress test resources..."
cd "$API_STRESS_DIR"
python3 stress-test/generate_resources.py

echo ""
echo "✓ Resources generated:"
echo "  - $API_STRESS_DIR/stress-test/user-files/resources/warriors-payloads.tsv"
echo "  - $API_STRESS_DIR/stress-test/user-files/resources/search-terms.tsv"

