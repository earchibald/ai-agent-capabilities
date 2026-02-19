#!/usr/bin/env python3
"""
Source Verification Pipeline

Three-pass verification of source citations, with autonomous maintenance mode.

Usage:
  python3 verify_sources.py                        # Run passes 1 and 2
  python3 verify_sources.py --pass3                # Also run pass 3 (requires LLM API)
  python3 verify_sources.py --agent gemini-cli     # Verify one agent only
  python3 verify_sources.py --fix-redirects        # Auto-update redirected URLs to canonical targets
  python3 verify_sources.py --apply-fixes fixes.json  # Apply a URL replacement mapping file
  python3 verify_sources.py --report               # Print fix report from last reachability run

Maintenance workflow:
  1. Run normally to produce reachability.json for each agent
  2. --fix-redirects reads those results, updates data files with canonical URLs
  3. For 404s: create a fixes.json mapping (old_url → new_url) then --apply-fixes
  4. Re-run to confirm all sources are healthy
"""

import json
import sys
import time
import hashlib
import argparse
import urllib.request
import urllib.error
import ssl
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from html.parser import HTMLParser
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

# Rate limiting: max requests per domain per second
RATE_LIMIT_DELAY = 1.0
_last_request_time: Dict[str, float] = {}


class TextExtractor(HTMLParser):
    """Extract text content and anchor IDs from HTML."""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.anchors = set()
        self._skip = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in ('script', 'style', 'noscript'):
            self._skip = True
        anchor_id = attrs_dict.get('id', '')
        if anchor_id:
            self.anchors.add(anchor_id)
        # Also check name attribute for anchors
        name = attrs_dict.get('name', '')
        if name:
            self.anchors.add(name)

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.text_parts.append(data)

    def get_text(self) -> str:
        return ' '.join(self.text_parts)

    def get_anchors(self) -> set:
        return self.anchors


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    from urllib.parse import urlparse
    return urlparse(url).netloc


def rate_limit(domain: str):
    """Apply rate limiting per domain."""
    now = time.time()
    last = _last_request_time.get(domain, 0)
    wait = RATE_LIMIT_DELAY - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_request_time[domain] = time.time()


def fetch_url(url: str, method: str = 'GET', timeout: int = 15) -> dict:
    """Fetch a URL and return status info."""
    domain = get_domain(url)
    rate_limit(domain)

    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method=method)
    req.add_header('User-Agent', 'AI-Agent-Capabilities-Tracker/1.0 (verification)')

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode('utf-8', errors='replace') if method == 'GET' else ''
            return {
                'status': resp.status,
                'url': resp.url,
                'redirected': resp.url != url,
                'body': body,
                'error': None
            }
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'url': url, 'redirected': False, 'body': '', 'error': str(e)}
    except urllib.error.URLError as e:
        return {'status': 0, 'url': url, 'redirected': False, 'body': '', 'error': str(e.reason)}
    except Exception as e:
        return {'status': 0, 'url': url, 'redirected': False, 'body': '', 'error': str(e)}


def pass1_reachability(agents: List[str]) -> Dict[str, Any]:
    """Pass 1: Check URL reachability via HTTP HEAD."""
    results = {}

    for agent_name in agents:
        cap_file = AGENTS_DIR / agent_name / "capabilities" / "current.json"
        if not cap_file.exists():
            continue

        with open(cap_file) as f:
            data = json.load(f)

        agent_results = []
        # Deduplicate URLs to avoid double-checking
        checked_urls: Dict[str, dict] = {}

        for cap in data.get('capabilities', []):
            for src in cap.get('sources', []):
                url = src.get('url', '')
                base_url = url.split('#')[0]  # Strip fragment for reachability

                if base_url not in checked_urls:
                    print(f"    HEAD {base_url[:80]}...")
                    result = fetch_url(base_url, method='HEAD')
                    checked_urls[base_url] = result

                r = checked_urls[base_url]
                agent_results.append({
                    'capability': cap.get('name'),
                    'url': url,
                    'status_code': r['status'],
                    'redirected': r['redirected'],
                    'redirect_url': r['url'] if r['redirected'] else None,
                    'error': r['error'],
                    'reachable': 200 <= r['status'] < 400
                })

        results[agent_name] = agent_results

    return results


