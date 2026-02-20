# Pricing Plans Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured pricing data (`agents/{slug}/pricing/current.json`) for all four tracked agents, expose it via two new API endpoints, and add a validator check.

**Architecture:** Separate pricing files (not mixed into capabilities) follow the existing pattern of `capabilities/`, `releases/`, `verification/`. The static API generator reads pricing files and serves them at `/api/v1/pricing.json` (combined) and `/api/v1/agents/{slug}/pricing.json` (per-agent). The validator gains a new step warning if pricing files are missing or stale.

**Tech Stack:** Python 3, JSON, no new dependencies. Working directory is `.worktrees/feature-pricing-plans/` throughout.

**Design doc:** `docs/plans/2026-02-19-pricing-plans-design.md`

---

### Task 1: Add pricing validation to validate_framework.py

Run validation first (TDD: the new check will produce warnings until pricing files exist).

**Files:**
- Modify: `framework/scripts/validate_framework.py`

**Step 1: Read the validator to understand the pattern**

Open `framework/scripts/validate_framework.py`. Check steps 1–7. The pattern is:
- A numbered step heading printed with `print(f"\n{N}. Checking ...")`
- A loop over agents, checking files, appending to `warnings` list
- A `pass_count` / `fail_count` for hard failures, `warnings` for soft ones

**Step 2: Add the pricing check after the existing step 7 (semantic gap detection)**

Find the end of step 7 in `validate_framework.py`, then add step 8. Insert this code before the "8. Warnings" section (the final summary block that prints `\n8. Warnings`):

```python
    # 8. Check pricing files
    print("\n8. Checking pricing files...")
    today = date.today()
    for agent_slug in ['claude-code', 'copilot-cli', 'gemini-cli', 'vscode-copilot']:
        pricing_file = AGENTS_DIR / agent_slug / "pricing" / "current.json"
        if not pricing_file.exists():
            warnings.append(f"~ {agent_slug}: Missing pricing/current.json")
            continue
        try:
            with open(pricing_file) as f:
                pricing = json.load(f)
            last = pricing.get('lastUpdated', '')
            if last:
                age = (today - date.fromisoformat(last)).days
                if age > 30:
                    warnings.append(f"~ {agent_slug}: pricing/current.json is {age} days old (lastUpdated: {last})")
                else:
                    print(f"  + {agent_slug}/pricing/current.json ({age}d old)")
            else:
                warnings.append(f"~ {agent_slug}: pricing/current.json missing lastUpdated field")
        except json.JSONDecodeError as e:
            warnings.append(f"~ {agent_slug}: pricing/current.json is invalid JSON: {e}")
```

Also renumber the final "Warnings" section heading from `8.` to `9.`:
- Change `print("\n8. Warnings...")` → `print("\n9. Warnings...")`

**Step 3: Run validation to verify the new warnings appear**

```bash
python3 framework/scripts/validate_framework.py
```

Expected output includes four new warnings:
```
8. Checking pricing files...
...
9. Warnings (66)...
  ~ claude-code: Missing pricing/current.json
  ~ copilot-cli: Missing pricing/current.json
  ~ gemini-cli: Missing pricing/current.json
  ~ vscode-copilot: Missing pricing/current.json
```
Validation still says `PASSED` (these are warnings, not failures).

**Step 4: Commit**

```bash
git add framework/scripts/validate_framework.py
git commit -m "feat: add pricing file validation step to validate_framework"
```

---

### Task 2: Create pricing schema

**Files:**
- Create: `framework/schemas/pricing-schema.json`

