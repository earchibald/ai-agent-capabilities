# Copilot Coding Agent Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire up the Copilot Coding Agent as the intelligent layer for fixing broken sources and discovering new capabilities.

**Architecture:** Two GitHub Actions workflows trigger the coding agent via issue assignment. Two skills (`.github/skills/`) teach the agent how to use existing scripts, research documentation sites, and produce structured output as PRs.

**Tech Stack:** GitHub Actions YAML, Copilot agent skills (Markdown+YAML frontmatter), existing Python scripts (unchanged)

---

### Task 1: Create the source-maintenance skill

**Files:**
- Create: `.github/skills/source-maintenance/SKILL.md`

**Step 1: Create the skill directory and file**

```markdown
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
```

**Step 2: Verify the skill file structure**

Run: `ls -la .github/skills/source-maintenance/SKILL.md`
Expected: file exists with non-zero size

**Step 3: Commit**

```bash
git add .github/skills/source-maintenance/SKILL.md
git commit -m "feat: add source-maintenance skill for Copilot coding agent"
```

---

### Task 2: Create the research-leads skill

**Files:**
- Create: `.github/skills/research-leads/SKILL.md`

**Step 1: Create the skill directory and file**

```markdown
---
name: research-leads
description: Research new capabilities and changes for tracked AI coding agents. Use this skill when assigned a research-leads issue to discover new features, or when asked to revise a research PR.
---

# Research Leads Skill

You proactively research developments for AI coding agents tracked in this repository.

## Context

This repository tracks capabilities of these AI coding agents:
- **claude-code** (Anthropic) — CLI agent for code generation, editing, debugging
- **copilot-cli** (GitHub) — CLI companion for terminal workflows
- **gemini-cli** (Google) — CLI agent powered by Gemini models
- **vscode-copilot** (GitHub) — VS Code integrated AI coding assistant

Each agent's capabilities are stored in `agents/<name>/capabilities/current.json`.

## Lead Types

Research these categories of changes:

1. **New capability** — A feature not yet tracked (e.g. a new tool, mode, or integration)
2. **Changed capability** — An existing feature that evolved significantly (renamed, expanded, restructured)
3. **Version / model release** — A new version, model update, or platform change
4. **Deprecation notice** — A feature being removed or replaced
5. **New agent** — A new AI coding agent worth adding to the tracker

## Confidence Levels

- **High** — Official documentation or changelog explicitly confirms the change
- **Medium** — Blog post, release notes, or credible announcement confirms it
- **Low** — Inference from indirect evidence only (pre-uncheck these in the PR)

## Research Mode

When assigned an issue labelled `research-leads`:

### Step 1: Understand current state

Read each `agents/<name>/capabilities/current.json` to understand what's already tracked. Note capability names, descriptions, and source URLs.

### Step 2: Research each agent

For each tracked agent, check:
- Official documentation sites for new or restructured pages
- Changelog / release notes for recent updates
- GitHub releases (for open-source agents)
- Product announcement blogs
- Any other authoritative sources you find

Look for capabilities, features, or integrations not yet in the data.

### Step 3: Create the PR

Open a PR with the actual proposed changes to `current.json` files in the diff.

**PR description format — this IS the triage interface:**

```markdown
## Research Leads — YYYY-MM-DD

Uncheck items to skip. Edit inline to correct a source URL.
Comment `@copilot revise` after making changes.

---

### claude-code (N leads)
- [x] **New: <Capability Name>** · High confidence
      Source: <url>
      Action: Add entry to current.json

- [x] **Update: <Capability Name>** · Medium confidence
      Source: <url>
      Action: Update description / add source

- [ ] **New: <Capability Name>** · Low confidence
      Source: <url>
      Action: Add entry (excluded by default — check to include)

### gemini-cli (N leads)
...

