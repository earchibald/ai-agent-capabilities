#!/usr/bin/env python3
"""
Static API Generator

Generates a self-discoverable static API from agent capability data.
Output is deployed to GitHub Pages at /api/v1/.

Usage:
  python3 generate_static_api.py
  python3 generate_static_api.py --serve  # Generate and start local server
"""

import json
import re
import sys
import argparse
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
DIST_DIR = REPO_ROOT / "dist" / "api" / "v1"
COMPARISONS_DIR = REPO_ROOT / "comparisons"
SCHEMA_DIR = REPO_ROOT / "framework" / "schemas"


def slugify(name: str) -> str:
    """Convert a capability name to a URL-safe slug."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def load_agent_data() -> Dict[str, Any]:
    """Load all agent capability data."""
    agents = {}
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        cap_file = agent_dir / "capabilities" / "current.json"
        if cap_file.exists():
            with open(cap_file) as f:
                agents[agent_dir.name] = json.load(f)
    return agents


def load_verification_data(agent_name: str) -> Dict[str, Any]:
    """Load verification results for an agent."""
    verify_dir = AGENTS_DIR / agent_name / "verification"
    results = {}
    for pass_file in ('reachability.json', 'relevance.json', 'semantic.json'):
        path = verify_dir / pass_file
        if path.exists():
            with open(path) as f:
                results[pass_file.replace('.json', '')] = json.load(f)
    return results


def compute_quality_stats(agents: Dict[str, Any]) -> Dict[str, Any]:
    """Compute data quality statistics."""
    total_caps = 0
    total_sources = 0
    verified_30d = 0
    broken = 0
    granularity_counts = defaultdict(int)
    today = date.today()

    for agent_name, data in agents.items():
        for cap in data.get('capabilities', []):
            total_caps += 1
            for src in cap.get('sources', []):
                total_sources += 1
                g = src.get('sourceGranularity', 'unknown')
                granularity_counts[g] += 1
                vd = src.get('verifiedDate', '')
                if vd:
                    try:
                        age = (today - date.fromisoformat(vd)).days
                        if age <= 30:
                            verified_30d += 1
                    except ValueError:
                        pass
                if src.get('status') == 'broken':
                    broken += 1

    # Compute average granularity (dedicated=3, section=2, excerpt=1)
    scores = {'dedicated': 3, 'section': 2, 'excerpt': 1}
    weighted = sum(scores.get(g, 0) * c for g, c in granularity_counts.items())
    avg_score = weighted / total_sources if total_sources else 0
    avg_label = 'dedicated' if avg_score >= 2.5 else 'section' if avg_score >= 1.5 else 'excerpt'

    return {
        'totalCapabilities': total_caps,
        'totalSources': total_sources,
        'verifiedWithin30d': verified_30d,
        'brokenSources': broken,
        'averageSourceGranularity': avg_label,
        'granularityBreakdown': dict(granularity_counts)
    }


def generate_index(agents: Dict[str, Any], quality: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the root discovery endpoint."""
    return {
        'name': 'AI Agent Capabilities Tracker',
        'version': '1.0.0',
        'description': 'Structured capability data for AI coding agents, with verified source citations',
        'lastUpdated': datetime.now(timezone.utc).isoformat(),
        'dataQuality': quality,
        'endpoints': {
            'agents': '/api/v1/agents.json',
            'capabilities': '/api/v1/capabilities.json',
            'sources': '/api/v1/sources.json',
            'quality': '/api/v1/quality.json',
            'schema': '/api/v1/schema.json'
        },
        'agents': [
            {
                'name': data.get('agent', {}).get('name', slug),
                'slug': slug,
                'endpoint': f'/api/v1/agents/{slug}.json',
                'capabilities': len(data.get('capabilities', []))
            }
            for slug, data in agents.items()
        ]
    }


def generate_agents_list(agents: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the agents listing endpoint."""
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'agents': [
            {
                'slug': slug,
                'name': data.get('agent', {}).get('name', slug),
                'vendor': data.get('agent', {}).get('vendor', ''),
                'version': data.get('agent', {}).get('version', ''),
                'lastUpdated': data.get('agent', {}).get('lastUpdated', ''),
                'totalCapabilities': len(data.get('capabilities', [])),
                'endpoint': f'/api/v1/agents/{slug}.json'
            }
            for slug, data in agents.items()
        ]
    }


def generate_capabilities_list(agents: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the capabilities listing with slugs."""
    caps = {}
    for agent_slug, data in agents.items():
        for cap in data.get('capabilities', []):
            name = cap.get('name', '')
            slug = slugify(name)
            if slug not in caps:
                caps[slug] = {
                    'slug': slug,
                    'name': name,
                    'category': cap.get('category', ''),
                    'agents': [],
                    'comparisonEndpoint': f'/api/v1/comparisons/{slug}.json'
                }
            caps[slug]['agents'].append({
                'agent': agent_slug,
                'available': cap.get('available', False),
                'tier': cap.get('tier', ''),
                'maturityLevel': cap.get('maturityLevel', ''),
                'status': cap.get('status', '')
            })

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'capabilities': sorted(caps.values(), key=lambda c: c['name'])
    }


