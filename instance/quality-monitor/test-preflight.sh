#!/bin/bash
# Test script for the quality monitor preflight

set -e

echo "Testing Quality Monitor Preflight Script"
echo "========================================"

# Set up environment
export PYTHONPATH="$(pwd)/presets/shared/preflight:$(pwd)/.claude/skills"
export BOT_INSTANCE_ID="quality-monitor-test"
export BOT_MEMORY_URL="http://localhost:8080"

# Check for GH_TOKEN
if [ -z "$GH_TOKEN" ]; then
    echo "Warning: GH_TOKEN not set. GitHub CLI operations may fail."
    echo "Set it with: export GH_TOKEN=your_token"
fi

# Run preflight
echo ""
echo "Running preflight script..."
echo ""

python3 instance/quality-monitor/agent/workflows/quality-monitor/preflight/01-scan-prs-for-violations.py

echo ""
echo "Test complete!"
