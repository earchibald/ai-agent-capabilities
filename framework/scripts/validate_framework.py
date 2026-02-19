#!/usr/bin/env python3
"""
Framework Validation Script

This script validates the AI Agent Capabilities framework to ensure:
1. All capability files conform to the schema
2. All release notes conform to the schema
3. All required files exist
4. Source citations meet quality standards
5. Data freshness is tracked
"""

import json
import sys
from datetime import datetime, date
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
SCHEMA_DIR = REPO_ROOT / "framework" / "schemas"

STALENESS_WARN_DAYS = 30
STALENESS_ERROR_DAYS = 90

# Load valid enums from schema
VALID_CATEGORIES = set()
VALID_TIERS = set()
VALID_MATURITY = set()
VALID_STATUS = set()
VALID_GRANULARITY = set()
_schema_file = SCHEMA_DIR / "capability-schema.json"
if _schema_file.exists():
    with open(_schema_file, 'r') as f:
        _schema = json.load(f)
    cap_props = _schema.get('properties', {}).get('capabilities', {}).get('items', {}).get('properties', {})
    VALID_CATEGORIES = set(cap_props.get('category', {}).get('enum', []))
    VALID_TIERS = set(cap_props.get('tier', {}).get('enum', []))
    VALID_MATURITY = set(cap_props.get('maturityLevel', {}).get('enum', []))
    VALID_STATUS = set(cap_props.get('status', {}).get('enum', []))
    src_props = cap_props.get('sources', {}).get('items', {}).get('properties', {})
    VALID_GRANULARITY = set(src_props.get('sourceGranularity', {}).get('enum', []))


