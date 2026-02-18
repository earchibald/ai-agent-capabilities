# Design: agent-capabilities MCP Server

**Date:** 2026-02-18
**Status:** Draft
**Scope:** MCP server exposing agent capability data with minimal tools, maximum invocation accuracy, and embedded implementation guidance.

## Decisions

- **Naming:** `agent-capabilities` (no `-mcp` suffix — the protocol context is implicit)
- **Tool count:** 4 tools (lookup, compare, list, sources)
- **Implementation notes:** Embedded in responses (Option A) — zero extra tool calls
- **Fuzzy matching:** Alias table v1, embeddings v2 if needed
- **Read-only:** No write operations via MCP

## Design Principles

Optimization target: **minimum tools x maximum invocation accuracy x minimum token cost x minimum retry rate**.

Every design decision was evaluated against these axes. Adding a tool increases the decision space for agents. Removing a tool forces overloading. Four tools is the sweet spot for this data shape.

## 1. Tool Definitions

### `lookup_capability`

**Purpose:** "What can agent X do for Y?"

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent` | string | yes | Agent ID: `claude-code`, `copilot-cli`, `gemini-cli`, `vscode-copilot` |
| `capability` | string | yes | Capability name (fuzzy-matched) |

**Response:**

```json
{
  "agent": "claude-code",
  "capability": {
    "name": "MCP Support",
    "category": "api-integration",
    "available": true,
    "tier": "pro",
    "maturityLevel": "stable",
    "description": "Connect to external tools and services via Model Context Protocol servers",
    "implementationNotes": {
      "setup": "claude mcp add <server-name> -- <command>",
      "configFile": ".claude/settings.json",
      "startUrl": "https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/tutorials/set-up-mcp",
      "gotchas": ["Server process must be available at runtime"]
    },
    "sources": [{ "url": "...", "verifiedDate": "..." }]
  }
}
```

**Fuzzy matching:** If the query doesn't exactly match a capability name, the server resolves it. On ambiguity, returns top 3 matches with `matchConfidence` scores.

### `compare_capability`

**Purpose:** "How does capability Y differ across agents?"

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `capability` | string | yes | Capability name (fuzzy-matched) |
| `agents` | string[] | no | Filter to specific agents (default: all) |

**Response:**

```json
{
  "capability": "MCP Support",
  "comparison": [
    {
      "agent": "claude-code",
      "available": true,
      "tier": "pro",
      "maturityLevel": "stable",
      "implementationNotes": { "setup": "claude mcp add ...", "startUrl": "..." }
    },
    {
      "agent": "copilot-cli",
      "available": false
    },
    {
      "agent": "gemini-cli",
      "available": true,
      "tier": "free",
      "maturityLevel": "stable",
      "implementationNotes": { "setup": "Add to settings.json mcpServers", "startUrl": "..." }
    },
    {
      "agent": "vscode-copilot",
      "available": true,
      "tier": "pro",
      "maturityLevel": "stable",
      "implementationNotes": { "setup": "Configure in .vscode/mcp.json", "startUrl": "..." }
    }
  ]
}
```

Unavailable agents return only `agent` + `available: false` — no noise.

### `list_capabilities`

**Purpose:** "What capabilities does agent X have?" or "What's in category Y?"

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent` | string | no | Filter by agent |
| `category` | string | no | Filter by category |

At least one parameter required. Returns compact list: names, categories, tiers, availability. No `implementationNotes` (too much data at list scale). Agent calls `lookup_capability` for depth.

**Response:**

```json
{
  "agent": "claude-code",
  "capabilities": [
    { "name": "Agent Mode", "category": "agent-orchestration", "tier": "pro", "available": true },
    { "name": "MCP Support", "category": "api-integration", "tier": "pro", "available": true }
  ]
}
```

### `get_sources`

