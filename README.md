# AI Agent Capabilities Tracker

Structured data tracking the capabilities of AI coding agents, with automated comparison generation.

## Tracked Agents

| Agent | Vendor | Type |
|-------|--------|------|
| [Claude Code](agents/claude-code/) | Anthropic | Terminal CLI, IDE, Web, Desktop |
| [GitHub Copilot (VS Code)](agents/vscode-copilot/) | GitHub / Microsoft | IDE extension |
| [GitHub Copilot CLI](agents/copilot-cli/) | GitHub / Microsoft | Terminal CLI (preview) |
| [Gemini CLI](agents/gemini-cli/) | Google | Terminal CLI (open source) |

## Usage

```bash
# Generate side-by-side comparison
python3 framework/scripts/generate_comparison.py

# Fetch latest release notes (GitHub API sources)
python3 framework/scripts/fetch_releases.py

# Validate data against schemas
python3 framework/scripts/validate_framework.py
```

View the generated comparison: [comparisons/README.md](comparisons/README.md)

## Repository Structure

```
agents/
  {agent}/capabilities/current.json   # Capability data (the core product)
  {agent}/releases/                   # Release note history
comparisons/                          # Generated comparison outputs
framework/
  schemas/capability-schema.json      # JSON schema for capability files
  scripts/generate_comparison.py      # Comparison generator
  scripts/fetch_releases.py           # Release note fetcher
  scripts/validate_framework.py       # Data validation
```

## Adding a New Agent

1. Create `agents/{agent-id}/capabilities/current.json` following the schema
2. Add fetch config to `framework/scripts/fetch_releases.py`
3. Run `python3 framework/scripts/generate_comparison.py`

## Documentation Sources

See [SOURCES.md](SOURCES.md) for the official documentation URLs used to verify capability data.

## Data Accuracy

Capability data was last verified against live documentation on 2026-02-18.
Each agent's `current.json` includes a `documentation` field with source URLs.
