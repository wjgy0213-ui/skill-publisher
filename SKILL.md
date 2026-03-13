---
name: skill-publisher
description: One-command skill publishing pipeline. Validate → Package (.skill) → GitHub repo create & push → SkillPay listing → config writeback. Use when packaging a skill for distribution, creating a GitHub repo for a skill, listing a skill on SkillPay, or checking publish status of an existing skill. Handles the full lifecycle from local skill directory to live marketplace listing.
---

# Skill Publisher v1.0

One-command pipeline: validate → package → GitHub → SkillPay → done.

## Quick Start

### Full Pipeline (recommended)
```bash
python3 scripts/publish_skill.py publish --path /path/to/my-skill --github-org wjgy0213-ui --price 1.0
```

### Individual Steps
```bash
# Validate skill structure
python3 scripts/publish_skill.py validate --path /path/to/my-skill

# Package only
python3 scripts/publish_skill.py package --path /path/to/my-skill

# Push to GitHub only
python3 scripts/publish_skill.py github --path /path/to/my-skill --github-org wjgy0213-ui

# Prepare SkillPay listing info
python3 scripts/publish_skill.py skillpay --name "My Skill" --desc "What it does" --price 0.5

# Check publish status
python3 scripts/publish_skill.py report --path /path/to/my-skill
```

### API Mode
```bash
echo '{"action":"publish","path":"./my-skill","github_org":"wjgy0213-ui","price":1.0}' | python3 scripts/publish_skill.py --api
```

## Pipeline Steps

| Step | What | Auto? |
|------|------|-------|
| 1. Validate | Check SKILL.md frontmatter, structure, config | ✅ |
| 2. Package | Create .skill zip file | ✅ |
| 3. GitHub | git init + create repo + push | ✅ (needs `gh` auth or browser) |
| 4. SkillPay | List on marketplace | ⚠️ Browser needed (no public API) |
| 5. Config | Write Skill ID back to config.json | ✅ (after manual step 4) |

## SkillPay Browser Automation

SkillPay doesn't have a public create-skill API. The tool outputs:
1. Pre-filled field values for browser form
2. Step-by-step browser automation instructions (for Agent with browser tool)
3. Post-creation config update command

For Agent automation: use the `browser_automation.steps` from `skillpay` action output to drive the SkillPay dashboard.

## Actions

| Action | Description |
|--------|-------------|
| `publish` | Full pipeline (all steps) |
| `validate` | Check skill structure |
| `package` | Create .skill package |
| `github` | Create repo + push |
| `skillpay` | Prepare SkillPay listing |
| `update_config` | Write Skill ID to config |
| `report` | Status report |

## Publish Checklist

See `references/publish-checklist.md` for the complete pre/post publish checklist.

## Files

- `scripts/publish_skill.py` — Main publisher script
- `scripts/config.json` — Default configuration
- `references/publish-checklist.md` — Publish checklist
