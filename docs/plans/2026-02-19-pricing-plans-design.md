# Pricing Plans Design

**Date:** 2026-02-19

## Goal

Add structured cost/pricing data for each tracked agent. Cover three cost models:

- **Subscription (allowance)** — fixed recurring fee, includes a usage quota; optional overage billing
- **Pay-per-token** — no subscription, billed per token by the provider directly
- **Free** — no cost, may have rate limits

## File Structure

Each agent gets a separate pricing file, consistent with the existing pattern of `capabilities/`, `releases/`, and `verification/`:

```
agents/
  claude-code/pricing/current.json
  copilot-cli/pricing/current.json
  gemini-cli/pricing/current.json
  vscode-copilot/pricing/current.json
framework/schemas/pricing-schema.json
```

Top-level shape of each file:

```json
{
  "agent": "claude-code",
  "lastUpdated": "2026-02-19",
  "plans": [ ... ],
  "sources": [ ... ]
}
```

## Plan Schema

Each entry in `plans`:

| Field | Type | Notes |
|---|---|---|
| `id` | string | URL-safe slug, e.g. `pro`, `aws-bedrock` |
| `name` | string | Human-readable, e.g. `Claude Pro` |
| `type` | `subscription` \| `pay-per-token` \| `free` | Cost model |
| `billedBy` | `anthropic` \| `github` \| `google` \| `aws` \| `gcp` \| `azure` \| `openai` \| `varies` | Who charges the card |
| `price` | object \| null | null for pay-per-token; `{amount, currency, period, annualOption?}` |
| `allowance` | object \| null | Present for subscription/free; `{unit, quotas[]}` |
| `overage` | object \| null | `{available, model, unit, costPerUnit, currency, note?}` |
| `tokenPricing` | array \| null | Present for pay-per-token; per-model input/output costs |
| `note` | string \| null | Caveats, unconfirmed details, etc. |

**`allowance.unit`:** `tokens` | `premium-requests` | `requests`

**`allowance.quotas[]`:** `{period, amount, note?}` where `period` is `4h-rolling` | `day` | `week` | `month` and `amount` is a number or `null` (undocumented).

**`overage.model`:** `pay-as-you-go` | `blocked` | `configurable-budget`

**`tokenPricing[]`:** `{model, inputPerMTokens, outputPerMTokens, currency, contextTiers?}`

## Per-Agent Plan Inventory

### Claude Code — 7 plans

| id | name | type | billedBy | price |
|---|---|---|---|---|
| `pro` | Claude Pro | subscription | anthropic | $20/mo or $200/yr |
| `max-5x` | Claude Max (5×) | subscription | anthropic | $100/mo |
| `max-20x` | Claude Max (20×) | subscription | anthropic | $200/mo |
| `anthropic-api` | Anthropic API Key | pay-per-token | anthropic | per token |
| `aws-bedrock` | Amazon Bedrock | pay-per-token | aws | per token via AWS |
| `gcp-vertex` | Google Vertex AI | pay-per-token | gcp | per token via GCP |
| `azure-foundry` | Azure AI Foundry | pay-per-token | azure | per token via Azure |

All three subscriptions have 4h-rolling + weekly quotas (amount `null` — Anthropic does not publish exact numbers). Quota is relative: Max 5× = 5× Pro, Max 20× = 20× Pro. Overage model is `pay-as-you-go` at standard API rates.

### Copilot CLI — 5 plans (no BYO API key)

| id | name | type | billedBy | price | allowance | overage |
|---|---|---|---|---|---|---|
| `free` | Copilot Free | free | github | $0 | 50 req/mo | blocked |
| `pro` | Copilot Pro | subscription | github | $10/mo or $100/yr | 300 req/mo | $0.04/req |
| `pro-plus` | Copilot Pro+ | subscription | github | $39/mo or $390/yr | 1,500 req/mo | $0.04/req |
| `business` | Copilot Business | subscription | github | $19/seat/mo | 300 req/mo | configurable-budget |
| `enterprise` | Copilot Enterprise | subscription | github | $39/seat/mo | ~1,000 req/mo | configurable-budget |

Enterprise allowance (~1,000) is 3.33× Business (300); not exact. Business/Enterprise overage requires org admin to enable and set a spending budget (default $0 = blocked).

### VS Code Copilot — 8 plans (same 5 subscription plans + 3 BYO API key)

Same five subscription plans as Copilot CLI, plus:

| id | name | type | billedBy |
|---|---|---|---|
| `byo-anthropic` | Anthropic API Key | pay-per-token | anthropic |
| `byo-openai` | OpenAI API Key | pay-per-token | openai |
| `byo-openai-compatible` | OpenAI-compatible API | pay-per-token | varies |

BYO plans: user pays provider directly. No GitHub billing. Accessed via VS Code language model picker → "Add Models".

### Gemini CLI — 6 plans

| id | name | type | billedBy | allowance |
|---|---|---|---|---|
| `google-oauth` | Google Account (OAuth) | free | google | 1,000 req/day, 60 req/min |
| `gemini-api-free` | Gemini API Key (free tier) | free | google | 250 req/day, 10 req/min; Flash models only |
| `code-assist-standard` | Gemini Code Assist Standard | subscription | google | 1,500 req/day, 120 req/min |
| `code-assist-enterprise` | Gemini Code Assist Enterprise | subscription | google | 2,000 req/day, 120 req/min |
| `gemini-api-paid` | Gemini API Key (paid) | pay-per-token | google | per token at Gemini API rates |
| `vertex-ai` | Vertex AI | pay-per-token | gcp | 90-day Express Mode trial, then billed via GCP |

Note on `google-oauth`: whether quota shares the same pool as Google AI Studio is unconfirmed.

## API Surface Changes

New endpoints in `generate_static_api.py`:

- `/api/v1/agents/{slug}/pricing.json` — pricing file for one agent (served directly from source)
- `/api/v1/pricing.json` — all four agents' pricing combined, keyed by slug

`index.json` `endpoints` map gains a `pricing` key: `/api/v1/pricing.json`.

`validate_framework.py` gains a new check: warn if any agent is missing a `pricing/current.json` or if `lastUpdated` is stale (>30 days), consistent with existing capabilities staleness check.

## Sources

Each pricing file carries a `sources` array at the file level (not per-plan) with the same shape as capability sources: `{url, description, verifiedDate, sourceGranularity, excerpt?}`.

Key sources:
- Claude Code: `https://claude.com/pricing`, `https://claude.com/claude-code`
- Copilot: `https://docs.github.com/en/copilot/concepts/billing/individual-plans`, `https://docs.github.com/en/copilot/managing-copilot/monitoring-usage-and-entitlements/about-premium-requests`
- Gemini CLI: `https://geminicli.com/docs/quota-and-pricing/`
