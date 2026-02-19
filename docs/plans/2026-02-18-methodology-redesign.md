# Methodology Redesign: Doc-First Pipeline, Source Quality, Verification & Static API

**Status:** Approved
**Date:** 2026-02-18
**Supersedes:** Ad-hoc data collection, `2026-02-18-source-citations-design.md` (source schema retained, methodology replaced)

## Problem Statement

The current data collection methodology is backwards: it starts from capability names and hunts for URLs to justify them. This produced demonstrably wrong data (Gemini CLI lifecycle hooks marked `available: false` when they have the most comprehensive hooks system of all 4 agents) and low-quality citations (22 of 22 Gemini CLI capabilities citing the same repo homepage, 24 of 24 Claude Code capabilities citing the same overview page).

### Quantified damage

| Agent | Capabilities | Unique Source URLs | Worst offender |
|-------|-------------|-------------------|----------------|
| Claude Code | 24 | 4 | `/overview` cited 24 times |
| Gemini CLI | 22 | 4 | Repo homepage cited 22 times |
| Copilot CLI | 14 | 3 | Usage guide cited 10 times |
| VS Code Copilot | 24 | 37 | Reasonable specificity |

### Root causes

1. **Data pipeline inverted.** Capabilities were defined from LLM knowledge, then URLs were retroactively attached. The correct approach is to start from documentation, extract what it says, and reconcile against our data.
2. **Validation is syntactic, not semantic.** The validator checks that URLs are well-formed strings and required fields exist. It never fetches a URL, never checks content relevance, never detects 404s.
3. **Mass data entry without real verification.** Every `verifiedDate` across 84 capabilities is `2026-02-18` -- the date of bulk injection, not the date of individual verification.
4. **No freshness detection.** `verifiedDate` is stored but never checked for staleness. Data can drift from reality indefinitely without warning.

---

## Section 1: Doc-First Discovery Pipeline

### Per-agent documentation registry

Each agent gets a `docs-registry.json` that declares its authoritative documentation sources:

```json
{
  "agent": "gemini-cli",
  "docSources": [
    {
      "url": "https://geminicli.com/docs/",
      "type": "sitemap",
      "crawlStrategy": "follow-links"
    },
    {
      "url": "https://github.com/google-gemini/gemini-cli",
      "type": "readme",
      "crawlStrategy": "single-page"
    }
  ]
}
```

Located at `agents/{name}/docs-registry.json`.

### The crawl-extract-reconcile cycle

1. **Crawl:** `framework/scripts/crawl_docs.py` fetches each registered doc source, following links for `sitemap` types, fetching single pages for `readme`/`single-page` types.

2. **Extract:** For each page, an LLM extracts structured capability claims: "This page documents feature X with properties Y." Extractions are stored as intermediate artifacts at `agents/{name}/docs-cache/*.json` for auditability.

3. **Reconcile:** A reconciliation step diffs extracted capabilities against `current.json` and produces a report with three categories:
   - **Missing from our data:** Docs mention a feature we don't track (e.g., Gemini CLI hooks)
   - **Unverified in docs:** We claim a capability but no doc page supports it
   - **Contradictions:** Our data says X, docs say Y (e.g., we say unavailable, docs say available)

The reconciliation report is the key artifact. It prevents the Gemini CLI hooks mistake -- the pipeline would have flagged "docs at geminicli.com/docs/hooks/ describe a lifecycle hooks system, but current.json says `available: false`."

---

## Section 2: Source Quality Standards

### Source granularity tiers

Every source citation is classified by granularity and must meet minimum evidence requirements.

| Tier | Meaning | Rule |
|------|---------|------|
| `dedicated` | URL is about this specific capability | URL covers <=3 capabilities. Best quality. |
| `section` | URL has an anchor pointing to the relevant section | Must include `#fragment`. Page may cover many features but the anchor narrows it. |
| `excerpt` | URL is broad (homepage, overview) but an extracted quote proves the claim | Must include `excerpt` field with verbatim text from the page (50-300 chars). |

### Schema additions

New fields on the source object:

```json
{
  "url": "https://github.com/google-gemini/gemini-cli",
  "description": "...",
  "verifiedDate": "2026-02-18",
  "status": "active",
  "sourceGranularity": "excerpt",
  "excerpt": "Gemini CLI supports 11 lifecycle hooks triggered at specific agent loop points..."
}
```

### Validation rules

