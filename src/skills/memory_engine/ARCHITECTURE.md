# ARCHITECTURE

This document describes the current memory architecture implemented in the `memory_engine` skill. It focuses on how the system avoids classic RAG failure modes (vector dilution, noisy logs, time-based aggregation inaccuracies) by using a hybrid 2-lane RAG design:

- A semantic recall (RAG) lane backed by Postgres + pgvector (good for “find the relevant day / concept”).
- A deterministic analytics lane backed by plain SQL over structured daily summaries (good for “counts / trends / top X / date lists”).

This document reflects the current codebase only and focuses on the architecture that is implemented today.

---

## 1. Key Concepts (What Exists Today)

### 1.1 Source Files

The system operates on a small set of file types:

- Daily notes: `YYYY-MM-DD.md`
- Raw transcripts: `YYYY-MM-DD-*.md`
- Daily summaries: `summaries/YYYY-MM-DD.summary.md` (Markdown with YAML frontmatter)
- Core knowledge docs: `MEMORY.md`, `SOUL.md`, `USER.md`, `IDENTITY.md`, `AGENTS.md`, `INFRASTRUCTURE.md`, and `MEMORY_INDEX.md`

Daily summaries are the “junction format”: they power both analytics and the memory index.

### 1.2 Storage Backends

#### A. Semantic Recall (Postgres + pgvector)

- Table: `nouva_memories`
- Content: embeddings for core knowledge docs (and the index map docs that help bridge query → date)
- Query method: cosine distance search via raw SQL

Code references:
- Vector table schema: [init_db.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/db/init_db.py)
- Vector search implementation: [db_helper.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/db/db_helper.py)

#### B. Deterministic Analytics (Postgres SQL)

- Table: `daily_summaries`
- Content: one row per date parsed from `.summary.md` YAML fields (arrays + scalar fields)
- Query method: pure SQL aggregations, with GIN indexes over arrays

Code references:
- Analytics schema + queries: [analytics_repo.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/db/analytics_repo.py)
- Sync `.summary.md` → `daily_summaries`: [analytics_sync.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/sync/analytics_sync.py)

---

## 2. System Overview Diagram (As Implemented)

```mermaid
flowchart LR
  subgraph Local["Active Memory Dir (local)"]
    DN["YYYY-MM-DD.md (daily note)"]
    RT["YYYY-MM-DD-*.md (raw transcripts)"]
    SUM["summaries/YYYY-MM-DD.summary.md"]
    IDX["MEMORY_INDEX.md"]
    CORE["MEMORY.md / SOUL.md / USER.md / ..."]
  end

  subgraph NAS["Archived Memory Dir (NAS)"]
    NASDAY["daily_sessions/YYYY-MM-DD/*"]
    NASSUM["daily_sessions/summaries/*.summary.md"]
    NASIDX["indexes/MEMORY_INDEX.md"]
    ENT["entities/*.md"]
  end

  subgraph PG["Postgres (RAG & Analytics Backends)"]
    VEC["pgvector: nouva_memories (Semantic RAG)"]
    ANA["SQL: daily_summaries (Analytics)"]
  end

  DN --> SUM
  RT --> SUM

  SUM --> IDX
  IDX --> NASIDX

  CORE --> VEC
  IDX --> VEC

  SUM --> ANA

  DN --> NASDAY
  RT --> NASDAY
  SUM --> NASSUM
  ENT --> NAS
```

---

## 3. Sync Pipeline (auto_sync.py)

The sync process is orchestrated by `auto_sync.py` and is designed to be incremental and idempotent:

- `sync-state.json` is used to drive incremental archival for daily sessions.
- Summaries are reconciled/created before archival, so the summary layer stays available even after local raw files are cleaned.

Code reference:
- Orchestrator: [auto_sync.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/auto_sync.py)

### 3.1 Diagram: Sync Steps (High Level)

```mermaid
flowchart TD
  CRON["cron / manual run"] --> AS["auto_sync.py"]

  AS --> S1["reconcile_missing_summaries()\nensure summaries exist"]
  S1 --> S1b["inject_related_dates()\npgvector-assisted linking\n+ ensure entity stubs on NAS"]

  AS --> S2["cleanup_local_rina_mentions()"]
  AS --> S3["sync_daily_summaries_to_db()\n.summary.md -> daily_summaries"]
  AS --> S4["generate_memory_index()\nfrom summaries (NAS-backed)"]
  AS --> S5["sync_core_files()\ncore docs -> pgvector"]
  AS --> S6["sync_memory_logs()\narchive daily notes + raw + summaries\n(sync-state.json; delete local)"]
  AS --> S7["sync_core_files_to_nas()"]
```