def pass2_relevance(agents: List[str]) -> Dict[str, Any]:
    """Pass 2: Check content relevance via keyword/anchor/excerpt matching."""
    results = {}

    for agent_name in agents:
        cap_file = AGENTS_DIR / agent_name / "capabilities" / "current.json"
        if not cap_file.exists():
            continue

        with open(cap_file) as f:
            data = json.load(f)

        agent_results = []
        # Cache fetched pages
        page_cache: Dict[str, dict] = {}

        for cap in data.get('capabilities', []):
            for src in cap.get('sources', []):
                url = src.get('url', '')
                base_url = url.split('#')[0]
                fragment = url.split('#')[1] if '#' in url else None
                granularity = src.get('sourceGranularity', '')
                excerpt = src.get('excerpt', '')

                # Fetch page if not cached
                if base_url not in page_cache:
                    print(f"    GET {base_url[:80]}...")
                    result = fetch_url(base_url, method='GET')
                    if result['body']:
                        extractor = TextExtractor()
                        try:
                            extractor.feed(result['body'])
                        except Exception:
                            pass
                        page_cache[base_url] = {
                            'text': extractor.get_text().lower(),
                            'anchors': extractor.get_anchors(),
                            'raw': result['body'],
                            'reachable': 200 <= result['status'] < 400
                        }
                    else:
                        page_cache[base_url] = {
                            'text': '',
                            'anchors': set(),
                            'raw': '',
                            'reachable': False
                        }

                page = page_cache[base_url]
                check_result = {
                    'capability': cap.get('name'),
                    'url': url,
                    'granularity': granularity,
                    'relevant': False,
                    'checks': {}
                }

                if not page['reachable']:
                    check_result['checks']['page_reachable'] = False
                    agent_results.append(check_result)
                    continue

                # Check based on granularity
                if granularity == 'dedicated':
                    # For dedicated: capability name should appear on page
                    cap_name_lower = cap.get('name', '').lower()
                    name_found = cap_name_lower in page['text']
                    # Also check key words from the name
                    words = [w for w in cap_name_lower.split() if len(w) > 3]
                    words_found = sum(1 for w in words if w in page['text']) if words else 0
                    word_ratio = words_found / len(words) if words else 1.0
                    check_result['checks']['name_found'] = name_found
                    check_result['checks']['keyword_ratio'] = round(word_ratio, 2)
                    check_result['relevant'] = name_found or word_ratio >= 0.5

                elif granularity == 'section':
                    # For section: check that #fragment anchor exists
                    if fragment:
                        # Check various anchor formats
                        anchor_found = (
                            fragment in page['anchors']
                            or fragment.lower() in {a.lower() for a in page['anchors']}
                            or fragment.replace('-', '_') in page['anchors']
                        )
                        check_result['checks']['anchor_found'] = anchor_found
                        check_result['checks']['fragment'] = fragment
                        check_result['relevant'] = anchor_found
                    else:
                        check_result['checks']['no_fragment'] = True
                        check_result['relevant'] = False

                elif granularity == 'excerpt':
                    # For excerpt: check that excerpt text still appears
                    if excerpt:
                        # Normalize whitespace for comparison
                        excerpt_normalized = ' '.join(excerpt.lower().split())
                        text_normalized = ' '.join(page['text'].split())
                        # Check exact match first
                        exact = excerpt_normalized in text_normalized
                        # Then try fuzzy (first 50 chars)
                        prefix = excerpt_normalized[:50]
                        prefix_found = prefix in text_normalized
                        check_result['checks']['exact_match'] = exact
                        check_result['checks']['prefix_match'] = prefix_found
                        check_result['relevant'] = exact or prefix_found
                    else:
                        check_result['checks']['no_excerpt'] = True
                        check_result['relevant'] = False

                agent_results.append(check_result)

        results[agent_name] = agent_results

    return results


