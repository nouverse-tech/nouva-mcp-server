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