def generate_comparison(cap_name: str, cap_slug: str, agents: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a cross-agent comparison for a single capability."""
    comparison = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'capability': cap_name,
        'slug': cap_slug,
        'agents': {}
    }

    for agent_slug, data in agents.items():
        for cap in data.get('capabilities', []):
            if slugify(cap.get('name', '')) == cap_slug:
                comparison['agents'][agent_slug] = {
                    'name': data.get('agent', {}).get('name', agent_slug),
                    'available': cap.get('available', False),
                    'description': cap.get('description', ''),
                    'tier': cap.get('tier', ''),
                    'maturityLevel': cap.get('maturityLevel', ''),
                    'status': cap.get('status', ''),
                    'limitations': cap.get('limitations', []),
                    'sources': cap.get('sources', [])
                }
                break
        else:
            comparison['agents'][agent_slug] = {
                'name': data.get('agent', {}).get('name', agent_slug),
                'available': False,
                'description': 'Not available for this agent',
                'tier': None,
                'maturityLevel': None,
                'status': None,
                'limitations': [],
                'sources': []
            }

    return comparison


def write_json(path: Path, data: Any):
    """Write JSON to a file, creating directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description='Generate static API')
    parser.add_argument('--serve', action='store_true', help='Start local server after generation')
    parser.add_argument('--port', type=int, default=8080, help='Port for local server')
    args = parser.parse_args()

    print("Generating static API...")

    # Load all data
    agents = load_agent_data()
    if not agents:
        print("No agent data found.")
        return 1

    quality = compute_quality_stats(agents)

    # Clean dist directory
    if DIST_DIR.exists():
        import shutil
        shutil.rmtree(DIST_DIR)

    # 1. Root discovery endpoint
    print("  - index.json (discovery)")
    write_json(DIST_DIR / "index.json", generate_index(agents, quality))

    # 2. Agents list
    print("  - agents.json")
    write_json(DIST_DIR / "agents.json", generate_agents_list(agents))

    # 3. Per-agent endpoints
    for slug, data in agents.items():
        print(f"  - agents/{slug}.json")
        write_json(DIST_DIR / "agents" / f"{slug}.json", data)

    # 4. Capabilities list
    print("  - capabilities.json")
    caps_data = generate_capabilities_list(agents)
    write_json(DIST_DIR / "capabilities.json", caps_data)

    # 5. Per-capability comparison endpoints
    print("  - comparisons/...")
    seen_slugs = set()
    for agent_data in agents.values():
        for cap in agent_data.get('capabilities', []):
            name = cap.get('name', '')
            slug = slugify(name)
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                comparison = generate_comparison(name, slug, agents)
                write_json(DIST_DIR / "comparisons" / f"{slug}.json", comparison)
    print(f"    ({len(seen_slugs)} comparison files)")

    # 6. Sources index
    print("  - sources.json")
    sources_file = COMPARISONS_DIR / "sources-index.json"
    if sources_file.exists():
        with open(sources_file) as f:
            write_json(DIST_DIR / "sources.json", json.load(f))
    else:
        write_json(DIST_DIR / "sources.json", {'sources': []})

    # 7. Quality endpoint
    print("  - quality.json")
    quality_data = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'summary': quality,
        'perAgent': {}
    }
    for slug in agents:
        verification = load_verification_data(slug)
        quality_data['perAgent'][slug] = {
            'verification': {k: v.get('generated_at') for k, v in verification.items()},
            'hasVerification': bool(verification)
        }
    write_json(DIST_DIR / "quality.json", quality_data)

    # 8. Schema
    print("  - schema.json")
    schema_file = SCHEMA_DIR / "capability-schema.json"
    if schema_file.exists():
        with open(schema_file) as f:
            write_json(DIST_DIR / "schema.json", json.load(f))

    # Count total files
    total_files = sum(1 for _ in DIST_DIR.rglob("*.json"))
    print(f"\nGenerated {total_files} files in {DIST_DIR.relative_to(REPO_ROOT)}/")

    # Serve if requested
    if args.serve:
        import http.server
        import functools

        dist_root = DIST_DIR.parent.parent  # dist/
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(dist_root))
        with http.server.HTTPServer(('', args.port), handler) as httpd:
            print(f"\nServing at http://localhost:{args.port}/api/v1/index.json")
            print("Press Ctrl+C to stop.")
            httpd.serve_forever()

    return 0


if __name__ == "__main__":
    sys.exit(main())