### No leads
- vscode-copilot: No new developments found
```

### Step 4: Validate

Before creating the PR, run:
```bash
python3 framework/scripts/validate_framework.py
```

Fix any errors before committing.

## Revise Mode

When someone comments `@copilot revise` on a research PR:

1. Re-read the PR description to see which items are checked/unchecked
2. Remove commits/changes for unchecked items
3. Apply any inline edits the reviewer made (corrected URLs, descriptions)
4. Re-run `python3 framework/scripts/validate_framework.py`
5. Push the updated commits

## Schema Reference

Each capability entry in `current.json` must have:

```json
{
  "category": "<one of: code-completion, code-generation, chat-assistance, code-explanation, code-refactoring, testing, debugging, documentation, command-line, multi-file-editing, context-awareness, language-support, ide-integration, api-integration, customization, security, performance, collaboration, model-selection, agent-orchestration, observability>",
  "name": "Capability Name",
  "description": "What this capability does, in 1-2 sentences",
  "available": true,
  "tier": "<free|pro|business|enterprise>",
  "maturityLevel": "<experimental|beta|stable|deprecated>",
  "status": "active",
  "sources": [
    {
      "url": "https://...",
      "description": "Brief source label",
      "verifiedDate": "YYYY-MM-DD",
      "sourceGranularity": "<dedicated|section|excerpt>",
      "excerpt": "Required 50-300 char verbatim quote when sourceGranularity is excerpt"
    }
  ]
}
```

## Adding a New Agent

If you discover a new AI coding agent worth tracking:

1. Create the directory: `agents/<agent-name>/capabilities/`
2. Create `current.json` with the agent info and initial capabilities
3. Create `agents/<agent-name>/docs-registry.json` listing authoritative doc sources
4. Run `python3 framework/scripts/validate_framework.py` to confirm schema compliance
5. Mark this lead as "New agent" in the PR description with Low confidence

## Important Rules

- NEVER fabricate capabilities. Every lead must cite a real, accessible source URL.
- Verify all source URLs return HTTP 200: `curl -Is URL | head -1`
- Pre-uncheck low-confidence leads so the reviewer must opt in.
- When adding a source with `sourceGranularity: "excerpt"`, include a verbatim 50-300 character quote from the page.
- Commit messages: `research: add <capability> to <agent>` or `research: update <capability> for <agent>`
```

**Step 2: Verify**

Run: `ls -la .github/skills/research-leads/SKILL.md`
Expected: file exists with non-zero size

**Step 3: Commit**

```bash
git add .github/skills/research-leads/SKILL.md
git commit -m "feat: add research-leads skill for Copilot coding agent"
```

---

### Task 3: Update weekly-verification.yml

**Files:**
- Modify: `.github/workflows/weekly-verification.yml:66-112`

**Step 1: Update the issue creation step**

Replace the existing "Open issue for broken sources" step (lines 66-111) with a version that:
1. Adds a machine-readable `<!-- BROKEN_SOURCES_JSON -->` block to the issue body
2. Assigns the issue to `copilot`
3. Includes `@copilot` mention in the body to trigger the agent

The updated step:

```yaml
      - name: Open issue for broken sources and assign to Copilot
        if: ${{ steps.check_broken.outputs.BROKEN_COUNT != '0' && steps.check_broken.outputs.BROKEN_COUNT != '' }}
        uses: actions/github-script@v7
        with:
          script: |
            const brokenCount = '${{ steps.check_broken.outputs.BROKEN_COUNT }}';
            const brokenUrls = `${{ steps.check_broken.outputs.BROKEN_URLS }}`;
            const today = new Date().toISOString().split('T')[0];

            // Build machine-readable JSON block for the skill to parse
            const brokenLines = brokenUrls.trim().split('\n')
              .filter(l => l.trim().startsWith('- '))
              .map(l => {
                const match = l.match(/^\s*-\s+(\S+):\s+\[([^\]]+)\]\s+(.+)$/);
                if (match) {
                  return JSON.stringify({agent: match[1], capability: match[2], url: match[3]});
                }
                return null;
              })
              .filter(Boolean);
            const jsonBlock = brokenLines.length > 0
              ? `<!-- BROKEN_SOURCES_JSON\n${brokenLines.join('\n')}\n-->\n\n`
              : '';

            // Check for existing open issue
            const issues = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'open',
              labels: 'broken-source'
            });

            const body = jsonBlock +
              `## ${brokenCount} broken source URL(s) detected on ${today}\n\n` +
              `The weekly source verification found unreachable URLs that could not be auto-fixed.\n\n` +
              `### Broken URLs\n\`\`\`\n${brokenUrls}\n\`\`\`\n\n` +
              `### Resolution\n` +
              `@copilot Please fix these broken sources using the \`source-maintenance\` skill.\n\n` +
              `_Generated by weekly-verification workflow_`;

            if (issues.data.length > 0) {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: issues.data[0].number,
                body: `Updated on ${today}:\n\n` + body
              });
              // Re-assign to copilot to retrigger
              await github.rest.issues.addAssignees({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: issues.data[0].number,
                assignees: ['copilot']
              });
            } else {
              await github.rest.issues.create({
                owner: context.repo.owner,
                repo: context.repo.repo,
                title: `[Automated] ${brokenCount} broken source URL(s) need fixes`,
                body: body,
                labels: ['broken-source', 'maintenance'],
                assignees: ['copilot']
              });
            }
