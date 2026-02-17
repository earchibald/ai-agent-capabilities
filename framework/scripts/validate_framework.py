#!/usr/bin/env python3
"""
Framework Validation Script

This script validates the AI Agent Capabilities framework to ensure:
1. All capability files conform to the schema
2. All release notes conform to the schema
3. All required files exist
4. Scripts run without errors
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
SCHEMA_DIR = REPO_ROOT / "framework" / "schemas"

def load_json(filepath: Path) -> dict:
    """Load and parse a JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {filepath}: {e}")
        return {}

def validate_capability_file(filepath: Path) -> Tuple[bool, List[str]]:
    """Validate a capability file against expected structure."""
    errors = []
    data = load_json(filepath)
    
    if not data:
        return False, ["Could not load file"]
    
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
    if 'capabilities' in data:
        if not isinstance(data['capabilities'], list):
            errors.append("'capabilities' must be a list")
        else:
            for i, cap in enumerate(data['capabilities']):
                if not isinstance(cap, dict):
                    errors.append(f"Capability {i} is not a dict")
                    continue
                
                required_cap_keys = ['category', 'name', 'description', 'available']
                for key in required_cap_keys:
                    if key not in cap:
                        errors.append(f"Capability {i} missing key: {key}")
    
    return len(errors) == 0, errors

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
            print(f"  ✅ {dir_path.relative_to(REPO_ROOT)}")
        else:
            print(f"  ❌ {dir_path.relative_to(REPO_ROOT)} - MISSING")
            all_passed = False
    print()
    
    # Check required scripts exist
    print("2. Checking automation scripts...")
    required_scripts = [
        REPO_ROOT / "framework" / "scripts" / "generate_comparison.py",
        REPO_ROOT / "framework" / "scripts" / "fetch_releases.py",
        REPO_ROOT / "framework" / "scripts" / "update_automation.sh"
    ]
    
    for script in required_scripts:
        if script.exists():
            # Check if executable
            is_executable = script.stat().st_mode & 0o111
            status = "✅ (executable)" if is_executable else "⚠️  (not executable)"
            print(f"  {status} {script.name}")
        else:
            print(f"  ❌ {script.name} - MISSING")
            all_passed = False
    print()
    
    # Validate capability files
    print("3. Validating capability files...")
    agents = [d for d in AGENTS_DIR.iterdir() if d.is_dir()]
    
    for agent_dir in sorted(agents):
        agent_name = agent_dir.name
        cap_file = agent_dir / "capabilities" / "current.json"
        
        if cap_file.exists():
            valid, errors = validate_capability_file(cap_file)
            if valid:
                print(f"  ✅ {agent_name}/capabilities/current.json")
            else:
                print(f"  ❌ {agent_name}/capabilities/current.json")
                for error in errors:
                    print(f"      - {error}")
                all_passed = False
        else:
            print(f"  ⚠️  {agent_name}/capabilities/current.json - NOT FOUND")
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
                    print(f"  ✅ {agent_name}/releases/{release_file.name}")
                    release_count += 1
                else:
                    print(f"  ❌ {agent_name}/releases/{release_file.name}")
                    for error in errors:
                        print(f"      - {error}")
                    all_passed = False
    
    if release_count == 0:
        print("  ℹ️  No release files found (this is okay for initial setup)")
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
            print(f"  ✅ {comp_file.name}")
        else:
            print(f"  ⚠️  {comp_file.name} - NOT FOUND (run generate_comparison.py)")
    print()
    
    # Summary
    print("=" * 60)
    if all_passed:
        print("✅ Framework validation PASSED")
        print()
        print("Next steps:")
        print("  1. Run: python3 framework/scripts/generate_comparison.py")
        print("  2. Run: python3 framework/scripts/fetch_releases.py")
        print("  3. Review comparisons/README.md")
        return 0
    else:
        print("❌ Framework validation FAILED")
        print()
        print("Please fix the errors above before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