### 3.2 Note on LLM Usage

Summary generation uses a configurable LLM endpoint/model from `memory_config.json` via [summary_sync.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/sync/summary_sync.py). `llm.timeout_seconds` is configurable, while `temperature` currently falls back to the script default when omitted from config. If summaries already exist (pre-generated), the rest of the pipeline still works without calling an LLM.

---

## 4. Retrieval Flow (query_memory.py)

The RAG retrieval path is intentionally hybrid:

- Semantic search (RAG) is used primarily to find candidate dates (via the index map).
- Ranking weights and score decay are loaded from `memory_config.json` under `retrieval.*`.
- Summaries are the primary answer surface (short, clean, low token usage).
- Keyword scanning over summaries is always executed as a safety net.
- Raw transcripts are not automatically loaded; they are exposed via NAS path pointers.

Entry point:
- Tool wrapper: [query_memory.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/tools/query_memory.py)
- Script: [query_memory.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/query_memory.py)

### 4.1 Diagram: RAG Retrieval Tiers

```mermaid
flowchart TD
  U["User query"] --> QM["query_memory.py"]

  subgraph RAG["Two-Tier Hybrid RAG Pipeline"]
    QM --> V["Tier A: pgvector search (nouva_memories)\nreturns chunks from core docs"]
    V --> D{"Is chunk an index map\n(MEMORY_INDEX.md)?"}
    D -->|yes| EX["Extract YYYY-MM-DD dates (regex)"]
    D -->|no| RC["Keep as direct semantic chunks\n(MEMORY.md etc.)"]

    EX --> HS["Hybrid score per date\nsemantic+importance+recency\n+ configurable related_dates traversal"]
    HS --> SUM["Tier B: read summaries\n(local summaries/ OR NAS daily_sessions/summaries)"]

    QM --> KW["Tier C: keyword scan summaries (always)\nmerge + dedupe"]
  end

  SUM --> OUT["Return top summaries + NAS path pointers\nand optional semantic chunks"]
  KW --> OUT
  RC --> OUT
```

---

## 5. Analytics Flow (query_analytics.py)

Analytics queries should not be answered by semantic search. They are routed to SQL over `daily_summaries` and return deterministic results (counts, distributions, top values, date lists).

`query_analytics.py` is now an executor only:

- It accepts **structured analytics arguments**, not natural-language questions.
- Natural-language parsing belongs in the agent/client layer.
- The server validates the structured payload, syncs `daily_summaries`, then executes SQL or file-backed fallback logic.
- The analytics contract now supports both base intents (`dates_for_value`, `top_values`, `mood_timeseries`, `mood_distribution_by_weekday`) and quick-win aggregate intents (`count_distinct_dates_for_value`, `count_by_period`, `grouped_top_values`, `average_importance`).

Code reference:
- Tool wrapper: [query_analytics.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/tools/query_analytics.py)
- Script: [query_analytics.py](file:///Users/gadingnst/Workspace/nouverse/nouva-mcp-server/src/skills/memory_engine/scripts/query_analytics.py)

```mermaid
flowchart TD
  U["User analytics question\n(trends / counts / top X)"] --> AGENT["Agent/client parser\nconverts NL -> structured args"]
  AGENT --> QA["query_analytics.py\n(validate + execute)"]
  QA --> SYNC["sync_daily_summaries_to_db()"]
  SYNC --> SQL["SQL queries on daily_summaries"]
  SQL --> OUT["Deterministic analytics answer\n(+ optional date list)"]
```

---

## 6. What This Architecture Solves

- Vector dilution in RAG: embeddings focus on core docs and navigational index maps, not raw transcripts.
- Time-based aggregation: handled by structured SQL over `daily_summaries`, not by semantic similarity.
- Token efficiency: summaries are returned as the primary payload; raw logs remain available by path.

---

## 7. Known Operational Risks / Maintenance Notes

- `MEMORY_INDEX.md` can grow continuously; if it becomes too large for good semantic mapping, it should be split (index-of-indexes + topic sub-indexes).
- `memory_config.json` already reserves `multi_level_index_threshold_entries` and `multi_level_index_threshold_kb` for that future `MEMORY_INDEX.md` split/scaling strategy, but those thresholds are not enforced by runtime code yet.
- Append-only logs (for retrieval diagnostics) should have a rotation/retention strategy to avoid becoming a new “bloat file”.
