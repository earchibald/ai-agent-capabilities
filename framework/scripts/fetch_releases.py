#!/usr/bin/env python3
"""
Release Notes Fetcher

Fetches and processes release notes from various sources for tracked AI agents.
This script is designed to be run periodically to keep release notes up to date.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

# Configuration for each agent's release notes
AGENT_CONFIGS = {
    "vscode-copilot": {
        "name": "GitHub Copilot (VS Code)",
        "sources": [
            {
                "type": "changelog-url",
                "url": "https://github.blog/changelog/label/copilot/"
            }
        ]
    },
    "copilot-cli": {
        "name": "GitHub Copilot CLI",
        "sources": [
            {
                "type": "github-releases",
                "repo": "github/copilot-cli",
                "url": "https://api.github.com/repos/github/copilot-cli/releases"
            }
        ]
    },
    "claude-code": {
        "name": "Claude Code",
        "sources": [
            {
                "type": "changelog-url",
                "url": "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md"
            }
        ]
    },
    "gemini-cli": {
        "name": "Gemini CLI",
        "sources": [
            {
                "type": "github-releases",
                "repo": "google-gemini/gemini-cli",
                "url": "https://api.github.com/repos/google-gemini/gemini-cli/releases"
            },
            {
                "type": "changelog-url",
                "url": "https://geminicli.com/docs/changelogs/"
            }
        ]
    }
}


def fetch_github_releases(repo: str, since_date: Optional[datetime] = None) -> List[Dict]:
    """Fetch releases from GitHub API."""
    url = f"https://api.github.com/repos/{repo}/releases"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/vnd.github.v3+json')
        
        # Add GitHub token if available
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            req.add_header('Authorization', f'token {github_token}')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            releases = json.loads(response.read().decode())
        
        # Filter by date if specified
        if since_date:
            filtered = []
            for release in releases:
                published_at = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
                if published_at >= since_date:
                    filtered.append(release)
            return filtered
        
        return releases
    
    except urllib.error.HTTPError as e:
        print(f"Error fetching releases for {repo}: {e.code} {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error fetching releases for {repo}: {e}", file=sys.stderr)
        return []


def parse_github_release(release: Dict) -> Dict[str, Any]:
    """Parse a GitHub release into our schema format."""
    published_date = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
    
    return {
        "version": release.get('tag_name', release.get('name', 'Unknown')),
        "releaseDate": published_date.strftime('%Y-%m-%d'),
        "sourceUrl": release.get('html_url', ''),
        "changes": [
            {
                "type": "feature",
                "description": release.get('body', 'No description available'),
                "impact": "minor"
            }
        ],
        "capabilitiesAdded": [],
        "capabilitiesModified": [],
        "capabilitiesRemoved": []
    }


def fetch_agent_releases(agent_id: str, since_date: Optional[datetime] = None) -> List[Dict]:
    """Fetch releases for a specific agent."""
    config = AGENT_CONFIGS.get(agent_id)
    if not config:
        print(f"No configuration found for agent: {agent_id}", file=sys.stderr)
        return []
    
    all_releases = []
    
    for source in config.get('sources', []):
        source_type = source.get('type')
        
        if source_type == 'github-releases':
            repo = source.get('repo')
            releases = fetch_github_releases(repo, since_date)
            
            for release in releases:
                parsed = parse_github_release(release)
                parsed['agent'] = config['name']
                all_releases.append(parsed)
        
        elif source_type == 'changelog-url':
            # For changelog URLs, we'll add a placeholder
            # In a real implementation, you'd scrape or fetch these
            print(f"  Note: Changelog URL source requires manual review: {source.get('url')}")
    
    return all_releases


def save_releases(agent_id: str, releases: List[Dict]) -> None:
    """Save release notes to the agent's releases directory."""
    releases_dir = AGENTS_DIR / agent_id / "releases"
    releases_dir.mkdir(exist_ok=True, parents=True)
    
    # Save each release as a separate file
    for release in releases:
        version = release.get('version', 'unknown').replace('/', '-')
        filename = f"{version}.json"
        filepath = releases_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(release, f, indent=2)
    
    # Also save an index file
    index_file = releases_dir / "index.json"
    index_data = {
        "agent": agent_id,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "releases": [
            {
                "version": r.get('version'),
                "releaseDate": r.get('releaseDate'),
                "sourceUrl": r.get('sourceUrl')
            }
            for r in sorted(releases, key=lambda x: x.get('releaseDate', ''), reverse=True)
        ]
    }
    
    with open(index_file, 'w') as f:
        json.dump(index_data, f, indent=2)


def main():
    """Main function to fetch release notes for all agents."""
    # Calculate date 2 months ago (timezone-aware for GitHub API comparison)
    two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
    
    print(f"Fetching release notes since {two_months_ago.strftime('%Y-%m-%d')}...")
    print()
    
    for agent_id in AGENT_CONFIGS.keys():
        print(f"Processing {agent_id}...")
        
        releases = fetch_agent_releases(agent_id, since_date=two_months_ago)
        
        if releases:
            save_releases(agent_id, releases)
            print(f"  ✅ Saved {len(releases)} releases for {agent_id}")
        else:
            print(f"  ⚠️  No releases found for {agent_id}")
        
        print()
    
    print("✅ Release notes fetch complete!")
    print()
    print("📝 Next steps:")
    print("  1. Review the release notes in agents/*/releases/")
    print("  2. Update capability files based on new features")
    print("  3. Run generate_comparison.py to update comparisons")


if __name__ == "__main__":
    main()