- Every source MUST have `sourceGranularity` set (enum: `dedicated`, `section`, `excerpt`)
- `section` sources MUST have a `#fragment` in the URL
- `excerpt` sources MUST have a non-empty `excerpt` field (50-300 characters)
- A capability with ONLY `excerpt`-tier sources gets a validation warning -- it means no dedicated documentation exists, which is itself a data quality signal
- `dedicated` sources need no additional fields -- URL specificity speaks for itself

### Practical impact

Claude Code's `/overview` page cited 24 times would require an excerpt per capability it's cited for. This forces the verifier to actually read the page and confirm the feature is mentioned. The Gemini CLI repo homepage cited 22 times would similarly require evidence. This raises the cost of lazy citations to where it's easier to just find the right URL.

---

## Section 3: Automated Verification Pipeline

A new script `framework/scripts/verify_sources.py` runs in three passes, each catching different failure modes.

### Pass 1: URL Reachability (no LLM, fast)

- HTTP HEAD request to every source URL
- Flags: 404s, 301 redirects (update URL), timeouts, SSL errors
- Updates `verifiedDate` on success, sets `status: "broken"` on failure
- Respects rate limits with per-domain throttling
- Output: `agents/{name}/verification/reachability.json`

### Pass 2: Content Relevance (lightweight, keyword-based)

- HTTP GET to fetch page content, convert HTML to text
- For `dedicated` sources: check that the capability name appears on the page
- For `section` sources: check that the `#fragment` anchor exists in the HTML
- For `excerpt` sources: check that the `excerpt` text still appears on the page (catches when docs are rewritten and the old text is gone)
- Output: `agents/{name}/verification/relevance.json`

### Pass 3: Semantic Verification (LLM-assisted, on demand)

- Sends page content + capability claim to an LLM with a structured prompt: "Does this page document a capability matching this description? Return yes/no with confidence and a suggested excerpt."
- Only runs for sources that passed Pass 1+2 but haven't been semantically verified in the last 30 days
- This is the pass that would have caught the Gemini CLI hooks error -- the LLM would read the README, find no mention of hooks, and flag the contradiction
- Output: `agents/{name}/verification/semantic.json`

### Staleness detection

Runs on every `validate_framework.py` invocation:

- Warning if any `verifiedDate` is >30 days old
- Error if any `verifiedDate` is >90 days old
- Summary report: "42 of 84 capabilities verified within 30 days"

### CI integration

- Passes 1 and 2 run on every push via GitHub Actions
- Pass 3 runs weekly on a schedule (or manually triggered)
- Verification results are committed back to the repo so they're versioned

---

## Section 4: Self-Discoverable Static API

Instead of building an MCP server, we publish a static API on GitHub Pages with a single discovery endpoint that any agent can navigate autonomously.

### Root discovery endpoint

`https://{user}.github.io/ai-agent-capabilities/api/v1/index.json`

```json
{
  "name": "AI Agent Capabilities Tracker",
  "version": "1.0.0",
  "description": "Structured capability data for AI coding agents, with verified source citations",
  "lastUpdated": "2026-02-18T08:34:27Z",
  "commit": "a4b293d",
  "dataQuality": {
    "totalCapabilities": 84,
    "verifiedWithin30d": 84,
    "brokenSources": 0,
    "averageSourceGranularity": "section"
  },
  "endpoints": {
    "agents": "/api/v1/agents.json",
    "capabilities": "/api/v1/capabilities.json",
    "comparisons": "/api/v1/comparisons/{capability-slug}.json",
    "sources": "/api/v1/sources.json",
    "quality": "/api/v1/quality.json",
    "schema": "/api/v1/schema.json"
  },
  "agents": [
    {"name": "Claude Code", "slug": "claude-code", "endpoint": "/api/v1/agents/claude-code.json"},
    {"name": "GitHub Copilot (VS Code)", "slug": "vscode-copilot", "endpoint": "/api/v1/agents/vscode-copilot.json"},
    {"name": "GitHub Copilot CLI", "slug": "copilot-cli", "endpoint": "/api/v1/agents/copilot-cli.json"},
    {"name": "Gemini CLI", "slug": "gemini-cli", "endpoint": "/api/v1/agents/gemini-cli.json"}
  ]
}
```

### Directory structure