def save_results(agent_name: str, pass_name: str, results: Any):
    """Save verification results to agent's verification directory."""
    verify_dir = AGENTS_DIR / agent_name / "verification"
    verify_dir.mkdir(parents=True, exist_ok=True)

    output = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'pass': pass_name,
        'results': results
    }

    with open(verify_dir / f"{pass_name}.json", 'w') as f:
        json.dump(output, f, indent=2)
        f.write('\n')


def print_summary(pass_name: str, all_results: Dict[str, Any]):
    """Print a summary of verification results."""
    print(f"\n{'=' * 60}")
    print(f"  {pass_name} Summary")
    print(f"{'=' * 60}")

    for agent, results in all_results.items():
        total = len(results)
        if pass_name == 'reachability':
            passed = sum(1 for r in results if r.get('reachable'))
        else:
            passed = sum(1 for r in results if r.get('relevant'))

        status = "PASS" if passed == total else "WARN"
        print(f"  {agent}: {passed}/{total} {status}")

        # Show failures
        for r in results:
            ok = r.get('reachable') if pass_name == 'reachability' else r.get('relevant')
            if not ok:
                print(f"    FAIL: {r.get('capability')} -> {r.get('url', '')[:70]}")
                if r.get('error'):
                    print(f"          Error: {r['error']}")
                if r.get('checks'):
                    print(f"          Checks: {r['checks']}")


def load_reachability_results(agents: List[str]) -> Dict[str, list]:
    """Load saved reachability.json results for each agent."""
    all_results = {}
    for agent in agents:
        result_file = AGENTS_DIR / agent / "verification" / "reachability.json"
        if result_file.exists():
            with open(result_file) as f:
                data = json.load(f)
            all_results[agent] = data.get('results', [])
    return all_results


