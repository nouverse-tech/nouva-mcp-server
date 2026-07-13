# Memory Engine Skill

This skill provides Nouva's current 2-lane memory architecture:

- **Semantic recall (RAG)** via **PostgreSQL + pgvector** for finding relevant concepts or dates.
- **Deterministic analytics** via structured SQL over daily summaries for counts, trends, and date lists.
- **Sync pipelines** that generate summaries, refresh the memory index, archive logs, and keep both storage lanes updated.

## Features
- **Semantic Vector Search (RAG)**: Uses a local embedding model (e.g. `bge-m3:latest`) to query pgvector memories.
- **Hybrid RAG Scoring**: Combines semantic similarity, importance, and recency using configurable weights from `memory_config.json`.
- **Obsidian Graph Expansion**: Traverses `related_dates` using a configurable graph depth and score decay.
- **Deterministic Analytics**: Loads `.summary.md` metadata into the `daily_summaries` SQL table for aggregation queries.
- **Auto-Sync / Ingestion**: Reconciles summaries, updates `MEMORY_INDEX.md`, syncs core docs to pgvector (RAG database), syncs daily summaries to SQL, and archives logs to NAS.
- **Memory Indexing (`MEMORY_INDEX.md`)**: Serves as the main historical memory map. This file is synced to `pgvector` and acts as a crucial key/map for the RAG retrieval pipeline, helping the system map semantic queries to specific dates before returning clean summaries and archive path pointers for optional transcript follow-up. An example structure of this file can be found in `memories/active/examples/MEMORY_INDEX.md`.

---

## Configuration

The skill configuration is defined in `memory_config.json`. 

For a deeper explanation of the 2-lane design, retrieval flow, analytics flow, and `MEMORY_INDEX.md` scaling direction, see [ARCHITECTURE.md](./ARCHITECTURE.md).

### 1. Setup Config File
Copy the example config:
```bash
cp src/skills/memory_engine/memory_config.example.json src/skills/memory_engine/memory_config.json
```