**Step 1: Create the file**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AI Agent Pricing Schema",
  "description": "Schema for documenting AI agent pricing plans and cost models",
  "type": "object",
  "required": ["agent", "lastUpdated", "plans", "sources"],
  "properties": {
    "agent": {
      "type": "string",
      "description": "Agent slug matching the directory name"
    },
    "lastUpdated": {
      "type": "string",
      "format": "date",
      "description": "Date this pricing data was last verified"
    },
    "plans": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "type", "billedBy"],
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "type": {
            "type": "string",
            "enum": ["subscription", "pay-per-token", "free"]
          },
          "billedBy": {
            "type": "string",
            "enum": ["anthropic", "github", "google", "aws", "gcp", "azure", "openai", "varies"]
          },
          "price": {
            "oneOf": [
              { "type": "null" },
              {
                "type": "object",
                "required": ["amount", "currency", "period"],
                "properties": {
                  "amount": { "type": "number" },
                  "currency": { "type": "string" },
                  "period": {
                    "type": "string",
                    "enum": ["month", "year", "seat/month"]
                  },
                  "annualOption": {
                    "type": "object",
                    "properties": {
                      "amount": { "type": "number" },
                      "currency": { "type": "string" },
                      "period": { "type": "string" }
                    }
                  }
                }
              }
            ]
          },
          "allowance": {
            "oneOf": [
              { "type": "null" },
              {
                "type": "object",
                "required": ["unit", "quotas"],
                "properties": {
                  "unit": {
                    "type": "string",
                    "enum": ["tokens", "premium-requests", "requests"]
                  },
                  "quotas": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "required": ["period"],
                      "properties": {
                        "period": {
                          "type": "string",
                          "enum": ["4h-rolling", "day", "week", "month"]
                        },
                        "amount": { "type": ["number", "null"] },
                        "note": { "type": "string" }
                      }
                    }
                  }
                }
              }
            ]
          },
          "overage": {
            "oneOf": [
              { "type": "null" },
              {
                "type": "object",
                "required": ["available", "model"],
                "properties": {
                  "available": { "type": "boolean" },
                  "model": {
                    "type": "string",
                    "enum": ["pay-as-you-go", "blocked", "configurable-budget"]
                  },
                  "unit": { "type": "string" },
                  "costPerUnit": { "type": ["number", "null"] },
                  "currency": { "type": "string" },
                  "note": { "type": "string" }
                }
              }
            ]
          },
          "tokenPricing": {
            "oneOf": [
              { "type": "null" },
              {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["model", "inputPerMTokens", "outputPerMTokens", "currency"],
                  "properties": {
                    "model": { "type": "string" },
                    "inputPerMTokens": { "type": "number" },
                    "outputPerMTokens": { "type": "number" },
                    "currency": { "type": "string" },
                    "contextTiers": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "upToTokens": { "type": ["number", "null"] },
                          "inputPerMTokens": { "type": "number" },
                          "outputPerMTokens": { "type": "number" }
                        }
                      }
                    }
                  }
                }
              }
            ]
          },
          "note": { "type": ["string", "null"] }
        }
      }
    },
    "sources": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["url", "description", "verifiedDate", "sourceGranularity"],
        "properties": {
          "url": { "type": "string", "format": "uri" },
          "description": { "type": "string" },
          "verifiedDate": { "type": "string", "format": "date" },
          "sourceGranularity": {
            "type": "string",
            "enum": ["dedicated", "section", "excerpt"]
          },
          "excerpt": { "type": "string" }
        }
      }
    }
  }
}
```

**Step 2: Commit**

```bash
git add framework/schemas/pricing-schema.json
git commit -m "feat: add pricing schema"
```

---

### Task 3: Create claude-code pricing file

**Files:**
- Create: `agents/claude-code/pricing/current.json`

**Step 1: Create directory and file**

```bash
mkdir -p agents/claude-code/pricing
```

Content of `agents/claude-code/pricing/current.json`:

```json
{
  "agent": "claude-code",
  "lastUpdated": "2026-02-19",
  "plans": [
    {
      "id": "pro",
      "name": "Claude Pro",
      "type": "subscription",
      "billedBy": "anthropic",
      "price": {
        "amount": 20,
        "currency": "USD",
        "period": "month",
        "annualOption": { "amount": 200, "currency": "USD", "period": "year" }
      },
      "allowance": {
        "unit": "tokens",
        "quotas": [
          { "period": "4h-rolling", "amount": null, "note": "Not publicly documented; varies by model and message length" },
          { "period": "week", "amount": null, "note": "Not publicly documented; varies by model and message length" }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "tokens",
        "costPerUnit": null,
        "currency": "USD",
        "note": "Usage above quota billed at standard Anthropic API rates per model"
      },
      "tokenPricing": null,
      "note": null
    },
    {
      "id": "max-5x",
      "name": "Claude Max (5x)",
      "type": "subscription",
      "billedBy": "anthropic",
      "price": {
        "amount": 100,
        "currency": "USD",
        "period": "month"
      },
      "allowance": {
        "unit": "tokens",
        "quotas": [
          { "period": "4h-rolling", "amount": null, "note": "5x Pro quota; not publicly documented" },
          { "period": "week", "amount": null, "note": "5x Pro quota; not publicly documented" }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "tokens",
        "costPerUnit": null,
        "currency": "USD",
        "note": "Usage above quota billed at standard Anthropic API rates per model"
      },
      "tokenPricing": null,
      "note": "5x the usage quota of Claude Pro"
    },
    {
      "id": "max-20x",
      "name": "Claude Max (20x)",
      "type": "subscription",
      "billedBy": "anthropic",
      "price": {
        "amount": 200,
        "currency": "USD",
        "period": "month"
      },
      "allowance": {
        "unit": "tokens",
        "quotas": [
          { "period": "4h-rolling", "amount": null, "note": "20x Pro quota; not publicly documented" },
          { "period": "week", "amount": null, "note": "20x Pro quota; not publicly documented" }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "tokens",
        "costPerUnit": null,
        "currency": "USD",
        "note": "Usage above quota billed at standard Anthropic API rates per model"
      },
      "tokenPricing": null,
      "note": "20x the usage quota of Claude Pro"
    },
    {
      "id": "anthropic-api",
      "name": "Anthropic API Key",
      "type": "pay-per-token",
      "billedBy": "anthropic",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        { "model": "claude-opus-4-5", "inputPerMTokens": 15.00, "outputPerMTokens": 75.00, "currency": "USD" },
        { "model": "claude-sonnet-4-5", "inputPerMTokens": 3.00, "outputPerMTokens": 15.00, "currency": "USD" },
        { "model": "claude-haiku-3-5", "inputPerMTokens": 0.80, "outputPerMTokens": 4.00, "currency": "USD" }
      ],
      "note": "Requires ANTHROPIC_API_KEY. Billed via Anthropic console. Supports all Claude models."
    },
    {
      "id": "aws-bedrock",
      "name": "Amazon Bedrock",
      "type": "pay-per-token",
      "billedBy": "aws",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        { "model": "claude-opus-4-5", "inputPerMTokens": 15.00, "outputPerMTokens": 75.00, "currency": "USD" },
        { "model": "claude-sonnet-4-5", "inputPerMTokens": 3.00, "outputPerMTokens": 15.00, "currency": "USD" },
        { "model": "claude-haiku-3-5", "inputPerMTokens": 0.80, "outputPerMTokens": 4.00, "currency": "USD" }
      ],
      "note": "Requires AWS credentials and Bedrock model access. Billed via AWS account."
    },
    {
      "id": "gcp-vertex",
      "name": "Google Vertex AI",
      "type": "pay-per-token",
      "billedBy": "gcp",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        { "model": "claude-opus-4-5", "inputPerMTokens": 15.00, "outputPerMTokens": 75.00, "currency": "USD" },
        { "model": "claude-sonnet-4-5", "inputPerMTokens": 3.00, "outputPerMTokens": 15.00, "currency": "USD" }
      ],
      "note": "Requires Google Cloud project with Vertex AI API enabled. Billed via GCP account."
    },
    {
      "id": "azure-foundry",
      "name": "Azure AI Foundry",
      "type": "pay-per-token",
      "billedBy": "azure",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        { "model": "claude-opus-4-5", "inputPerMTokens": 15.00, "outputPerMTokens": 75.00, "currency": "USD" },
        { "model": "claude-sonnet-4-5", "inputPerMTokens": 3.00, "outputPerMTokens": 15.00, "currency": "USD" }
      ],
      "note": "Requires Azure subscription with Claude models deployed via Azure AI Foundry. Billed via Azure account."
    }
  ],
  "sources": [
    {
      "url": "https://claude.com/pricing",
      "description": "Claude pricing page - subscription plan prices and descriptions",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://claude.com/claude-code",
      "description": "Claude Code product page - plan tiers and usage limits overview",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://support.claude.com/en/articles/11647753-understanding-usage-and-length-limits",
      "description": "Claude usage limits support article - quota structure per plan",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://platform.claude.com/docs/en/about-claude/models/overview",
      "description": "Anthropic model overview with API pricing per model",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    }
  ]
}
```

**Step 2: Run validation to confirm warning clears for claude-code**

```bash
python3 framework/scripts/validate_framework.py 2>&1 | grep -A2 "8\. Checking"
```

Expected: `+ claude-code/pricing/current.json (0d old)`, three remaining warnings for other agents.

**Step 3: Commit**

```bash
git add agents/claude-code/pricing/current.json
git commit -m "feat: add claude-code pricing plans"
```

---

### Task 4: Create copilot-cli pricing file

**Files:**
- Create: `agents/copilot-cli/pricing/current.json`

**Step 1: Create directory and file**

```bash
mkdir -p agents/copilot-cli/pricing
```

Content of `agents/copilot-cli/pricing/current.json`:

```json
{
  "agent": "copilot-cli",
  "lastUpdated": "2026-02-19",
  "plans": [
    {
      "id": "free",
      "name": "Copilot Free",
      "type": "free",
      "billedBy": "github",
      "price": {
        "amount": 0,
        "currency": "USD",
        "period": "month"
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 50 }
        ]
      },
      "overage": {
        "available": false,
        "model": "blocked",
        "note": "Free plan cannot purchase additional premium requests"
      },
      "tokenPricing": null,
      "note": "Not available to users who already have a paid Copilot seat through an organization"
    },
    {
      "id": "pro",
      "name": "Copilot Pro",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 10,
        "currency": "USD",
        "period": "month",
        "annualOption": { "amount": 100, "currency": "USD", "period": "year" }
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 300 }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "premium-requests",
        "costPerUnit": 0.04,
        "currency": "USD",
        "note": "Overage requires setting a spending budget in account settings; default budget is $0 (requests blocked)"
      },
      "tokenPricing": null,
      "note": "Free for verified students, teachers, and maintainers of popular open-source projects"
    },
    {
      "id": "pro-plus",
      "name": "Copilot Pro+",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 39,
        "currency": "USD",
        "period": "month",
        "annualOption": { "amount": 390, "currency": "USD", "period": "year" }
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 1500 }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "premium-requests",
        "costPerUnit": 0.04,
        "currency": "USD",
        "note": "Overage requires setting a spending budget in account settings; default budget is $0 (requests blocked)"
      },
      "tokenPricing": null,
      "note": null
    },
    {
      "id": "business",
      "name": "Copilot Business",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 19,
        "currency": "USD",
        "period": "seat/month"
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 300 }
        ]
      },
      "overage": {
        "available": true,
        "model": "configurable-budget",
        "unit": "premium-requests",
        "costPerUnit": null,
        "note": "Organization admin must enable 'Premium request paid usage' policy and set a spending budget"
      },
      "tokenPricing": null,
      "note": "Includes user management, IP indemnity, and usage metrics"
    },
    {
      "id": "enterprise",
      "name": "Copilot Enterprise",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 39,
        "currency": "USD",
        "period": "seat/month"
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 1000, "note": "Approximately 3.33x Business (300); exact number not published" }
        ]
      },
      "overage": {
        "available": true,
        "model": "configurable-budget",
        "unit": "premium-requests",
        "costPerUnit": null,
        "note": "Organization admin must enable 'Premium request paid usage' policy and set a spending budget"
      },
      "tokenPricing": null,
      "note": "Includes codebase indexing, custom fine-tuned models, and all available AI models"
    }
  ],
  "sources": [
    {
      "url": "https://docs.github.com/en/copilot/concepts/billing/individual-plans",
      "description": "GitHub Copilot individual plans - Free, Pro, Pro+ pricing and allowances",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://docs.github.com/en/copilot/managing-copilot/monitoring-usage-and-entitlements/about-premium-requests",
      "description": "GitHub Copilot premium requests - allowances per plan and overage billing",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://github.com/features/copilot",
      "description": "GitHub Copilot product page - plan comparison including Business and Enterprise",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    }
  ]
}
```

**Step 2: Run validation to confirm warning clears for copilot-cli**

```bash
python3 framework/scripts/validate_framework.py 2>&1 | grep -A4 "8\. Checking"
```

**Step 3: Commit**

```bash
git add agents/copilot-cli/pricing/current.json
git commit -m "feat: add copilot-cli pricing plans"
```

---

### Task 5: Create gemini-cli pricing file

**Files:**
- Create: `agents/gemini-cli/pricing/current.json`

**Step 1: Create directory and file**

```bash
mkdir -p agents/gemini-cli/pricing
```

Content of `agents/gemini-cli/pricing/current.json`:

```json
{
  "agent": "gemini-cli",
  "lastUpdated": "2026-02-19",
  "plans": [
    {
      "id": "google-oauth",
      "name": "Google Account (OAuth)",
      "type": "free",
      "billedBy": "google",
      "price": {
        "amount": 0,
        "currency": "USD",
        "period": "month"
      },
      "allowance": {
        "unit": "requests",
        "quotas": [
          { "period": "day", "amount": 1000 },
          { "period": "4h-rolling", "amount": null, "note": "60 requests/minute rate limit" }
        ]
      },
      "overage": {
        "available": false,
        "model": "blocked",
        "note": "No overage on OAuth free tier; upgrade to API key paid or Code Assist subscription"
      },
      "tokenPricing": null,
      "note": "Authenticated via personal Google account. Whether quota shares the same pool as Google AI Studio is unconfirmed."
    },
    {
      "id": "gemini-api-free",
      "name": "Gemini API Key (free tier)",
      "type": "free",
      "billedBy": "google",
      "price": {
        "amount": 0,
        "currency": "USD",
        "period": "month"
      },
      "allowance": {
        "unit": "requests",
        "quotas": [
          { "period": "day", "amount": 250 },
          { "period": "4h-rolling", "amount": null, "note": "10 requests/minute rate limit" }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "tokens",
        "costPerUnit": null,
        "note": "Upgrade API key to paid billing to access per-token pricing above free limits"
      },
      "tokenPricing": null,
      "note": "Free tier restricted to Flash models only. Lower limits than OAuth free tier."
    },
    {
      "id": "code-assist-standard",
      "name": "Gemini Code Assist Standard",
      "type": "subscription",
      "billedBy": "google",
      "price": null,
      "allowance": {
        "unit": "requests",
        "quotas": [
          { "period": "day", "amount": 1500 },
          { "period": "4h-rolling", "amount": null, "note": "120 requests/minute rate limit" }
        ]
      },
      "overage": null,
      "tokenPricing": null,
      "note": "Subscription pricing not confirmed; contact Google for current pricing."
    },
    {
      "id": "code-assist-enterprise",
      "name": "Gemini Code Assist Enterprise",
      "type": "subscription",
      "billedBy": "google",
      "price": null,
      "allowance": {
        "unit": "requests",
        "quotas": [
          { "period": "day", "amount": 2000 },
          { "period": "4h-rolling", "amount": null, "note": "120 requests/minute rate limit" }
        ]
      },
      "overage": null,
      "tokenPricing": null,
      "note": "Subscription pricing not confirmed; contact Google for current pricing."
    },
    {
      "id": "gemini-api-paid",
      "name": "Gemini API Key (paid)",
      "type": "pay-per-token",
      "billedBy": "google",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        {
          "model": "gemini-2.5-pro",
          "inputPerMTokens": 1.25,
          "outputPerMTokens": 10.00,
          "currency": "USD",
          "contextTiers": [
            { "upToTokens": 200000, "inputPerMTokens": 1.25, "outputPerMTokens": 10.00 },
            { "upToTokens": null, "inputPerMTokens": 2.50, "outputPerMTokens": 15.00 }
          ]
        },
        {
          "model": "gemini-2.5-flash",
          "inputPerMTokens": 0.30,
          "outputPerMTokens": 2.50,
          "currency": "USD"
        }
      ],
      "note": "Requires Gemini API key with billing enabled. Billed via Google Cloud billing account."
    },
    {
      "id": "vertex-ai",
      "name": "Vertex AI",
      "type": "pay-per-token",
      "billedBy": "gcp",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        { "model": "gemini-2.5-pro", "inputPerMTokens": 1.25, "outputPerMTokens": 10.00, "currency": "USD" },
        { "model": "gemini-2.5-flash", "inputPerMTokens": 0.30, "outputPerMTokens": 2.50, "currency": "USD" }
      ],
      "note": "90-day Vertex AI Express Mode trial available before paid billing begins. Billed via GCP account."
    }
  ],
  "sources": [
    {
      "url": "https://geminicli.com/docs/quota-and-pricing/",
      "description": "Gemini CLI quota and pricing documentation - free tier limits and paid plan allowances",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://ai.google.dev/pricing",
      "description": "Google AI / Gemini API pricing - per-token costs by model",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    }
  ]
}
```

**Step 2: Commit**

```bash
git add agents/gemini-cli/pricing/current.json
git commit -m "feat: add gemini-cli pricing plans"
```

---

### Task 6: Create vscode-copilot pricing file

**Files:**
- Create: `agents/vscode-copilot/pricing/current.json`

**Step 1: Create directory and file**

```bash
mkdir -p agents/vscode-copilot/pricing
```

Content of `agents/vscode-copilot/pricing/current.json`:

```json
{
  "agent": "vscode-copilot",
  "lastUpdated": "2026-02-19",
  "plans": [
    {
      "id": "free",
      "name": "Copilot Free",
      "type": "free",
      "billedBy": "github",
      "price": {
        "amount": 0,
        "currency": "USD",
        "period": "month"
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 50 }
        ]
      },
      "overage": {
        "available": false,
        "model": "blocked",
        "note": "Free plan cannot purchase additional premium requests"
      },
      "tokenPricing": null,
      "note": "Also includes up to 2,000 inline code completion suggestions per month"
    },
    {
      "id": "pro",
      "name": "Copilot Pro",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 10,
        "currency": "USD",
        "period": "month",
        "annualOption": { "amount": 100, "currency": "USD", "period": "year" }
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 300 }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "premium-requests",
        "costPerUnit": 0.04,
        "currency": "USD",
        "note": "Overage requires setting a spending budget in account settings; default is $0 (requests blocked)"
      },
      "tokenPricing": null,
      "note": "Free for verified students, teachers, and maintainers of popular open-source projects"
    },
    {
      "id": "pro-plus",
      "name": "Copilot Pro+",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 39,
        "currency": "USD",
        "period": "month",
        "annualOption": { "amount": 390, "currency": "USD", "period": "year" }
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 1500 }
        ]
      },
      "overage": {
        "available": true,
        "model": "pay-as-you-go",
        "unit": "premium-requests",
        "costPerUnit": 0.04,
        "currency": "USD",
        "note": "Overage requires setting a spending budget in account settings; default is $0 (requests blocked)"
      },
      "tokenPricing": null,
      "note": null
    },
    {
      "id": "business",
      "name": "Copilot Business",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 19,
        "currency": "USD",
        "period": "seat/month"
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 300 }
        ]
      },
      "overage": {
        "available": true,
        "model": "configurable-budget",
        "unit": "premium-requests",
        "costPerUnit": null,
        "note": "Organization admin must enable 'Premium request paid usage' policy and set a spending budget"
      },
      "tokenPricing": null,
      "note": null
    },
    {
      "id": "enterprise",
      "name": "Copilot Enterprise",
      "type": "subscription",
      "billedBy": "github",
      "price": {
        "amount": 39,
        "currency": "USD",
        "period": "seat/month"
      },
      "allowance": {
        "unit": "premium-requests",
        "quotas": [
          { "period": "month", "amount": 1000, "note": "Approximately 3.33x Business (300); exact number not published" }
        ]
      },
      "overage": {
        "available": true,
        "model": "configurable-budget",
        "unit": "premium-requests",
        "costPerUnit": null,
        "note": "Organization admin must enable 'Premium request paid usage' policy and set a spending budget"
      },
      "tokenPricing": null,
      "note": null
    },
    {
      "id": "byo-anthropic",
      "name": "Anthropic API Key (BYO)",
      "type": "pay-per-token",
      "billedBy": "anthropic",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        { "model": "claude-opus-4-5", "inputPerMTokens": 15.00, "outputPerMTokens": 75.00, "currency": "USD" },
        { "model": "claude-sonnet-4-5", "inputPerMTokens": 3.00, "outputPerMTokens": 15.00, "currency": "USD" },
        { "model": "claude-haiku-3-5", "inputPerMTokens": 0.80, "outputPerMTokens": 4.00, "currency": "USD" }
      ],
      "note": "Add via VS Code language model picker → Manage Models → Add Models → Anthropic. Billed directly by Anthropic, not GitHub."
    },
    {
      "id": "byo-openai",
      "name": "OpenAI API Key (BYO)",
      "type": "pay-per-token",
      "billedBy": "openai",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": [
        { "model": "gpt-5", "inputPerMTokens": 2.50, "outputPerMTokens": 10.00, "currency": "USD" },
        { "model": "gpt-4o", "inputPerMTokens": 2.50, "outputPerMTokens": 10.00, "currency": "USD" }
      ],
      "note": "Add via VS Code language model picker → Manage Models → Add Models → OpenAI. Billed directly by OpenAI, not GitHub."
    },
    {
      "id": "byo-openai-compatible",
      "name": "OpenAI-compatible API (BYO)",
      "type": "pay-per-token",
      "billedBy": "varies",
      "price": null,
      "allowance": null,
      "overage": null,
      "tokenPricing": null,
      "note": "Supports any OpenAI-compatible endpoint (Azure OpenAI, local Ollama, etc.) via github.copilot.chat.customOAIModels setting. Pricing varies by provider."
    }
  ],
  "sources": [
    {
      "url": "https://docs.github.com/en/copilot/concepts/billing/individual-plans",
      "description": "GitHub Copilot individual plans - Free, Pro, Pro+ pricing and allowances",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://docs.github.com/en/copilot/managing-copilot/monitoring-usage-and-entitlements/about-premium-requests",
      "description": "GitHub Copilot premium requests - allowances per plan and overage billing",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    },
    {
      "url": "https://code.visualstudio.com/docs/copilot/language-models",
      "description": "VS Code Copilot language models - BYO API key configuration and supported providers",
      "verifiedDate": "2026-02-19",
      "sourceGranularity": "dedicated"
    }
  ]
}
```

**Step 2: Run validation — all four pricing warnings should now be cleared**

```bash
python3 framework/scripts/validate_framework.py 2>&1 | grep -A6 "8\. Checking"
```

Expected: four `+` lines, no `~` warnings for missing pricing files.

**Step 3: Commit**

```bash
git add agents/vscode-copilot/pricing/current.json
git commit -m "feat: add vscode-copilot pricing plans"
```

---

### Task 7: Update generate_static_api.py to serve pricing endpoints

**Files:**
- Modify: `framework/scripts/generate_static_api.py`

**Step 1: Add `load_pricing_data()` function after `load_verification_data()`**

After the `load_verification_data` function (around line 57), add:

```python
def load_pricing_data() -> Dict[str, Any]:
    """Load pricing data for all agents."""
    pricing = {}
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        pricing_file = agent_dir / "pricing" / "current.json"
        if pricing_file.exists():
            with open(pricing_file) as f:
                pricing[agent_dir.name] = json.load(f)
    return pricing
