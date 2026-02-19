---
name: source-maintenance
description: Fix broken source URLs in the AI Agent Capabilities tracker. Use this skill when assigned an issue with the broken-source label containing unreachable documentation URLs that need replacement.
---

# Source Maintenance Skill

You are fixing broken source URLs in the AI Agent Capabilities tracker repository.

## Context

This repository tracks capabilities of AI coding agents (Claude Code, VS Code Copilot, Copilot CLI, Gemini CLI). Each agent has a `agents/<name>/capabilities/current.json` file with source citations that link to official documentation. Documentation sites restructure periodically, breaking these URLs.

## Your Tools

The repository includes `framework/scripts/verify_sources.py` with maintenance modes:

```bash
# See what's broken (reads saved verification results)
python3 framework/scripts/verify_sources.py --report

# Apply a URL replacement mapping
python3 framework/scripts/verify_sources.py --apply-fixes fixes.json

# Preview changes without writing
python3 framework/scripts/verify_sources.py --apply-fixes fixes.json --dry-run

# Run full verification to confirm fixes
python3 framework/scripts/verify_sources.py
```

## Workflow

### Step 1: Understand the broken sources

Run `python3 framework/scripts/verify_sources.py --report` to get the current list of broken URLs.

Also parse the issue body for the machine-readable block:
```
<!-- BROKEN_SOURCES_JSON
{"agent":"...","url":"...","capability":"..."}
-->
```

### Step 2: Research replacement URLs

For each broken URL, search the same documentation site for where the content moved:

1. **Check the site's top-level navigation** — fetch the docs index page and look for the capability topic
2. **Try common restructuring patterns:**
   - Flat page to subdirectory: `/docs/copilot/page-name` → `/docs/copilot/section/page-name`
   - VS Code pattern: `reference/`, `guides/`, `agents/`, `customization/` subdirectories
   - GitHub docs pattern: `how-tos/`, `tutorials/`, `concepts/`, `reference/` sections
3. **Verify each candidate URL is live** before using it:
   ```bash
   curl -Is "https://example.com/new-url" | head -1
   ```
   Only use URLs that return `HTTP/2 200` or `HTTP/1.1 200`.

### Step 3: Create and apply fixes

Create a `fixes.json` file mapping each broken URL to its confirmed replacement:

**Simple format:**
```json
{
  "https://old-url.com/broken": "https://old-url.com/new-location"
}
```

**Extended format** (when the page granularity changes):
```json
{
  "https://old-url.com/broken": {
    "url": "https://old-url.com/new-location",
    "sourceGranularity": "dedicated"
  }
}
```

The `sourceGranularity` field must be one of:
- `dedicated` — URL is specifically about this capability (best)
- `section` — URL has a `#fragment` anchor pointing to a relevant section
- `excerpt` — Broad page; a verbatim 50-300 char `excerpt` field is required

Apply with: `python3 framework/scripts/verify_sources.py --apply-fixes fixes.json`

### Step 4: Verify and report

Run full verification: `python3 framework/scripts/verify_sources.py`

Validate schema compliance: `python3 framework/scripts/validate_framework.py`

### Step 5: Create the PR

Open a PR with:
- **Title:** `fix: resolve N broken source URLs`
- **Description template:**

```markdown
## Broken Source Fixes — YYYY-MM-DD

Triggered by: #<issue-number>

### Fixed (N URLs)
| Agent | Capability | Old URL | New URL | Confidence |
|-------|-----------|---------|---------|------------|
| ... | ... | ... | ... | High/Medium |

### Unresolvable (N URLs)
These URLs could not be matched to a replacement. The content may have been removed.
- `agent`: `capability` — `url` — Reason: ...

### Verification result
- Reachability: X/Y pass
- Relevance: X/Y pass
```

Clean up the `fixes.json` file before committing (do not commit it).

## Important Rules

- NEVER guess a URL. Every replacement must return HTTP 200 when fetched.
- Prefer URLs from the SAME domain as the broken URL.
- When upgrading from `excerpt` to `dedicated`/`section`, the `excerpt` field is automatically removed by `--apply-fixes`.
- Always re-run `verify_sources.py` after applying fixes to confirm they work.
- Commit message format: `fix: resolve N broken source URLs [automated]`
