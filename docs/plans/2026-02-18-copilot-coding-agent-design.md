# Copilot Coding Agent Integration Design

**Date**: 2026-02-18
**Status**: Approved
**Branch**: copilot/map-agents-capabilities

---

## Problem

The weekly maintenance pipeline handles deterministic work well (HTTP reachability, redirect canonicalization) but cannot resolve hard 404s that require web research to find replacement URLs. This work was being done entirely manually. Similarly, there is no proactive research process to discover new capabilities, version releases, or depreciations for tracked agents.

---

## Solution

Integrate the GitHub Copilot Coding Agent as the intelligent layer above the existing deterministic scripts. The scripts remain as tools; the agent provides the judgment.

Two workflows run on separate schedules:

1. **Weekly broken-source fixer** — fixes what scripts can't (hard 404s)
2. **Daily research run** — proactively surfaces new capability leads

---

## Architecture

### Layer 1 — Deterministic (GitHub Actions, existing)

`weekly-verification.yml` continues to handle:
- HTTP reachability checks (pass 1)
- Content relevance scoring (pass 2)
- Redirect canonicalization (`--fix-redirects`)
- Committing verification results

This is fast, cheap, and fully predictable.

### Layer 2 — Intelligent (Copilot Coding Agent, new)

Triggered via GitHub Issues assigned to `@copilot`. The agent:
- Has web access (repository firewall disabled)
- Retains cross-session learning (Copilot Memory enabled)
- Uses skills for structured, reliable behaviour
- Produces PRs for human review — no unreviewed changes land on main

### The Handoff Contract

The Actions workflow creates a structured GitHub Issue. The issue body is the interface between the two layers. It contains machine-parseable data in an HTML comment block that the skill parses programmatically.

---

## Workflow A: Weekly Broken-Source Fixer

**Schedule**: Monday 06:00 UTC (unchanged)
**File**: `.github/workflows/weekly-verification.yml` (modified)

### Flow

```
cron → verify_sources.py → --fix-redirects → commit deterministic fixes
     ↓ (if hard 404s remain)
create/update issue with machine-readable broken URL data
assign issue to @copilot
     ↓
coding agent loads source-maintenance skill
runs --report to confirm current broken list
searches documentation sites for replacement URLs
verifies each candidate URL with HTTP HEAD
creates fixes.json, runs --apply-fixes
re-runs full verification
opens PR: copilot/fix-sources-YYYY-MM-DD
reports unresolvable URLs in PR description
```

### Issue body structure

```markdown
<!-- BROKEN_SOURCES_JSON
{"agent":"vscode-copilot","url":"https://...","capability":"Extensions"}
{"agent":"vscode-copilot","url":"https://...","capability":"Security Analysis"}
-->

## N broken source URL(s) detected — YYYY-MM-DD

[human-readable description as before]

### Resolution
@copilot Please fix these broken sources using the `source-maintenance` skill.
```

### Skill: `.github/skills/source-maintenance/SKILL.md`