```
dist/
  api/v1/
    index.json                        # Discovery endpoint
    agents.json                       # All agents summary
    agents/
      claude-code.json                # Full agent data
      vscode-copilot.json
      copilot-cli.json
      gemini-cli.json
    capabilities.json                 # All capabilities with slugs
    comparisons/
      agent-mode.json                 # Cross-agent comparison per capability
      lifecycle-hooks.json
      ...
    sources.json                      # Deduplicated source index
    quality.json                      # Data quality report
    quality/
      stale.json                      # Capabilities needing re-verification
      broken-sources.json             # Sources that failed reachability
    schema.json                       # Capability schema for consumers
  meta/
    last-updated.json                 # Build timestamp, commit SHA
    verification-report.json          # Latest verify_sources.py output
```

### Why this beats MCP

- Any agent with URL fetching can use it -- no MCP SDK, no protocol handshake
- Works with Claude Code's WebFetch, Copilot's fetch tools, Gemini CLI's web grounding
- The discovery endpoint IS the documentation -- an agent reads it and knows where everything is
- Versioned via URL path (`/v1/`), evolves without breaking consumers
- Data quality metrics are front and center, not hidden behind a tool

### What we lose vs MCP

Typed tool interfaces and parameter validation. An MCP tool says "give me a capability name and I'll fuzzy-match it." A static API requires the consumer to figure out the slug. Mitigated by including `capabilities.json` listing all slugs, which any agent can search client-side.

### The MCP path remains open

If demand materializes, a thin MCP wrapper can sit in front of these same static files. We don't build it until someone needs it.

### Build pipeline

`framework/scripts/generate_static_api.py` reads `agents/*/capabilities/current.json` + verification results, generates `dist/api/v1/`, GitHub Actions deploys to Pages on push.

---

## Section 5: Implementation Order

Five phases, each delivering standalone value. Each phase gates the next.

### Phase 1: Schema + Source Quality Enforcement

- Add `sourceGranularity` (enum: `dedicated`/`section`/`excerpt`) and `excerpt` (string, 50-300 chars) to the source object in `capability-schema.json`
- Update `validate_framework.py` with new quality rules (section needs `#fragment`, excerpt needs `excerpt` field, warn on excerpt-only capabilities)
- Existing sources that don't meet the new rules will fail validation -- this is intentional, forcing data fixes in Phase 2

### Phase 2: Doc-First Crawl + Data Fix

One agent at a time, starting with worst data quality:

1. **Gemini CLI** (4 unique URLs for 22 capabilities -- worst)
2. **Claude Code** (4 unique URLs for 24 capabilities)
3. **Copilot CLI** (3 unique URLs for 14 capabilities)
4. **VS Code Copilot** (37 unique URLs -- best, likely needs minimal fixes)

For each agent:
- Create `docs-registry.json`
- Build and run `crawl_docs.py`
- Reconcile against `current.json`
- Fix all sources to meet quality standards (specific URLs, anchors, or excerpts)
- All capabilities pass new validation

### Phase 3: Automated Verification Pipeline

- Build `verify_sources.py` with all three passes (reachability, relevance, semantic)
- Integrate staleness detection into `validate_framework.py`
- All existing sources get their first real verification pass
- `verifiedDate` values are updated to reflect actual verification, not bulk injection date

### Phase 4: Static API Generation

- Build `generate_static_api.py` producing `dist/api/v1/`
- Root `index.json` with discovery endpoint, data quality summary, agent listings
- Per-agent, per-capability, comparison, and quality endpoints
- Local serving for testing (`python -m http.server` on `dist/`)

### Phase 5: CI/CD + GitHub Pages

- GitHub Actions workflow: validate + generate + verify + deploy on push to main
- Weekly scheduled verification (all 3 passes)
- PR preview comments with diff summaries
- GitHub Pages deployment for the static API

---

## Decision Log

| Decision | Choice | Alternatives Considered |
|----------|--------|------------------------|
| Data pipeline direction | Doc-first (crawl docs, extract capabilities) | Capability-first (define capabilities, find URLs) -- caused the Gemini CLI hooks error |
| Monolithic source handling | Anchors + excerpts (belt and suspenders) | Accept generic URLs with quality flag; require section anchors only; excerpts only |
| Serving model | Self-discoverable static API on GitHub Pages | MCP server (local stdio); MCP server (remote HTTP); dual-mode local+remote |
| MCP server | Deferred (path remains open) | Build alongside static API |
| Verification automation scope | Full (reachability + relevance + semantic) | URL reachability only; keyword matching only; LLM-only |
| Implementation order | Gemini CLI first (worst data) | VS Code first (best data, easiest); all agents simultaneously |
