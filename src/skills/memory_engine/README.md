# Memory Engine Skill

This skill provides Nouva's current 2-lane memory architecture:

- **Semantic recall** via **PostgreSQL + pgvector** for finding relevant concepts or dates.
- **Deterministic analytics** via structured SQL over daily summaries for counts, trends, and date lists.
- **Sync pipelines** that generate summaries, refresh the memory index, archive logs, and keep both storage lanes updated.

## Features
- **Semantic Vector Search**: Uses a local embedding model (e.g. `bge-m3:latest`) to query pgvector memories.
- **Hybrid Scoring**: Combines semantic similarity (50%), importance score (30%), and recency decay (20%).
- **Obsidian Graph Expansion**: Performs a 1-hop related dates expansion to bridge contextual gaps.
- **Deterministic Analytics**: Loads `.summary.md` metadata into the `daily_summaries` SQL table for aggregation queries.
- **Auto-Sync / Ingestion**: Reconciles summaries, updates `MEMORY_INDEX.md`, syncs core docs to pgvector, syncs daily summaries to SQL, and archives logs to NAS.

---

## Configuration

The skill configuration is defined in `memory_config.json`. 

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
- **`llm`**: Local proxy URL and model used for daily summary generation.
- **`memory_paths`**: Active memory folder and archived NAS mount path.

> **Note**: `memory_config.json` is git-ignored — it is safe to store credentials here.

---

## Database Initialization

If you are setting up the database for the first time:
```bash
python3 src/skills/memory_engine/scripts/db/init_db.py
```
This script will enable the `vector` extension and create the `nouva_memories` table with an HNSW index.

---

## Running Auto-Sync

The auto-sync script runs periodically (recommended: daily via cron) to keep both memory lanes synchronized:

- Generate or reconcile missing daily summaries.
- Sync daily summary metadata into `daily_summaries`.
- Rebuild or update `MEMORY_INDEX.md`.
- Sync core docs and index files into pgvector.
- Archive daily logs and summaries to NAS.

```bash
python3 src/skills/memory_engine/scripts/auto_sync.py
```

---

## Analytics Tool Contract

`mcp_query_analytics` is now a deterministic executor with **structured input only**.

- Do not send natural-language questions directly to the tool.
- The agent/client must first parse the user's request into explicit arguments.
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

