# Getting Started Guide

Welcome to the AI Agent Capabilities Tracking Framework!

## Quick Overview

This repository helps you:
- 📊 **Compare** AI coding agent capabilities side-by-side
- 🔍 **Track** new features and updates automatically
- 📝 **Document** capabilities in a structured format
- 🤖 **Automate** updates with scripts and workflows

## Prerequisites

- Python 3.8 or higher
- Git
- Basic familiarity with JSON and command line

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/earchibald/ai-agent-capabilities.git
cd ai-agent-capabilities
```

### 2. Verify the Framework

Run the validation script to ensure everything is set up correctly:

```bash
python3 framework/scripts/validate_framework.py
```

You should see all checks pass with ✅.

## Daily Usage

### View Current Comparisons

The latest capability comparison is always available in:

```
comparisons/README.md
```

Open this file to see a side-by-side comparison of all tracked agents.

### Update Comparisons

If capability files have been updated, regenerate the comparisons:

```bash
python3 framework/scripts/generate_comparison.py
```

This creates/updates:
- `comparisons/README.md` - Human-readable comparison table
- `comparisons/comparison-matrix.json` - Structured data
- `comparisons/capability-summary.json` - Statistics

### Check for New Releases

Fetch the latest release notes from all tracked agents:

```bash
python3 framework/scripts/fetch_releases.py
```

This downloads release notes from the past 2 months into `agents/*/releases/`.

### Full Update Cycle

To run the complete update workflow:

```bash
bash framework/scripts/update_automation.sh
```

This will:
1. Fetch latest release notes
2. Prompt you to review and update capabilities
3. Regenerate comparisons

## Weekly Maintenance

### Reviewing New Releases

1. Check for new release files:
   ```bash
   ls agents/*/releases/
   ```

2. Read each new release file to identify capability changes

3. Update the corresponding capability file:
   ```bash
   vim agents/vscode-copilot/capabilities/current.json
   ```

4. Regenerate comparisons:
   ```bash
   python3 framework/scripts/generate_comparison.py
   ```

5. Commit changes:
   ```bash
   git add .
   git commit -m "Update capabilities based on new releases"
   git push
   ```

## Understanding the Structure

### Capability Files

Located in `agents/*/capabilities/current.json`, these files contain:

- **agent**: Metadata about the agent (name, vendor, version)
- **capabilities**: Array of capability objects with:
  - `category`: Capability category (e.g., "code-completion")
  - `name`: Capability name
  - `description`: What it does
  - `available`: Whether it's available
  - `tier`: Pricing tier (free, pro, business, enterprise)
  - `maturityLevel`: Stability (experimental, beta, stable, deprecated)

Example:
```json
{
  "category": "code-completion",
  "name": "Inline Code Suggestions",
  "description": "Real-time code completions as you type",
  "available": true,
  "tier": "free",
  "maturityLevel": "stable"
}
```

### Release Note Files

Located in `agents/*/releases/*.json`, these track:

- **version**: Release version
- **releaseDate**: When it was released
- **changes**: Array of changes with type and description
- **capabilitiesAdded/Modified/Removed**: Capability changes

## Automation

### GitHub Actions

The repository includes a GitHub Actions workflow that:

- Runs daily to fetch new release notes
- Creates a PR when new releases are found
- Auto-updates comparisons when capability files change

To enable this:
1. The workflow is already in `.github/workflows/update-capabilities.yml`
2. It runs automatically on schedule
3. Manual trigger available via GitHub UI

## Adding a New Agent

1. Create the directory structure:
   ```bash
   mkdir -p agents/new-agent/{capabilities,documentation,releases}
   ```

2. Create `agents/new-agent/capabilities/current.json` following the schema

3. Add agent configuration to `framework/scripts/fetch_releases.py`

4. Add documentation sources to `SOURCES.md`

5. Run the comparison generator

## Troubleshooting

### Validation Fails

Run the validation script to see specific errors:
```bash
python3 framework/scripts/validate_framework.py
```

### Scripts Not Executable

Make them executable:
```bash
chmod +x framework/scripts/*.py framework/scripts/*.sh
```

### JSON Syntax Errors

Validate JSON files:
```bash
python3 -m json.tool agents/vscode-copilot/capabilities/current.json
```

## Best Practices

1. **Always validate** after editing capability files
2. **Document sources** for all capability claims
3. **Use consistent naming** across agents
4. **Update comparisons** after any capability changes
5. **Review release notes** weekly
6. **Commit frequently** with descriptive messages

## Getting Help

- Read [FRAMEWORK.md](FRAMEWORK.md) for detailed documentation
- Check [SOURCES.md](SOURCES.md) for official documentation links
- Review existing capability files as examples

## Next Steps

1. ✅ Run validation script
2. ✅ Review current comparisons
3. ✅ Fetch latest release notes
4. ✅ Set up GitHub Actions (if not already done)
5. ✅ Schedule weekly reviews

Happy tracking! 🚀
