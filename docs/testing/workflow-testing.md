# Workflow Testing Reference

How to trigger and test the two automated workflows safely and repeatably.

## Prerequisites

- `gh` CLI authenticated
- Both workflows registered on `main` (see Setup)

## Safety inputs

Both `daily-research.yml` and `weekly-verification.yml` accept two `workflow_dispatch` inputs:

| Input | Default | Effect when true |
|---|---|---|
| `dry_run` | `false` | Logs what would happen; no commits, no issues created |
| `skip_copilot` | `false` | Omits `copilot` from issue assignees |

**Never set `skip_copilot=false` during testing** unless intentionally testing the full Copilot end-to-end path (uses premium requests).

Scheduled (`cron`) runs always use defaults — `dry_run=false, skip_copilot=false` — which is correct for production.

---

## Setup: Register workflows for dispatch

GitHub only registers `workflow_dispatch` for workflows on the default branch (`main`). One-time setup:

```bash
git checkout main
git checkout copilot/map-agents-capabilities -- .github/workflows/daily-research.yml .github/workflows/weekly-verification.yml
git commit -m "chore: register workflow files for dispatch testing"
git push origin main
git checkout copilot/map-agents-capabilities
```

Verify: `gh workflow list` should show "Daily Research Leads" and "Weekly Source Verification".

> **Note:** If the feature branch has since been merged, the workflows are already on `main` and no setup is needed.

---

## Testing: daily-research.yml

### Dry run (zero side effects)

```bash
gh workflow run "Daily Research Leads" \
  --ref copilot/map-agents-capabilities \
  -f dry_run=true -f skip_copilot=true
```

Monitor:
```bash
gh run list --workflow "Daily Research Leads" --limit 1
gh run watch <id>
```

Expected in logs:
- Agent stats collected (4 agents with capability counts)
- `DRY RUN — would create issue:` with title, labels, no assignees
- No issue created: `gh issue list --label research-leads`

### Real run (no Copilot)

```bash
gh workflow run "Daily Research Leads" \
  --ref copilot/map-agents-capabilities \
  -f dry_run=false -f skip_copilot=true
```

Expected:
- Issue created with correct title, body, and labels
- No assignees (Copilot not triggered)
- Verify: `gh issue list --label research-leads`

### Idempotency test

Run the real run again. Should log `Open research issue already exists, skipping.` and create no new issue.

### Cleanup

```bash
gh issue close <number> --comment "Test complete"
```

---

## Testing: weekly-verification.yml

### Dry run (zero side effects)

```bash
gh workflow run "Weekly Source Verification" \
  --ref copilot/map-agents-capabilities \
  -f dry_run=true -f skip_copilot=true
```

Expected in logs:
- Pass 1 + 2 run (HTTP reachability checks — takes ~2-5 min)
- Fix-redirects step prints `(DRY RUN)` if any redirects found
- Commit step is **SKIPPED**
- If broken URLs found: `DRY RUN — would create/update broken-source issue`
- No commits pushed, no issues created

### Real run (no Copilot)

```bash
gh workflow run "Weekly Source Verification" \
  --ref copilot/map-agents-capabilities \
  -f dry_run=false -f skip_copilot=true
```

Expected:
- Commit pushed to branch: `git fetch && git log --oneline origin/copilot/map-agents-capabilities -3`
- Verification timestamps updated in `agents/*/verification/*.json`
- If broken sources exist: issue created with `broken-source` label, no Copilot assignee

### Repeat test (comment-on-existing behaviour)

Run real run again while a `broken-source` issue is open. A comment should be appended to the existing issue rather than a new one created.

### Cleanup

```bash
gh issue close <number> --comment "Test complete"
git pull  # sync any commits from workflow runs
```

---

## Cleanup: main stubs (optional)

After the feature branch merges, the workflow stubs on `main` are superseded. If you need to remove them before merging:

```bash
git checkout main
git rm .github/workflows/daily-research.yml .github/workflows/weekly-verification.yml
git commit -m "chore: remove workflow stubs (superseded by merge)"
git push origin main
```
