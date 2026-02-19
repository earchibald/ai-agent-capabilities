# AI Agent Capabilities Tracker — Project Instructions

## Mission

This repository is a structured, source-verified data product that tracks and compares the capabilities of AI coding agents. The core deliverable is machine-readable JSON capability files for each tracked agent, with automated comparison generation and source citation.

**Tracked agents:** Claude Code (Anthropic), GitHub Copilot VS Code (GitHub/Microsoft), GitHub Copilot CLI (GitHub/Microsoft), Gemini CLI (Google).

## Temporary Files Policy

**ALWAYS** place temporary files in a `tmp/` folder within the current workspace directory. **NEVER** use global `/tmp`, `$TMPDIR`, or any path outside the repository root. This ensures all artifacts are visible, reproducible, and don't require human intervention to locate.

```
# Correct
./tmp/output.json
./tmp/scratch.py

# Wrong — never do this
/tmp/output.json
/var/tmp/scratch.py
```

The `tmp/` directory is gitignored. Create it if it doesn't exist.

## Technical Architecture

### Data layer
- `agents/{agent-id}/capabilities/current.json` — Structured capability data per agent. This IS the product.
- `framework/schemas/capability-schema.json` — JSON Schema defining valid capability structures.
- `agents/{agent-id}/releases/` — Release note history fetched from upstream.

### Generated outputs
- `comparisons/README.md` — Human-readable comparison tables (generated, do not hand-edit).
- `comparisons/comparison-matrix.json` — Structured comparison data (generated).
- `comparisons/capability-summary.json` — Statistics (generated).
- `comparisons/sources-index.json` — Deduplicated, time-sorted source citations (generated).

### Scripts
- `framework/scripts/generate_comparison.py` — Reads all capability JSONs, generates comparison outputs.
- `framework/scripts/fetch_releases.py` — Fetches release notes from GitHub API and changelog URLs.
- `framework/scripts/validate_framework.py` — Validates capability files against the JSON schema.

### CI/CD
- `.github/workflows/update-capabilities.yml` — Daily release fetch + comparison regeneration.

## Practical Approaches

### Data accuracy is paramount
Every capability fact must be verified against an authoritative source URL. The `sources` array on each capability entry must contain at least one source with `url`, `description`, and `verifiedDate`. Do not add capabilities you cannot cite.

### Standardize names across agents
When agents share a capability, use the SAME `name` value so comparison tables align correctly. "Chat Assistance" not "Interactive Chat" vs "Copilot Chat" vs "Terminal Chat".

### Schema-first development
Change the JSON schema before changing capability files. Validate after every change with `python3 framework/scripts/validate_framework.py`.

### Regenerate after every data change
After modifying any `current.json`, run `python3 framework/scripts/generate_comparison.py` and verify the output.

### Lifecycle tracking
Both capabilities and sources carry `status` (active/deprecated/modified/unknown) and optional `supersededBy` pointers. See `docs/plans/2026-02-18-source-citations-design.md` for the full specification.

### maturityLevel vs status
- `maturityLevel` = what the **vendor** says about the feature (experimental, beta, stable, deprecated)
- `status` = what **our record** says about our documentation (active, deprecated, modified, unknown)

These track different things and can disagree.

## Mode of Operation

1. **Research first** — Verify facts against live documentation before writing capability data.
2. **Schema first** — Update schemas before data files.
3. **Validate always** — Run validation after every change.
4. **Regenerate always** — Run comparison generation after every data change.
5. **Cite everything** — No unsourced facts in capability files.
6. **Minimize documentation** — The data files are self-documenting via schemas. Keep README under 60 lines. Avoid redundant docs.
7. **No over-engineering** — If it doesn't directly serve the comparison or citation use cases, don't build it.
