# ROADMAP_PLAN.md - Nouva MCP Server

Development roadmap for **Nouva MCP (Model Context Protocol) Server** as a centralized repository for modular, portable, and detachable *Personalized Skills* and *Memory*, usable from any agent/IDE client (OpenClaw, Hermes, Claude Code, Cursor, Zed, etc.).

---

## Architecture Overview

The up-to-date architecture diagram and client integration examples live in the root [README.md](README.md).

### Golden rules for migrating skills into MCP
- Python-based: the MCP server and its tools are implemented in Python (FastMCP / MCP Python SDK).
- Self-contained and native: skill logic, parsers, auth, and helpers must live inside this repo under `src/skills/`.
- No external wrappers: do not create MCP tools that merely call scripts outside this repository.
- Secrets management: keep secrets out of git and out of the repo by default. Prefer environment variables or host-mounted secret files. Avoid reading secrets from global paths so the repo stays portable.
- SSH keys exception: host-level SSH keys may be read from standard host paths when they are truly environment configuration.

---

## Phased Development Plan

### Phase 1: Initialization & Core Skills (TypeScript -> Python migration)
Migrate the MCP server foundation from TypeScript to Python and verify local integration.
- [x] Project setup: requirements and folder structure.
- [x] Core skill: `system_status` (Python).
- [x] Core skill: `run_safe_command` (Python).
- [x] Skill: MCP management scaffolding (`mcp_create_skill`).
- [x] Skill: `memory_engine` (Python).
- [x] Integration verification: connect MCP server to OpenClaw locally.

### Phase 2: Migrate advanced skills
Move operational skills from the OpenClaw workspace into this MCP Server repository so everything is portable and native.
- [ ] chart_maker: data visualization (matplotlib/python).
- [ ] document_converter: convert Markdown to Word via Pandoc.
- [ ] draw_diagram: render diagrams via Mermaid.js/Mermaid.ink.
- [ ] formula_renderer: render LaTeX formulas to PNG with handwriting fonts.
- [ ] github_pr: PR workflow SOP (branching, commits, review).

---

## Client Integration

Client integration examples are documented in the root [README.md](README.md).
