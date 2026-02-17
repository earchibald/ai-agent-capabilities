#!/bin/bash

# AI Agent Capabilities - Automation Update Script
# 
# This script runs the full update cycle for the capability tracking framework:
# 1. Fetches latest release notes
# 2. Prompts for manual capability updates
# 3. Regenerates comparison reports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "========================================"
echo "AI Agent Capabilities Update Automation"
echo "========================================"
echo ""

# Step 1: Fetch Release Notes
echo "Step 1: Fetching latest release notes..."
echo "----------------------------------------"
cd "${REPO_ROOT}"
python3 framework/scripts/fetch_releases.py
echo ""

# Step 2: Review Release Notes
echo "Step 2: Review new release notes"
echo "----------------------------------------"
echo "Please review the release notes in agents/*/releases/"
echo ""
echo "For each new release:"
echo "  1. Read the release notes"
echo "  2. Identify capability changes"
echo "  3. Update agents/*/capabilities/current.json"
echo ""
echo "Release note files can be found at:"
for agent_dir in "${REPO_ROOT}"/agents/*/; do
    agent_name=$(basename "$agent_dir")
    releases_dir="${agent_dir}releases"
    if [ -d "$releases_dir" ]; then
        count=$(find "$releases_dir" -name "*.json" ! -name "index.json" | wc -l)
        if [ "$count" -gt 0 ]; then
            echo "  - ${agent_name}: ${count} release(s)"
        fi
    fi
done
echo ""

read -p "Have you reviewed and updated capability files? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Update cancelled. Please review release notes and update capability files."
    exit 1
fi

# Step 3: Generate Comparisons
echo ""
echo "Step 3: Generating capability comparisons..."
echo "----------------------------------------"
python3 framework/scripts/generate_comparison.py
echo ""

# Step 4: Summary
echo "========================================"
echo "Update Complete!"
echo "========================================"
echo ""
echo "Generated files:"
echo "  - comparisons/README.md"
echo "  - comparisons/comparison-matrix.json"
echo "  - comparisons/capability-summary.json"
echo ""
echo "Next steps:"
echo "  1. Review the generated comparisons"
echo "  2. Commit changes: git add . && git commit -m 'Update capabilities'"
echo "  3. Push to repository: git push"
echo ""
