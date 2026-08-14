# Testing — a Claude Code skill

Document-driven QA for a web platform. Reads the PRD, slice specs, permissions
matrix, workflows, user flows and design system, derives precise test cases
traced to numbered requirements, and verifies the running platform with
Playwright plus Jest/Vitest.

Covers the nine test types (unit, integration, mock, smoke, sanity, functional,
regression, exploratory, non-functional), design conformance, a deterministic
UI defect sweep, and per-module + per-type result files after every run.

## Install

Clone into your Claude Code skills directory. The folder name becomes the
`/command`, so clone it as `testing`:

```bash
# Personal — available in every project
git clone https://github.com/aswinr3/claude-testing-skill.git ~/.claude/skills/testing

# OR project-scoped — ships with one repo, available to anyone who clones it
git clone https://github.com/aswinr3/claude-testing-skill.git <project>/.claude/skills/testing
```

Then invoke it in Claude Code with `/testing`.

## What it needs

The skill is the methodology. It expects, but does not bundle:

- **Playwright** and **@axe-core/playwright** in the project under test.
- Optional MCP servers (Playwright MCP, Context7) — see `references/tooling.md`.

## Structure

- `SKILL.md` — the entry point Claude loads first.
- `references/` — loaded on demand, one file per job (branching, targets,
  document extraction, the nine test types, Playwright/Jest mechanics, design
  conformance, UI audit, evidence, result files, and more).
