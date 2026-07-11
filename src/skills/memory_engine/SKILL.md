---
name: memory_engine
description: "Use the memory_engine tools for long-term memory recall, deterministic analytics, transcript logging, and sync operations."
---

# Memory Engine Skill

This skill exposes Nouva's 2-lane memory system:

- **Semantic recall** via `pgvector` for finding relevant concepts or dates.
- **Deterministic analytics** via SQL over daily summaries for counts, trends, and date lists.
- **Operational tools** for transcript writing and sync orchestration.

## Core Config
- **Memory Config**: `src/skills/memory_engine/memory_config.json` (contains hybrid scoring weights, graph traversal depths, database connection parameters including credentials, and embedding/LLM endpoints)

## Helper Scripts (Sync & Query Actions)
- **Auto Sync**: `src/skills/memory_engine/scripts/auto_sync.py` (Main smart sync for files, daily summaries, and logs)
- **Unified Memory Query**: `src/skills/memory_engine/scripts/query_memory.py` (Runs pgvector semantic search, applies Hybrid Scoring, resolves continue_of/related_dates via 1-hop expansion, then automatically falls back to NAS-by-date and NAS keyword search internally)
- **DB Init**: `src/skills/memory_engine/scripts/db/init_db.py` (Initialize local pgvector schema)

## Essential Endpoints / Commands

1. **Unified Memory Query (Recommended)**
   - Command: `python3 src/skills/memory_engine/scripts/query_memory.py "query"`
   - Purpose: Retrieve memory in one call. The script automatically: (1) searches pgvector for candidate dates/concepts, (2) computes a Hybrid Score (Semantic 50% + Importance 30% + Recency 20%), (3) performs 1-hop expansion over `related_dates` from `.summary.md` YAML frontmatter, (4) loads clean daily summaries from local/NAS storage, and (5) always runs keyword search over summaries as a safety net. Raw transcripts are not auto-loaded; the result returns archive path pointers.

## Memory Strategy

- **Writing New Facts**: When an important fact or decision is produced during conversation, write it into the appropriate memory workspace file (`MEMORY.md`, a daily note, or a transcript) explicitly.
- **Syncing (Automatic, not the agent's job)**: `auto_sync.py` reconciles summaries, syncs `.summary.md` metadata into SQL analytics, syncs core docs into pgvector, and archives raw logs to NAS. This runs as an operational pipeline, not as active "learning".

## Session Transcript Protocol

Nouva can log conversation sessions as transcript files in `active_memory_dir` using the `mcp_write_transcript` tool.

- **File format**: `YYYY-MM-DD-{sequential_id}.md` (e.g. `2026-07-09-0001.md`, `2026-07-09-0002.md`)
- **Session ID**: Auto-incremented per date. Each new conversation session gets the next available ID.
- **Header format**: Matches archived sessions (includes `Parent Day`, `Session Key`, `Session ID`, and `Source` fields).

Recommended create call:
- mode: `create`
- content: initial conversation content (plain text or markdown)
- session_key: `agent:main:{provider}:direct:{user_identifier_from_provider}`
- stable_session_id: UUID for stable cross-system reference (optional; generated if omitted)
- source: `whatsapp` | `telegram` | `webchat` | `unknown`

---

## Agent Integration (How the agent can use this skill)

### What SKILL.md is used for in this repo
- `SKILL.md` is loaded as resource guidelines by this server's dynamic skill loader, so agents will see it as usage guidance for this skill/tools.
- This is the best place to put tool-usage rules (when to use analytics vs semantic recall).
- Server installation details (Docker, mounts, etc.) are better documented in `README.md`, while agent usage rules belong in `SKILL.md`.

### MCP tools exposed by this skill
- `mcp_query_memory`: semantic recall (pgvector + fallback).
- `mcp_query_analytics`: analytics over daily YAML summaries (projects/tags/people/technologies/mood) with time-series aggregation.
- `mcp_write_transcript`: writes a session transcript into the memory workspace.
- `mcp_sync_memory`: runs the sync pipeline.

### How the agent should choose tools (routing rules)
Use these rules to keep analytics answers deterministic (not "LLM guessing"):

- Use `mcp_query_analytics` for questions that require aggregation/time-series:
  - "which days / when / how many times"
  - "pattern / trend"
  - "every <weekday>"
  - "last 2 weeks / last month"
  - "what did I talk about most"
- Use `mcp_query_memory` for detail/context recall:
  - "explain the details from that time"
  - "why / what decision / what plan"
  - "find the conversation that discussed ..."

### MCP client configuration (agent side)
The agent must be configured to connect to this MCP server (via Stdio or SSE) to call the tools above.

**Option A — Stdio (local)**
- Best when the agent runs on the same host and can execute Python directly.
- Example: run `python3 src/main.py --transport stdio`

**Option B — SSE (HTTP)**
- Best when the agent runs in a different environment and connects over HTTP.
- Run the server: `python3 src/main.py --transport sse --port 8000`
- Then register the MCP server in the agent using that SSE endpoint (URL depends on your host/IP).