def load_json(filepath: Path) -> dict:
    """Load and parse a JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"  Error loading {filepath}: {e}")
        return {}


def validate_capability_file(filepath: Path) -> Tuple[bool, List[str], List[str]]:
    """Validate a capability file against expected structure and quality rules."""
    errors = []
    warnings = []
    data = load_json(filepath)

    if not data:
        return False, ["Could not load file"], []

    # Check required top-level keys
    required_keys = ['agent', 'capabilities']
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    # Validate agent info
    if 'agent' in data:
        agent = data['agent']
        required_agent_keys = ['name', 'vendor', 'version', 'lastUpdated']
        for key in required_agent_keys:
            if key not in agent:
                errors.append(f"Missing agent key: {key}")

    # Validate capabilities
    today = date.today()
    if 'capabilities' in data:
        if not isinstance(data['capabilities'], list):
            errors.append("'capabilities' must be a list")
        else:
            for i, cap in enumerate(data['capabilities']):
                if not isinstance(cap, dict):
                    errors.append(f"Capability {i} is not a dict")
                    continue

                cap_name = cap.get('name', '?')

                required_cap_keys = ['category', 'name', 'description', 'available']
                for key in required_cap_keys:
                    if key not in cap:
                        errors.append(f"Capability {i} ({cap_name}) missing key: {key}")

                # Validate category against schema enum
                cat = cap.get('category')
                if cat and VALID_CATEGORIES and cat not in VALID_CATEGORIES:
                    errors.append(f"Capability {i} ({cap_name}) invalid category: '{cat}'")

                # Validate tier against schema enum
                tier = cap.get('tier')
                if tier and VALID_TIERS and tier not in VALID_TIERS:
                    errors.append(f"Capability {i} ({cap_name}) invalid tier: '{tier}'")

                # Validate maturity against schema enum
                maturity = cap.get('maturityLevel')
                if maturity and VALID_MATURITY and maturity not in VALID_MATURITY:
                    errors.append(f"Capability {i} ({cap_name}) invalid maturity: '{maturity}'")

                # Validate status against schema enum
                status = cap.get('status')
                if status and VALID_STATUS and status not in VALID_STATUS:
                    errors.append(f"Capability {i} ({cap_name}) invalid status: '{status}'")

                # Validate terminology field type
                terminology = cap.get('terminology')
                if terminology is not None and not isinstance(terminology, str):
                    errors.append(f"Capability {i} ({cap_name}) terminology must be a string")

                # Source validation
                if 'sources' not in cap or not cap.get('sources'):
                    warnings.append(f"Capability {i} ({cap_name}) missing sources")
                else:
                    has_non_excerpt = False
                    for j, src in enumerate(cap['sources']):
                        if not isinstance(src, dict):
                            errors.append(f"Capability {i} ({cap_name}) source {j} is not a dict")
                            continue

                        # Required fields
                        for req_key in ['url', 'description', 'verifiedDate', 'sourceGranularity']:
                            if req_key not in src:
                                errors.append(f"Capability {i} ({cap_name}) source {j} missing: {req_key}")

                        # Validate source status
                        src_status = src.get('status')
                        if src_status and VALID_STATUS and src_status not in VALID_STATUS:
                            errors.append(f"Capability {i} ({cap_name}) source {j} invalid status: '{src_status}'")

                        # Validate sourceGranularity
                        granularity = src.get('sourceGranularity')
                        if granularity and VALID_GRANULARITY and granularity not in VALID_GRANULARITY:
                            errors.append(f"Capability {i} ({cap_name}) source {j} invalid granularity: '{granularity}'")

                        # Section sources must have #fragment
                        if granularity == 'section':
                            url = src.get('url', '')
                            if '#' not in url:
                                errors.append(f"Capability {i} ({cap_name}) source {j}: section granularity requires #fragment in URL")

                        # Excerpt sources must have excerpt field
                        if granularity == 'excerpt':
                            excerpt = src.get('excerpt', '')
                            if not excerpt:
                                errors.append(f"Capability {i} ({cap_name}) source {j}: excerpt granularity requires non-empty excerpt field")
                            elif len(excerpt) < 50:
                                warnings.append(f"Capability {i} ({cap_name}) source {j}: excerpt is short ({len(excerpt)} chars, recommend 50-300)")
                            elif len(excerpt) > 300:
                                warnings.append(f"Capability {i} ({cap_name}) source {j}: excerpt is long ({len(excerpt)} chars, recommend 50-300)")

                        if granularity in ('dedicated', 'section'):
                            has_non_excerpt = True

                        # Staleness detection
                        verified_str = src.get('verifiedDate', '')
                        if verified_str:
                            try:
                                verified = date.fromisoformat(verified_str)
                                age_days = (today - verified).days
                                if age_days > STALENESS_ERROR_DAYS:
                                    errors.append(
                                        f"Capability {i} ({cap_name}) source {j}: stale ({age_days} days since verification, max {STALENESS_ERROR_DAYS})"
                                    )
                                elif age_days > STALENESS_WARN_DAYS:
                                    warnings.append(
                                        f"Capability {i} ({cap_name}) source {j}: aging ({age_days} days since verification)"
                                    )
                            except ValueError:
                                errors.append(f"Capability {i} ({cap_name}) source {j}: invalid verifiedDate format")

                    # Warn if capability has only excerpt-tier sources
                    if not has_non_excerpt and cap.get('sources'):
                        warnings.append(
                            f"Capability {i} ({cap_name}): all sources are excerpt-tier (no dedicated or section-level documentation found)"
                        )

    return len(errors) == 0, errors, warnings


def validate_release_file(filepath: Path) -> Tuple[bool, List[str]]:
    """Validate a release note file."""
    errors = []
    data = load_json(filepath)

    if not data:
        return False, ["Could not load file"]

    # Check required keys
    required_keys = ['agent', 'version', 'releaseDate', 'changes']
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    # Validate changes
    if 'changes' in data:
        if not isinstance(data['changes'], list):
            errors.append("'changes' must be a list")

    return len(errors) == 0, errors


def main():
    """Main validation function."""
    print("=" * 60)
    print("AI Agent Capabilities Framework Validation")
    print("=" * 60)
    print()

    all_passed = True

    # Check required directories exist
    print("1. Checking directory structure...")
    required_dirs = [
        AGENTS_DIR,
        SCHEMA_DIR,
        REPO_ROOT / "framework" / "scripts",
        REPO_ROOT / "comparisons"
    ]

    for dir_path in required_dirs:
        if dir_path.exists():
            print(f"  + {dir_path.relative_to(REPO_ROOT)}")
        else:
            print(f"  X {dir_path.relative_to(REPO_ROOT)} - MISSING")
            all_passed = False
    print()

    # Check required scripts exist
    print("2. Checking automation scripts...")
    required_scripts = [
        REPO_ROOT / "framework" / "scripts" / "generate_comparison.py",
        REPO_ROOT / "framework" / "scripts" / "fetch_releases.py",
    ]

    for script in required_scripts:
        if script.exists():
            is_executable = script.stat().st_mode & 0o111
            status = "+ (executable)" if is_executable else "~ (not executable)"
            print(f"  {status} {script.name}")
        else:
            print(f"  X {script.name} - MISSING")
            all_passed = False
    print()

    # Validate capability files
    print("3. Validating capability files...")
    agents = [d for d in AGENTS_DIR.iterdir() if d.is_dir()]
    all_warnings = []
    total_caps = 0
    verified_within_30d = 0
    total_sources = 0

    for agent_dir in sorted(agents):
        agent_name = agent_dir.name
        cap_file = agent_dir / "capabilities" / "current.json"

        if cap_file.exists():
            valid, errors, warnings = validate_capability_file(cap_file)
            if valid:
                print(f"  + {agent_name}/capabilities/current.json")
            else:
                print(f"  X {agent_name}/capabilities/current.json")
                for error in errors:
                    print(f"      - {error}")
                all_passed = False
            all_warnings.extend(
                f"{agent_name}: {w}" for w in warnings
            )
            # Count stats
            data = load_json(cap_file)
            for cap in data.get('capabilities', []):
                total_caps += 1
                for src in cap.get('sources', []):
                    total_sources += 1
                    vd = src.get('verifiedDate', '')
                    if vd:
                        try:
                            age = (date.today() - date.fromisoformat(vd)).days
                            if age <= 30:
                                verified_within_30d += 1
                        except ValueError:
                            pass
        else:
            print(f"  ~ {agent_name}/capabilities/current.json - NOT FOUND")
    print()

    # Validate release files
    print("4. Validating release note files...")
    release_count = 0

    for agent_dir in sorted(agents):
        agent_name = agent_dir.name
        releases_dir = agent_dir / "releases"

        if releases_dir.exists():
            release_files = [f for f in releases_dir.glob("*.json") if f.name != "index.json"]

            for release_file in release_files:
                valid, errors = validate_release_file(release_file)
                if valid:
                    print(f"  + {agent_name}/releases/{release_file.name}")
                    release_count += 1
                else:
                    print(f"  X {agent_name}/releases/{release_file.name}")
                    for error in errors:
                        print(f"      - {error}")
                    all_passed = False

    if release_count == 0:
        print("  i No release files found (this is okay for initial setup)")
    print()

    # Check comparison files exist
    print("5. Checking generated comparison files...")
    comparison_files = [
        REPO_ROOT / "comparisons" / "README.md",
        REPO_ROOT / "comparisons" / "comparison-matrix.json",
        REPO_ROOT / "comparisons" / "capability-summary.json"
    ]

    for comp_file in comparison_files:
        if comp_file.exists():
            print(f"  + {comp_file.name}")
        else:
            print(f"  ~ {comp_file.name} - NOT FOUND (run generate_comparison.py)")
    print()

    # Data quality summary
    print("6. Data quality summary...")
    print(f"  Total capabilities: {total_caps}")
    print(f"  Total source citations: {total_sources}")
    print(f"  Sources verified within 30 days: {verified_within_30d}/{total_sources}")
    print()

    # Semantic gap detection
    print("7. Semantic gap detection...")
    agent_cap_map = {}  # agent_slug -> set of capability names
    cap_agent_map = {}  # capability_name -> set of agent slugs
    terminology_map = {}  # capability_name -> {agent_slug: terminology}
    for agent_dir in sorted(agents):
        agent_name = agent_dir.name
        cap_file = agent_dir / "capabilities" / "current.json"
        if not cap_file.exists():
            continue
        data = load_json(cap_file)
        cap_names = set()
        for cap in data.get('capabilities', []):
            name = cap.get('name')
            if not name:
                continue
            cap_names.add(name)
            if name not in cap_agent_map:
                cap_agent_map[name] = set()
            cap_agent_map[name].add(agent_name)
            # Track terminology
            term = cap.get('terminology')
            if term:
                if name not in terminology_map:
                    terminology_map[name] = {}
                terminology_map[name][agent_name] = term
        agent_cap_map[agent_name] = cap_names

    num_agents = len(agent_cap_map)
    gap_count = 0
    for cap_name, agent_set in sorted(cap_agent_map.items()):
        missing_from = set(agent_cap_map.keys()) - agent_set
        if missing_from and len(agent_set) >= num_agents - 1:
            for missing_agent in sorted(missing_from):
                all_warnings.append(
                    f"Semantic gap: '{cap_name}' present in {len(agent_set)}/{num_agents} agents, missing from {missing_agent}"
                )
                gap_count += 1

    # Terminology consistency: if any agent has terminology for a capability, all should
    for cap_name, terms in terminology_map.items():
        agents_with_cap = cap_agent_map.get(cap_name, set())
        agents_missing_term = agents_with_cap - set(terms.keys())
        if agents_missing_term:
            for a in sorted(agents_missing_term):
                all_warnings.append(
                    f"Terminology gap: '{cap_name}' has terminology for {sorted(terms.keys())} but not {a}"
                )

    if gap_count == 0:
        print("  + No semantic gaps detected (all capabilities present in all agents or unique)")
    else:
        print(f"  ~ {gap_count} semantic gap(s) detected (see warnings)")
    print()

    # Show warnings (non-blocking)
    if all_warnings:
        print(f"8. Warnings ({len(all_warnings)})...")
        for w in all_warnings:
            print(f"  ~ {w}")
        print()

    # Summary
    print("=" * 60)
    if all_passed:
        print("PASSED - Framework validation succeeded")
        if all_warnings:
            print(f"  ({len(all_warnings)} warnings)")
        print()
        print("Next steps:")
        print("  1. Run: python3 framework/scripts/generate_comparison.py")
        print("  2. Run: python3 framework/scripts/fetch_releases.py")
        print("  3. Review comparisons/README.md")
        return 0
    else:
        print("FAILED - Framework validation found errors")
        print()
        print("Please fix the errors above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
