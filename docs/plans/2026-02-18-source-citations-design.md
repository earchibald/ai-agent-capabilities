# Design: Source Citations + Capability Lifecycle

**Date:** 2026-02-18
**Status:** Approved
**Scope:** Add source URL citations to all facts, capability lifecycle tracking, and a generated sources index.

## Decisions

- **Option C — Both**: Inline sources per capability AND a generated sources index
- **Option C — Both dates**: Track upstream publication date AND our verification date
- Capabilities get the same lifecycle fields as sources (status, deprecation, superseding)

## Key Distinction: maturityLevel vs status

> **`maturityLevel`** = what the *vendor* says about the feature ("still in beta", "stable", "they removed it")
> **`status`** = what *our record* says about our documentation of it ("we've verified this is current", "we know the docs changed but haven't re-checked", "we've retired this entry")

They can disagree: a vendor-stable feature can have `status: "modified"` if their docs changed since we last looked. A vendor-deprecated feature needs *both* set to `"deprecated"` to fully close the loop.

## 1. Inline Source Format (per capability)

Each capability in `current.json` gets a `sources` array:

```json
{
  "category": "agent-orchestration",
  "name": "Agent Mode",
  "description": "...",
  "available": true,
  "tier": "pro",
  "maturityLevel": "stable",
  "status": "active",
  "deprecatedDate": null,
  "supersededBy": null,
  "sources": [
    {
      "url": "https://code.claude.com/docs/en/overview",
      "description": "Claude Code overview — agent mode documentation",
      "publishedDate": "2025-10-22",
      "verifiedDate": "2026-02-18",
      "status": "active",
      "supersededBy": null
    }
  ]
}
```

### Capability lifecycle fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | enum | no | `"active"` / `"deprecated"` / `"modified"` / `"unknown"` |
| `deprecatedDate` | date string | no | When this capability was deprecated (null if active) |
| `supersededBy` | string | no | Name of the capability that replaced this one |

### Source object fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string (URI) | yes | Authoritative source URL |
| `description` | string | yes | Brief label for the source |
| `publishedDate` | date string | no | When the upstream page was published/last updated (null if unknown) |
| `verifiedDate` | date string | yes | When we confirmed the fact from this source |
| `status` | enum | no | `"active"` / `"deprecated"` / `"modified"` / `"unknown"` |
| `supersededBy` | string (URI) | no | URL of the replacement source |

### Status values (applies to both capabilities and sources)

| Status | Meaning |
|--------|---------|
| `active` | Current and verified |
| `deprecated` | Removed or fully replaced; `supersededBy` points to replacement |
| `modified` | Still exists but content has changed significantly since `verifiedDate` |
| `unknown` | Was valid at verify time but unconfirmed since |

## 2. Generated Sources Index

`generate_comparison.py` produces `comparisons/sources-index.json`:

```json
{
  "generated_at": "2026-02-18T05:00:00+00:00",
  "sources": [
    {
      "url": "https://...",
      "description": "Claude Code overview",
      "publishedDate": "2026-01-15",
      "verifiedDate": "2026-02-18",
      "status": "active",
      "supersededBy": null,
      "citedBy": [
        { "agent": "claude-code", "capability": "Agent Mode" },
        { "agent": "claude-code", "capability": "Sub-agents" }
      ]
    }
  ]
}
```

**Sort order:** Active sources by `publishedDate` descending (newest first), then deprecated sources (stale entries don't crowd the top). Within same status+date, alphabetical by URL.

## 3. Implementation Scope

### Schema changes (`framework/schemas/capability-schema.json`)

Add to capability item properties:
- `status` (enum: active/deprecated/modified/unknown)
- `deprecatedDate` (string, date format)
- `supersededBy` (string)
- `sources` (array of source objects with url, description, publishedDate, verifiedDate, status, supersededBy)

### Capability file changes (all 4 `agents/*/capabilities/current.json`)

- Add `"status": "active"` to every capability
- Add `"sources": [...]` with real verified URLs to every capability
- No deprecated capabilities yet (all are currently active)

### Script changes

**`generate_comparison.py`:**
- Add `generate_sources_index()` function
- Write `comparisons/sources-index.json` as additional output

**`validate_framework.py`:**
- Add warning (not failure) for capabilities missing `sources`
- Validate `status` enum values if present
- Validate source object structure if present

### No new files or scripts — extends existing infrastructure only.