```

**Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/weekly-verification.yml'))"`
Expected: no error (requires PyYAML; alternatively: `cat .github/workflows/weekly-verification.yml | python3 -c "import sys,json; __import__('yaml').safe_load(sys.stdin)" 2>&1 || echo "YAML syntax error"`)

If PyYAML not available, use: `gh workflow list` to check the workflow is parseable (only works if pushed).

**Step 3: Commit**

```bash
git add .github/workflows/weekly-verification.yml
git commit -m "feat: assign broken-source issues to Copilot coding agent"
```

---

### Task 4: Create daily-research.yml workflow

**Files:**
- Create: `.github/workflows/daily-research.yml`

**Step 1: Create the workflow file**

```yaml
name: Daily Research Leads

on:
  schedule:
    - cron: '0 7 * * *'  # Daily at 7am UTC
  workflow_dispatch:  # Allow manual trigger

permissions:
  contents: read
  issues: write

jobs:
  trigger-research:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Collect agent stats
        id: stats
        run: |
          python3 -c "
          import json
          from pathlib import Path
          from datetime import datetime

          lines = []
          for p in sorted(Path('agents').glob('*/capabilities/current.json')):
              agent = p.parent.parent.name
              data = json.load(open(p))
              count = len(data.get('capabilities', []))
              updated = data.get('agent', {}).get('lastUpdated', 'unknown')
              if updated != 'unknown':
                  try:
                      dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                      updated = dt.strftime('%Y-%m-%d')
                  except Exception:
                      pass
              lines.append(f'- {agent}: {count} capabilities (last updated: {updated})')

          result = chr(10).join(lines)

          # Use delimiter for multiline output
          import os
          with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
              f.write(f'AGENT_STATS<<EOF\n{result}\nEOF\n')
          "

      - name: Create research trigger issue
        uses: actions/github-script@v7
        with:
          script: |
            const today = new Date().toISOString().split('T')[0];
            const agentStats = `${{ steps.stats.outputs.AGENT_STATS }}`;

            // Check for existing open research issue from today
            const issues = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'open',
              labels: 'research-leads'
            });

            // Skip if there's already an open research issue
            if (issues.data.length > 0) {
              console.log('Open research issue already exists, skipping.');
              return;
            }

            const body = `## Daily Research Prompt — ${today}\n\n` +
              `@copilot Please research new developments for all tracked AI agents ` +
              `using the \`research-leads\` skill.\n\n` +
              `### Currently tracked agents\n${agentStats}\n\n` +
              `### What to look for\n` +
              `- New or changed capabilities\n` +
              `- Version or model releases\n` +
              `- Deprecation notices\n` +
              `- New AI coding agents worth tracking\n\n` +
              `_Generated by daily-research workflow_`;

            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `[Research] AI agent capability leads — ${today}`,
              body: body,
              labels: ['research-leads', 'maintenance'],
              assignees: ['copilot']
            });
```

**Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/daily-research.yml'))" 2>&1 || echo "install pyyaml or check manually"`

**Step 3: Commit**

```bash
git add .github/workflows/daily-research.yml
git commit -m "feat: add daily research workflow triggering Copilot coding agent"
```

---

### Task 5: Create the research-leads label via GitHub CLI

**Step 1: Create the label**

```bash
gh label create research-leads --description "Daily research for new AI agent capabilities" --color "0E8A16"
```

Expected: `Label "research-leads" was created`

If label already exists, this will error — that's fine.

---

### Task 6: Final validation and push

**Step 1: Run framework validation**

```bash
python3 framework/scripts/validate_framework.py
```

Expected: PASSED (existing warnings are OK; no new errors)

**Step 2: Check git log**

```bash
git log --oneline -5
```

Expected: 3-4 new commits from tasks 1-4

**Step 3: Push**

```bash
git push
```