Then edit `memory_config.json` to match your infrastructure settings:
- **`database.host/port/name/user`**: PostgreSQL instance connection details.
- **`database.password`**: Database password (plain text, used when `database.url` is empty).
- **`database.url`**: Full connection string (overrides individual fields if provided). Format: `postgresql://user:password@host:port/dbname`
- **`embedding`**: URL and model name for generating embeddings.
- **`llm`**: Local proxy URL and model used for daily summary generation. `timeout_seconds` is configurable; `temperature` falls back to the script default when omitted.
- **`memory_paths`**: Active memory folder and archived NAS mount path configurations (**Note: These must be absolute paths**):
  - **`active_memory_dir`**: Absolute path to the active/writable memory directory. This contains files that are still in the process of being written (e.g., today's ongoing session transcripts and daily notes, as today is not yet finished).
  - **`archived_memory_dir`**: Absolute path to the archived read-only memory directory. This contains historical daily sessions, summaries, and indexes that are no longer modified. In production, this directory is typically mounted to an external storage server like a NAS.
- **`retrieval`**: Central tuning block for semantic recall:
  - `weights.semantic|importance|recency`
  - `decay_constant`
  - `vector_search_limit`
  - `default_semantic_score`
  - `max_graph_depth`
  - `related_date_score_decay`
  - `default_importance`
  - `invalid_date_fallback_days`
  - `keyword_boost.unique_match_weight|frequency_weight|frequency_cap`
- **`chunking`**: Vector indexing chunk size and overlap.
- **`max_related_dates`**: Maximum related dates written into generated `.summary.md` metadata.
- **`multi_level_index_threshold_entries` / `multi_level_index_threshold_kb`**: Reserved config fields for future `MEMORY_INDEX.md` scaling. They are intended to act as thresholds for switching from a single large index into a multi-level index layout (for example, index-of-indexes + topic/date sub-indexes), but they are currently not consumed by runtime code.

### 2. Config Structure Reference

Current retrieval-related settings are nested under `retrieval` instead of legacy top-level fields:

```json
{
  "retrieval": {
    "decay_constant": 0.005,
    "vector_search_limit": 10,
    "default_semantic_score": 0.5,
    "max_graph_depth": 2,
    "related_date_score_decay": 0.7,
    "default_importance": 5,
    "invalid_date_fallback_days": 365,
    "keyword_boost": {
      "unique_match_weight": 0.02,
      "frequency_weight": 0.005,
      "frequency_cap": 20
    },
    "weights": {
      "semantic": 0.5,
      "importance": 0.3,
      "recency": 0.2
    }
  },
  "llm": {
    "url": "http://localhost:3000/v1/chat/completions",
    "model": "gemini-3.5-flash-low",
    "timeout_seconds": 60
  },
  "chunking": {
    "max_chunk_size": 1000,
    "overlap": 100
  }
}
```

> **Note**: `memory_config.json` is git-ignored — it is safe to store credentials here.

---

## Database Initialization

If you are setting up the database for the first time:
```bash
python3 src/skills/memory_engine/memory_scripts/memory_db/memory_init_db.py
```
This script will enable the `vector` extension and create the `memory_vectors` table with an HNSW index.

---

## Running Auto-Sync

The auto-sync script runs periodically (recommended: daily via cron) to keep both memory lanes synchronized:

- Generate or reconcile missing daily summaries.
- Sync daily summary metadata into `daily_summaries`.
- Rebuild or update `MEMORY_INDEX.md`.
- Sync core docs and index files into pgvector.
- Archive daily logs and summaries to NAS.

```bash
python3 src/skills/memory_engine/memory_scripts/memory_auto_sync.py
```

---

## Analytics Tool Contract

`memory_analyze` is now a deterministic executor with **structured input only**.

- Do not send natural-language questions directly to the tool.
- The agent/client must first parse the user's request into explicit arguments.
- The executor reads from the existing `daily_summaries` dataset and falls back to file-backed `_summaries` parsing if the database path is unavailable.
- Supported intents: `dates_for_value`, `top_values`, `mood_timeseries`, `mood_distribution_by_weekday`, `count_distinct_dates_for_value`, `count_by_period`, `grouped_top_values`, `average_importance`.

### Supported Fields

- `intent`: required.
- `column`: required for `dates_for_value`, `top_values`, `count_distinct_dates_for_value`, `count_by_period`, and `grouped_top_values`. Allowed values: `projects`, `tags`, `people`, `technologies`. Optional for `average_importance`.
- `value`: required for `dates_for_value`, `count_distinct_dates_for_value`, and `count_by_period`. Optional for `average_importance`, but required if `column` is provided.
- `start_date`, `end_date`: ISO `YYYY-MM-DD`. Required for `mood_timeseries`. Optional for `dates_for_value`, `count_distinct_dates_for_value`, and `average_importance`. Optional for `top_values`, which defaults to the last 30 days when both are omitted. Optional for `count_by_period` and `grouped_top_values`, which default to the last 90 days when both are omitted.
- `weekday`: integer `0..6` (`0=Monday`).
- `weekday_name`: alternative to `weekday`, allowed values `monday..sunday`.
- `limit`: optional for `top_values` and `grouped_top_values`, range `1..50`, default `20` for `top_values` and `5` for `grouped_top_values`.
- `period`: required for `count_by_period` and `grouped_top_values`. Allowed values: `day`, `week`, `month`.

### Example Tool Calls

Top tags in May 2025:

```json
{
  "intent": "top_values",
  "column": "tags",
  "start_date": "2025-05-01",
  "end_date": "2025-05-31",
  "limit": 10
}
```

Dates associated with a project:

```json
{
  "intent": "dates_for_value",
  "column": "projects",
  "value": "Nouverse"
}
```

Mood timeseries:

```json
{
  "intent": "mood_timeseries",
  "start_date": "2026-07-01",
  "end_date": "2026-07-10"
}
```

Mood distribution by weekday:

```json
{
  "intent": "mood_distribution_by_weekday",
  "weekday": 1
}
```

Distinct dates for one value:

```json
{
  "intent": "count_distinct_dates_for_value",
  "column": "projects",
  "value": "Nouverse",
  "start_date": "2025-05-01",
  "end_date": "2025-05-31"
}
```

Counts grouped by period:

```json
{
  "intent": "count_by_period",
  "column": "projects",
  "value": "Nouverse",
  "period": "month",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30"
}
```

Top values grouped by period:

```json
{
  "intent": "grouped_top_values",
  "column": "tags",
  "period": "month",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30",
  "limit": 5
}
```

Average importance:

```json
{
  "intent": "average_importance",
  "column": "projects",
  "value": "Nouverse",
  "start_date": "2025-05-01",
  "end_date": "2025-05-31"
}
```

---

## Visual Graph with Obsidian

Since all daily logs and summaries are stored in a clean Markdown format (`YYYY-MM-DD.md` and `_summaries/YYYY-MM-DD.summary.md`), you can easily open the active/archived memory directories in [Obsidian](https://obsidian.md) to explore your memories visually as an interconnected knowledge graph.

![Obsidian Graph View](../../../assets/obsidian_graph.jpg)