def fix_redirects(agents: List[str], dry_run: bool = False) -> dict:
    """
    Auto-fix maintenance pass: update redirected source URLs to their canonical targets.

    Reads saved reachability.json results, identifies redirects, and rewrites
    the source URL in each agent's current.json to the final redirect destination.
    Updates verifiedDate for all fixed sources.

    Returns a summary of changes made.
    """
    reachability = load_reachability_results(agents)
    if not reachability:
        print("No reachability results found. Run verification first.")
        return {}

    today = date.today().isoformat()
    all_changes = {}

    for agent in agents:
        cap_file = AGENTS_DIR / agent / "capabilities" / "current.json"
        if not cap_file.exists():
            continue

        agent_results = reachability.get(agent, [])
        if not agent_results:
            continue

        # Build redirect map: old_url → canonical_url
        redirect_map: Dict[str, str] = {}
        for r in agent_results:
            if r.get('redirected') and r.get('redirect_url'):
                old_url = r['url']
                # Strip fragment from old URL to match base URL
                old_base = old_url.split('#')[0]
                new_url = r['redirect_url']
                # Preserve fragment if present in original
                fragment = old_url.split('#')[1] if '#' in old_url else None
                if fragment:
                    # Try to keep fragment unless new URL already has one
                    if '#' not in new_url:
                        new_url_with_frag = new_url + '#' + fragment
                    else:
                        new_url_with_frag = new_url
                    redirect_map[old_url] = new_url_with_frag
                else:
                    redirect_map[old_base] = new_url

        if not redirect_map:
            continue

        with open(cap_file) as f:
            data = json.load(f)

        changes = []
        for cap in data.get('capabilities', []):
            for src in cap.get('sources', []):
                old_url = src.get('url', '')
                old_base = old_url.split('#')[0]
                new_url = redirect_map.get(old_url) or redirect_map.get(old_base)

                if new_url and new_url != old_url:
                    changes.append({
                        'capability': cap['name'],
                        'old_url': old_url,
                        'new_url': new_url
                    })
                    if not dry_run:
                        src['url'] = new_url
                        src['verifiedDate'] = today

        if changes and not dry_run:
            with open(cap_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.write('\n')

        all_changes[agent] = changes

    return all_changes


def apply_fixes(agents: List[str], fixes_file: Path, dry_run: bool = False) -> dict:
    """
    Apply a URL replacement mapping to all agent data files.

    The fixes file is a JSON object mapping old URLs to new URLs:
      {
        "https://old.example.com/moved-page": "https://old.example.com/new-location",
        ...
      }

    Also accepts extended format with granularity override:
      {
        "https://old.example.com/moved-page": {
          "url": "https://old.example.com/new-location",
          "sourceGranularity": "dedicated"
        }
      }

    Updates verifiedDate for all fixed sources.
    Returns a summary of changes made.
    """
    with open(fixes_file) as f:
        raw_fixes = json.load(f)

    # Normalise to {old_url: {url, sourceGranularity?}}
    fixes: Dict[str, dict] = {}
    for old_url, value in raw_fixes.items():
        if isinstance(value, str):
            fixes[old_url] = {'url': value}
        elif isinstance(value, dict):
            fixes[old_url] = value

    today = date.today().isoformat()
    all_changes = {}

    for agent in agents:
        cap_file = AGENTS_DIR / agent / "capabilities" / "current.json"
        if not cap_file.exists():
            continue

        with open(cap_file) as f:
            data = json.load(f)

        changes = []
        for cap in data.get('capabilities', []):
            for src in cap.get('sources', []):
                old_url = src.get('url', '')
                if old_url in fixes:
                    fix = fixes[old_url]
                    new_url = fix['url']
                    changes.append({
                        'capability': cap['name'],
                        'old_url': old_url,
                        'new_url': new_url,
                        'granularity_change': fix.get('sourceGranularity')
                    })
                    if not dry_run:
                        src['url'] = new_url
                        src['verifiedDate'] = today
                        if 'sourceGranularity' in fix:
                            src['sourceGranularity'] = fix['sourceGranularity']
                            # Remove excerpt if upgrading from excerpt to dedicated/section
                            if fix['sourceGranularity'] in ('dedicated', 'section'):
                                src.pop('excerpt', None)

        if changes and not dry_run:
            with open(cap_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.write('\n')

        all_changes[agent] = changes

    return all_changes


def print_fix_report(all_changes: dict, fix_type: str, dry_run: bool = False):
    """Print a human-readable report of what was or would be changed."""
    prefix = "[DRY RUN] Would fix" if dry_run else "Fixed"
    total = sum(len(v) for v in all_changes.values())

    if total == 0:
        print("  No changes needed.")
        return

    print(f"  {prefix} {total} source URL(s):")
    print()
    for agent, changes in all_changes.items():
        if not changes:
            continue
        print(f"  {agent}:")
        for c in changes:
            print(f"    [{c['capability']}]")
            print(f"      - {c['old_url']}")
            print(f"      + {c['new_url']}")
            if c.get('granularity_change'):
                print(f"      * sourceGranularity → {c['granularity_change']}")
        print()


def report_broken(agents: List[str]):
    """Print a summary of broken (404) sources from saved reachability results."""
    reachability = load_reachability_results(agents)
    if not reachability:
        print("No reachability results found. Run verification first.")
        return

    any_broken = False
    for agent, results in reachability.items():
        broken = [r for r in results if not r.get('reachable') and r.get('error')]
        if not broken:
            continue
        any_broken = True
        print(f"\n  {agent} ({len(broken)} broken):")
        seen_urls = set()
        for r in broken:
            url = r['url'].split('#')[0]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            print(f"    [{r['capability']}] {url}")
            print(f"      Error: {r['error']}")

    if not any_broken:
        print("  No broken sources found.")
    else:
        print()
        print("  To fix: create a fixes.json mapping old→new URLs and run:")
        print("    python3 verify_sources.py --apply-fixes fixes.json")




def main():
    parser = argparse.ArgumentParser(description='Verify source citations')
    parser.add_argument('--agent', help='Verify only this agent')
    parser.add_argument('--pass3', action='store_true', help='Also run semantic verification (pass 3)')
    parser.add_argument('--pass', dest='only_pass', type=int, help='Run only this pass (1, 2, or 3)')
    parser.add_argument('--fix-redirects', action='store_true',
                        help='Auto-update redirected URLs to their canonical targets')
    parser.add_argument('--apply-fixes', metavar='FIXES_JSON',
                        help='Apply a URL replacement mapping file (JSON: old_url → new_url)')
    parser.add_argument('--report', action='store_true',
                        help='Print report of broken sources from last reachability run')
    parser.add_argument('--dry-run', action='store_true',
                        help='With --fix-redirects or --apply-fixes: show what would change without writing')
    args = parser.parse_args()

    # Determine which agents to operate on
    if args.agent:
        agents = [args.agent]
    else:
        agents = sorted([
            d.name for d in AGENTS_DIR.iterdir()
            if d.is_dir() and (d / "capabilities" / "current.json").exists()
        ])

    # --- Maintenance modes (don't run verification passes) ---

    if args.report:
        print("Broken sources report")
        print("-" * 40)
        report_broken(agents)
        return

    if args.fix_redirects:
        print("Fixing redirected URLs → canonical targets")
        print("-" * 40)
        if args.dry_run:
            print("(DRY RUN - no files will be modified)")
            print()
        changes = fix_redirects(agents, dry_run=args.dry_run)
        print_fix_report(changes, 'redirect', dry_run=args.dry_run)
        if not args.dry_run and any(v for v in changes.values()):
            print("Run verification again to confirm fixes:")
            print("  python3 verify_sources.py")
        return

    if args.apply_fixes:
        fixes_file = Path(args.apply_fixes)
        if not fixes_file.exists():
            print(f"Error: fixes file not found: {fixes_file}")
            sys.exit(1)
        print(f"Applying URL fixes from {fixes_file.name}")
        print("-" * 40)
        if args.dry_run:
            print("(DRY RUN - no files will be modified)")
            print()
        changes = apply_fixes(agents, fixes_file, dry_run=args.dry_run)
        print_fix_report(changes, 'applied', dry_run=args.dry_run)
        if not args.dry_run and any(v for v in changes.values()):
            print("Run verification again to confirm fixes:")
            print("  python3 verify_sources.py")
        return

    # --- Normal verification passes ---

    run_pass1 = args.only_pass is None or args.only_pass == 1
    run_pass2 = args.only_pass is None or args.only_pass == 2
    run_pass3 = args.pass3 or args.only_pass == 3

    # Pass 1: Reachability
    if run_pass1:
        print("Pass 1: URL Reachability")
        print("-" * 40)
        p1_results = pass1_reachability(agents)
        for agent, results in p1_results.items():
            save_results(agent, 'reachability', results)
        print_summary('reachability', p1_results)
        print()

    # Pass 2: Content Relevance
    if run_pass2:
        print("Pass 2: Content Relevance")
        print("-" * 40)
        p2_results = pass2_relevance(agents)
        for agent, results in p2_results.items():
            save_results(agent, 'relevance', results)
        print_summary('relevance', p2_results)
        print()

    # Pass 3: Semantic Verification
    if run_pass3:
        print("Pass 3: Semantic Verification")
        print("-" * 40)
        print("  (Not yet implemented - requires LLM API integration)")
        print("  This pass will send page content + capability claims to an LLM")
        print("  for semantic verification of documentation claims.")
        print()

    print("Verification complete.")
    print(f"Results saved to agents/*/verification/")
    print()
    print("To auto-fix redirects:  python3 verify_sources.py --fix-redirects")
    print("To apply manual fixes:  python3 verify_sources.py --apply-fixes fixes.json")
    print("To view broken sources: python3 verify_sources.py --report")


if __name__ == "__main__":
    main()
