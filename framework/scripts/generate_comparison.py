#!/usr/bin/env python3
"""
Capability Comparison Generator

This script generates comparison matrices and reports from agent capability files.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
COMPARISONS_DIR = REPO_ROOT / "comparisons"


def load_agent_capabilities(agent_name: str) -> Dict[str, Any]:
    """Load current capabilities for an agent."""
    capability_file = AGENTS_DIR / agent_name / "capabilities" / "current.json"
    if not capability_file.exists():
        return {}
    
    with open(capability_file, 'r') as f:
        return json.load(f)


def get_all_agents() -> List[str]:
    """Get list of all tracked agents."""
    agents = []
    if not AGENTS_DIR.exists():
        return agents
    
    for item in AGENTS_DIR.iterdir():
        if item.is_dir() and (item / "capabilities").exists():
            agents.append(item.name)
    
    return sorted(agents)


def extract_capabilities_by_category(data: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """Group capabilities by category."""
    by_category = defaultdict(list)
    
    for cap in data.get('capabilities', []):
        category = cap.get('category', 'other')
        by_category[category].append(cap)
    
    return dict(by_category)


def generate_comparison_matrix() -> Dict[str, Any]:
    """Generate a comparison matrix of all agents and their capabilities."""
    agents = get_all_agents()
    
    if not agents:
        return {"error": "No agents found"}
    
    # Load all agent data
    agent_data = {}
    all_categories = set()
    
    for agent in agents:
        data = load_agent_capabilities(agent)
        if data:
            agent_data[agent] = data
            for cap in data.get('capabilities', []):
                all_categories.add(cap.get('category', 'other'))
    
    # Build comparison matrix
    matrix = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": list(agent_data.keys()),
        "categories": sorted(all_categories),
        "comparison": {}
    }
    
    # For each category, compare capabilities across agents
    for category in sorted(all_categories):
        matrix["comparison"][category] = {}
        
        for agent, data in agent_data.items():
            caps_in_category = [
                cap for cap in data.get('capabilities', [])
                if cap.get('category') == category
            ]
            
            matrix["comparison"][category][agent] = {
                "count": len(caps_in_category),
                "capabilities": [
                    {
                        "name": cap.get('name'),
                        "available": cap.get('available'),
                        "tier": cap.get('tier'),
                        "maturity": cap.get('maturityLevel')
                    }
                    for cap in caps_in_category
                ]
            }
    
    return matrix


def generate_capability_summary() -> Dict[str, Any]:
    """Generate a summary of capabilities across all agents."""
    agents = get_all_agents()
    
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": {}
    }
    
    for agent in agents:
        data = load_agent_capabilities(agent)
        if not data:
            continue
        
        agent_info = data.get('agent', {})
        capabilities = data.get('capabilities', [])
        
        summary["agents"][agent] = {
            "name": agent_info.get('name'),
            "vendor": agent_info.get('vendor'),
            "version": agent_info.get('version'),
            "total_capabilities": len(capabilities),
            "by_category": {},
            "by_tier": {},
            "by_maturity": {}
        }
        
        # Count by category
        for cap in capabilities:
            category = cap.get('category', 'other')
            summary["agents"][agent]["by_category"][category] = \
                summary["agents"][agent]["by_category"].get(category, 0) + 1
        
        # Count by tier
        for cap in capabilities:
            tier = cap.get('tier', 'unknown')
            summary["agents"][agent]["by_tier"][tier] = \
                summary["agents"][agent]["by_tier"].get(tier, 0) + 1
        
        # Count by maturity
        for cap in capabilities:
            maturity = cap.get('maturityLevel', 'unknown')
            summary["agents"][agent]["by_maturity"][maturity] = \
                summary["agents"][agent]["by_maturity"].get(maturity, 0) + 1
    
    return summary


def generate_markdown_comparison() -> str:
    """Generate a markdown comparison table."""
    agents = get_all_agents()
    agent_data = {agent: load_agent_capabilities(agent) for agent in agents}
    
    # Get all unique categories
    all_categories = set()
    for data in agent_data.values():
        for cap in data.get('capabilities', []):
            all_categories.add(cap.get('category', 'other'))
    
    md = ["# AI Agent Capability Comparison\n"]
    md.append(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n")
    md.append("## Overview\n")
    
    # Agent summary table
    md.append("| Agent | Vendor | Total Capabilities |")
    md.append("|-------|--------|-------------------|")
    
    for agent, data in agent_data.items():
        if not data:
            continue
        agent_info = data.get('agent', {})
        name = agent_info.get('name', agent)
        vendor = agent_info.get('vendor', 'Unknown')
        count = len(data.get('capabilities', []))
        md.append(f"| {name} | {vendor} | {count} |")
    
    md.append("\n## Capabilities by Category\n")
    
    # For each category, create a comparison
    for category in sorted(all_categories):
        md.append(f"\n### {category.replace('-', ' ').title()}\n")
        
        # Create table header
        md.append(f"| Capability | " + " | ".join(agent_data.keys()) + " |")
        md.append("|------------|" + "|".join(["------"] * len(agent_data)) + "|")
        
        # Collect all capability names in this category
        cap_names = set()
        for data in agent_data.values():
            for cap in data.get('capabilities', []):
                if cap.get('category') == category:
                    cap_names.add(cap.get('name'))
        
        # For each capability, show which agents have it
        for cap_name in sorted(cap_names):
            row = [cap_name]
            
            for agent, data in agent_data.items():
                # Find if this agent has this capability
                has_cap = False
                tier = ""
                
                for cap in data.get('capabilities', []):
                    if cap.get('category') == category and cap.get('name') == cap_name:
                        has_cap = cap.get('available', False)
                        tier = cap.get('tier', '')
                        break
                
                if has_cap:
                    row.append(f"✅ ({tier})")
                else:
                    # Check if similar capability exists
                    row.append("❌")
            
            md.append("| " + " | ".join(row) + " |")
    
    md.append("\n## Model Support\n")
    md.append("| Agent | Models Available |")
    md.append("|-------|------------------|")
    
    for agent, data in agent_data.items():
        if not data:
            continue
        models = data.get('models', [])
        model_names = [m.get('name', 'Unknown') for m in models]
        md.append(f"| {agent} | {', '.join(model_names)} |")
    
    md.append("\n## Integration Support\n")
    md.append("| Agent | Platforms |")
    md.append("|-------|-----------|")
    
    for agent, data in agent_data.items():
        if not data:
            continue
        integrations = data.get('integrations', [])
        platforms = [i.get('platform', 'Unknown') for i in integrations if i.get('supported', False)]
        md.append(f"| {agent} | {', '.join(platforms)} |")
    
    return "\n".join(md)


def main():
    """Main function to generate all comparisons."""
    print("Generating capability comparisons...")
    
    # Ensure comparisons directory exists
    COMPARISONS_DIR.mkdir(exist_ok=True, parents=True)
    
    # Generate comparison matrix
    print("  - Comparison matrix...")
    matrix = generate_comparison_matrix()
    with open(COMPARISONS_DIR / "comparison-matrix.json", 'w') as f:
        json.dump(matrix, f, indent=2)
    
    # Generate summary
    print("  - Capability summary...")
    summary = generate_capability_summary()
    with open(COMPARISONS_DIR / "capability-summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Generate markdown
    print("  - Markdown comparison...")
    markdown = generate_markdown_comparison()
    with open(COMPARISONS_DIR / "README.md", 'w') as f:
        f.write(markdown)
    
    print("✅ Comparison files generated successfully!")
    print(f"   - {COMPARISONS_DIR / 'comparison-matrix.json'}")
    print(f"   - {COMPARISONS_DIR / 'capability-summary.json'}")
    print(f"   - {COMPARISONS_DIR / 'README.md'}")


if __name__ == "__main__":
    main()