**Purpose:** "What are the authoritative sources for agent X / capability Y?"

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent` | string | no | Filter by agent |
| `capability` | string | no | Filter by capability |

Returns `sources` arrays with URLs, descriptions, dates, and status. Serves the citation use case.

## 2. Implementation Notes (Data Model)

Each capability gains an `implementationNotes` field:

```json
{
  "setup": "string — primary setup command or instruction",
  "configFile": "string — key configuration file path",
  "startUrl": "string — single best URL to fetch for deeper guidance",
  "gotchas": ["string[] — common pitfalls or prerequisites"]
}
```

All fields optional. `startUrl` is the most important: it creates a two-step flow:
1. `lookup_capability` gives the quick answer
2. If more depth needed, agent fetches `startUrl` — pre-selected by us, no guessing

## 3. Fuzzy Matching Strategy

### v1: Alias Table (zero dependencies)

Curated map of common synonyms to canonical capability names:

```json
{
  "mcp": "MCP Support",
  "model context protocol": "MCP Support",
  "tool integration": "MCP Support",
  "autocomplete": "Code Completion",
  "intellisense": "Code Completion",
  "inline suggestions": "Code Completion",
  "chat": "Chat Assistance",
  "agent": "Agent Mode",
  "agentic": "Agent Mode",
  "sub-agent": "Sub-agents",
  "subagent": "Sub-agents"
}
```

Resolution order:
1. Exact match (case-insensitive)
2. Alias table lookup
3. Substring match against name + description
4. If still ambiguous, return top 3 with confidence scores

### v2: Embeddings (optional enhancement)

Pre-compute embeddings at build time using `all-MiniLM-L6-v2` (~80MB model). Store as `framework/embeddings/capability-vectors.json` (~46KB for ~30 vectors x 384 dimensions). At runtime, embed query with ONNX runtime (~5MB), cosine similarity against pre-computed vectors. Sub-millisecond for 30 rows.

Upgrade path: the matching interface is a single function. Swapping alias-lookup for cosine-similarity is a one-function change.

## 4. Testing Framework

### Benchmark Suite

30-50 natural language prompts with expected tool calls:

```json
{
  "prompts": [
    {
      "input": "Does Claude Code support MCP?",
      "expectedTool": "lookup_capability",
      "expectedArgs": { "agent": "claude-code", "capability": "MCP Support" }
    },
    {
      "input": "Compare debugging features across all agents",
      "expectedTool": "compare_capability",
      "expectedArgs": { "capability": "Debugging" }
    },
    {
      "input": "What can Gemini CLI do?",
      "expectedTool": "list_capabilities",
      "expectedArgs": { "agent": "gemini-cli" }
    },
    {
      "input": "Where did you get the info about Copilot's agent mode?",
      "expectedTool": "get_sources",
      "expectedArgs": { "capability": "Agent Mode", "agent": "vscode-copilot" }
    }
  ]
}
```

### Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **Invocation accuracy** | % of prompts where agent selects the correct tool | >90% |
| **Argument accuracy** | % where agent passes correct parameters AND server resolves correctly | >85% |
| **Token efficiency** | Total tokens (tool descriptions + request/response) per scenario vs baseline | <50% of raw JSON baseline |
| **Retry rate** | % of prompts requiring a second tool call due to error or unexpected result | <10% |

### Test Scenarios (end-to-end workflows)

| Scenario | Expected Flow | Expected Calls |
|----------|--------------|----------------|
| Set up MCP in Claude Code | lookup → (optionally fetch startUrl) | 1-2 |
| Build cross-agent debugging workflow | compare debugging → lookup per agent | 2-5 |
| Cite all sources for Gemini CLI | get_sources | 1 |
| Find all free-tier capabilities | list_capabilities per agent / compare | 1-4 |
| Cross-agent feature parity check | compare for each capability | N |

### Test Harness

Script that:
1. Loads prompt suite
2. Sends each prompt to an LLM with MCP tool definitions in context
3. Records tool selection and arguments
4. Runs tool call against the server
5. Scores against expected results
6. Outputs report: invocation accuracy, argument accuracy, token usage, retry rate

Run against multiple LLMs (Claude, GPT, Gemini) to avoid single-model bias.

## 5. Implementation Scope

### Server (`mcp-server/`)

- Python or TypeScript MCP server (stdio transport)
- Reads capability data from `agents/*/capabilities/current.json` at startup
- Implements 4 tools
- Alias table for fuzzy matching
- No external dependencies beyond MCP SDK

### Data additions

- `implementationNotes` field added to each capability in `current.json` files
- `framework/data/aliases.json` — fuzzy match alias table
- `framework/tests/benchmark-prompts.json` — test suite

### Schema changes

Add to capability item properties in `capability-schema.json`:
- `implementationNotes` (object with optional setup, configFile, startUrl, gotchas fields)

### No new infrastructure

- No database
- No API keys
- No vector DB (v1)
- Server reads flat JSON files from disk
