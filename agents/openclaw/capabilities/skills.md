# OpenClaw Skills System

OpenClaw supports a modular skill system where agents load domain-specific markdown files before executing tasks.

## Key capabilities
- Skills are markdown files with YAML frontmatter (`name`, `description`, `version`)
- Skills live in `~/.openclaw/workspace/skills/`
- Agent reads relevant skill before starting a task (lazy loading)
- Compatible with googleworkspace/cli skill format
- 40+ community skills available at clawhub.com

## Skill categories supported
- Frontend design (UI/UX, typography, color)
- Video production (Remotion-based headless rendering)
- Web design guidelines
- Browser automation (Xbot MCP)
- Google Workspace (gws-compatible skills)
