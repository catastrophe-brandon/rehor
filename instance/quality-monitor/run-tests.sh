#!/bin/bash
# Run tests for quality monitor preflight script

set -e

echo "Running Quality Monitor Preflight Tests"
echo "========================================"

# Ensure pytest is available
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest not found. Install with: pip install pytest"
    exit 1
fi

# Run tests from repo root
cd "$(dirname "$0")/../.."

# Run tests with verbose output
pytest instance/quality-monitor/agent/workflows/quality-monitor/preflight/tests/ -v

echo ""
echo "✓ All tests passed!"