```

**Step 2: Add `generate_pricing_index()` function after `generate_index()`**

After the `generate_index` function, add:

```python
def generate_pricing_index(pricing: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the combined pricing endpoint."""
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'description': 'Pricing plans for all tracked agents. Each plan has a type (subscription, pay-per-token, free), billedBy provider, allowance quotas, and optional overage and tokenPricing details.',
        'agents': pricing
    }
```

**Step 3: Update `generate_index()` to add `pricing` to the endpoints map**

In `generate_index()`, change the `endpoints` dict from:

```python
        'endpoints': {
            'agents': '/api/v1/agents.json',
            'capabilities': '/api/v1/capabilities.json',
            'sources': '/api/v1/sources.json',
            'quality': '/api/v1/quality.json',
            'schema': '/api/v1/schema.json'
        },
```

To:

```python
        'endpoints': {
            'agents': '/api/v1/agents.json',
            'capabilities': '/api/v1/capabilities.json',
            'sources': '/api/v1/sources.json',
            'quality': '/api/v1/quality.json',
            'schema': '/api/v1/schema.json',
            'pricing': '/api/v1/pricing.json'
        },
```

**Step 4: Add pricing generation steps to `main()`**

In `main()`, after step 4 (capabilities list), add:

```python
    # 4b. Pricing data
    pricing_data = load_pricing_data()
    if pricing_data:
        print("  - pricing.json")
        write_json(DIST_DIR / "pricing.json", generate_pricing_index(pricing_data))
        for slug, data in pricing_data.items():
            print(f"  - agents/{slug}/pricing.json")
            write_json(DIST_DIR / "agents" / slug / "pricing.json", data)
```

**Step 5: Run the generator and verify new files appear**

```bash
python3 framework/scripts/generate_static_api.py
```

Expected output includes:
```
  - pricing.json
  - agents/claude-code/pricing.json
  - agents/copilot-cli/pricing.json
  - agents/gemini-cli/pricing.json
  - agents/vscode-copilot/pricing.json
```

Also verify the combined file is valid JSON:

```bash
python3 -c "import json; d=json.load(open('dist/api/v1/pricing.json')); print(list(d['agents'].keys()))"
```

Expected: `['claude-code', 'copilot-cli', 'gemini-cli', 'vscode-copilot']`

**Step 6: Verify `index.json` now includes pricing endpoint**

```bash
python3 -c "import json; d=json.load(open('dist/api/v1/index.json')); print(d['endpoints'])"
```

Expected includes `'pricing': '/api/v1/pricing.json'`.

**Step 7: Commit**

```bash
git add framework/scripts/generate_static_api.py
git commit -m "feat: add pricing endpoints to static API generator"
```

---

### Task 8: Final validation, regenerate, and merge

**Step 1: Run full validation**

```bash
python3 framework/scripts/validate_framework.py
```

Expected: `PASSED` with no new errors. Pricing warnings should all be cleared.

**Step 2: Regenerate comparison files**

```bash
python3 framework/scripts/generate_comparison.py
```

**Step 3: Push branch and open PR**

```bash
git push -u origin feature/pricing-plans
gh pr create --title "feat: add pricing plans for all agents" --body "$(cat <<'EOF'
## Summary

- Adds \`agents/{slug}/pricing/current.json\` for all four tracked agents (claude-code, copilot-cli, gemini-cli, vscode-copilot)
- Covers subscription/allowance plans, pay-per-token plans, and free tiers with overage models
- Adds \`/api/v1/pricing.json\` (combined) and \`/api/v1/agents/{slug}/pricing.json\` (per-agent) endpoints
- Adds pricing file validation step to \`validate_framework.py\`
- Adds \`framework/schemas/pricing-schema.json\`

## Test plan

- [ ] \`python3 framework/scripts/validate_framework.py\` passes with no new warnings
- [ ] \`dist/api/v1/pricing.json\` exists with all four agents
- [ ] \`dist/api/v1/agents/claude-code/pricing.json\` exists and is valid JSON
- [ ] \`dist/api/v1/index.json\` \`endpoints\` includes \`pricing\` key

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
