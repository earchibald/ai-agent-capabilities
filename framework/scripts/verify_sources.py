#!/usr/bin/env python3
"""
Source Verification Pipeline

Three-pass verification of source citations:
  Pass 1: URL Reachability (HTTP HEAD, no LLM)
  Pass 2: Content Relevance (keyword/anchor/excerpt matching)
  Pass 3: Semantic Verification (LLM-assisted, on demand)

Usage:
  python3 verify_sources.py              # Run passes 1 and 2
  python3 verify_sources.py --pass3      # Also run pass 3 (requires OPENAI_API_KEY or similar)
  python3 verify_sources.py --agent gemini-cli  # Verify one agent only
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


def main():
    parser = argparse.ArgumentParser(description='Verify source citations')
    parser.add_argument('--agent', help='Verify only this agent')
    parser.add_argument('--pass3', action='store_true', help='Also run semantic verification (pass 3)')
    parser.add_argument('--pass', dest='only_pass', type=int, help='Run only this pass (1, 2, or 3)')
    args = parser.parse_args()

    # Determine which agents to verify
    if args.agent:
        agents = [args.agent]
    else:
        agents = sorted([
            d.name for d in AGENTS_DIR.iterdir()
            if d.is_dir() and (d / "capabilities" / "current.json").exists()
        ])

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


if __name__ == "__main__":
    main()