Teaches the agent:
- How to run `verify_sources.py --report` and parse output
- The `fixes.json` format (simple: `{"old": "new"}` and extended: `{"old": {"url": "new", "sourceGranularity": "dedicated"}}`)
- Search strategy: check site top-level nav, look for flat→subdirectory patterns, try `reference/`, `guides/`, `how-tos/` prefixes
- How to verify a URL is live: `curl -Is URL | head -1` before committing to it
- How to run `--apply-fixes`, re-run full verification, and report residual failures
- What to include in the PR description (what was fixed, what couldn't be resolved, confidence notes)

---

## Workflow B: Daily Research Run

**Schedule**: Daily 07:00 UTC
**File**: `.github/workflows/daily-research.yml` (new)

### Flow

```
cron → collect current agent stats (capability counts, last verified dates)
     ↓
create trigger issue with agent context snapshot
assign issue to @copilot
     ↓
coding agent loads research-leads skill (research mode)
researches new developments for all tracked agents:
  - new or changed capabilities
  - version / model releases
  - deprecation notices
  - new agents worth tracking
opens PR: copilot/research-leads-YYYY-MM-DD
PR description = triage interface (checkbox list)
     ↓ (user reviews PR)
user unchecks items to skip, edits inline to correct URLs
user comments "@copilot revise" if changes needed
agent updates PR
user merges
```

### Trigger issue body structure

```markdown
## Daily Research Prompt — YYYY-MM-DD

@copilot Please research new developments for all tracked AI agents
using the `research-leads` skill.

### Currently tracked agents and capability counts
- claude-code: N capabilities (last verified: YYYY-MM-DD)
- copilot-cli: N capabilities (last verified: YYYY-MM-DD)
- gemini-cli: N capabilities (last verified: YYYY-MM-DD)
- vscode-copilot: N capabilities (last verified: YYYY-MM-DD)
```

### PR triage interface

The PR description is the triage UI. Leads arrive pre-checked:

```markdown
## Research Leads — YYYY-MM-DD

Uncheck items to skip. Edit inline to correct a source URL.
Comment `@copilot revise` after making changes.

---

### claude-code
- [x] **New capability: Vision** · High confidence
      Source: https://platform.claude.com/docs/en/build-with-claude/vision
      Action: Add `Vision` entry to current.json

- [x] **Update: Context Window** · Medium confidence
      Source: https://...

### vscode-copilot
- [x] **Update: Copilot Spaces now GA** · High confidence
      Source: https://...

- [ ] **New agent: GitHub Spark** · Low confidence — excluded by default
      Source: https://...
```

Low-confidence items arrive pre-unchecked. The diff shows exact proposed `current.json` changes.

### Skill: `.github/skills/research-leads/SKILL.md`

Two modes, selected by context:

**Research mode** (triggered by daily-research issue):
- Teaches the agent what agents are tracked and where their authoritative sources are
- Defines lead types: new capability, changed capability, version release, deprecation, new agent
- Confidence criteria: high = official docs confirm, medium = changelog/blog confirms, low = inference only
- PR description format: checkbox list, one entry per lead, low-confidence pre-unchecked
- Schema requirements for each change type

**Implement mode** (triggered by `@copilot revise` or `@copilot implement`):
- Teaches the agent to read checked items from the PR description
- Translates each checked lead into a valid `current.json` change
- Validates with `validate_framework.py` before committing
- Formats commit messages: `research: add Vision capability to claude-code`

---

## Configuration (completed)

| Item | Status |
|------|--------|
| Repository firewall | Disabled |
| Copilot Memory | Enabled |
| Copilot plan | Pro+ |
| Label `broken-source` | Exists |
| Label `maintenance` | Exists |
| Label `research-leads` | To create |

---

## Files Changed

| File | Change |
|------|--------|
| `.github/workflows/weekly-verification.yml` | Add `assignees: ['copilot']` + machine-readable issue body block |
| `.github/workflows/daily-research.yml` | New — daily trigger workflow |
| `.github/skills/source-maintenance/SKILL.md` | New — broken-source fix skill |
| `.github/skills/research-leads/SKILL.md` | New — research and implement skill |

No changes to `framework/scripts/` — the scripts remain as tools the agent calls.

---

## Constraints and Limitations

- Coding agent creates branches prefixed `copilot/` only
- Coding agent cannot work across multiple repositories
- One PR open at a time per session (two concurrent workflows use separate branch names so they don't conflict)
- `@copilot revise` costs one premium request per trigger
- Memory auto-expires after 28 days; memories are validated against current codebase before use

---

## Non-Goals

- Fully automated merging without human review (all changes require PR approval)
- Replacing `verify_sources.py` with agent logic (scripts stay as tools)
- Cross-repository capability tracking (single-repo constraint)
