# Nouva MCP Server 🌌🐱

Nouva MCP (Model Context Protocol) Server is a centralized repository for modular, portable, and detachable *Personalized Skills* and *Memory*. It is written in Python (FastMCP) and runs on Gading's `agent-host`. You can run it locally or in a containerized environment.

The server supports dual transport:
1. **Stdio Transport**: Used natively by OpenClaw on the local machine.
2. **SSE (Server-Sent Events) Transport**: Runs an HTTP server on port `8000` to be accessed by external clients like Cursor, Windsurf, or Hermes.

---

## Architecture Overview

```text
[AI Agent / IDE Client]
  (OpenClaw, Cursor, Zed, Claude Code)
        │
        ▼ (via stdio / SSE)
┌─────────────────────────────────┐
│           Nouva MCP Server      │
│  ┌───────────────────────────┐  │
│  │        Skills Engine       │  │ (native skills under src/skills/)
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │ Memory Engine (2-Lane)     │  │ (pgvector recall + SQL analytics + archived memory dir)
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### Skill migration rules (portable by design)
- Python-based: tools should be implemented as native Python inside this repository.
- Self-contained: avoid wrappers that call scripts outside the repo.
- Secrets: keep secrets out of git and out of the repo by default. Prefer environment variables or host-mounted secret files.

---

## Directory Structure

```text
nouva-mcp-server/
├── src/
│   ├── main.py                # Entrypoint & Dynamic Skill Loader
│   ├── skills/                # Modular skill directories (native Python)
│   │   ├── memory_engine/
│   │   │   ├── README.md      # Setup and operational notes for memory_engine
│   │   │   ├── SKILL.md       # Agent routing guidance for memory tools
│   │   │   ├── memory_config.example.json # Template config for memory variables
│   │   │   ├── scripts/
│   │   │   │   ├── auto_sync.py         # Memory auto-sync cron script
│   │   │   │   ├── query_memory.py      # Hybrid search query engine
│   │   │   │   ├── query_analytics.py   # Deterministic structured analytics executor
│   │   │   │   ├── db/                  # DB helpers and init scripts
│   │   │   │   │   ├── init_db.py
│   │   │   │   │   ├── db_helper.py
│   │   │   │   │   └── analytics_repo.py
│   │   │   │   └── sync/
│   │   │   │       ├── summary_sync.py
│   │   │   │       └── analytics_sync.py
│   │   │   └── tools/
│   │   │       ├── query_memory.py # Tool: query_memory
│   │   │       ├── query_analytics.py # Tool: structured analytics executor
│   │   │       └── sync_memory.py  # Tool: sync_memory
│   │   ├── mcp_management/
│   │   │   ├── SKILL.md       # Scaffolding guidelines (Resource)
│   │   │   └── tools/
│   │   │       └── create_skill.py # Tool: mcp_create_skill
│   └── utils/
├── requirements.txt           # Python dependencies
└── ROADMAP_PLAN.md            # Long-term development plan
```

---

## Deployment & Running Options

You can run Nouva MCP Server either **natively** using Python or containerized via **Docker**.

### Option A: Native Setup (Python)

#### 1. Prerequisites (System Dependencies)
Install minimal system dependencies required for python packages compilation (e.g. `psycopg2` for PostgreSQL):
```bash
apt update && apt install -y git build-essential libpq-dev python3-dev
```

#### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/nouverse-tech/nouva-mcp-server.git
cd nouva-mcp-server
pip install -r requirements.txt --break-system-packages
```

#### 3. Configure Memory
Copy the memory configuration file:
```bash
# Setup memory config (includes database credentials)
cp src/skills/memory_engine/memory_config.example.json src/skills/memory_engine/memory_config.json
# Edit src/skills/memory_engine/memory_config.json with your local details:
# - database.host/port/name/user/password (or database.url for full connection string)
# - embedding.url and embedding.model
# - llm.url and llm.model
# - memory_paths.active_memory_dir
```

#### 4. Running the Server (Stdio Mode)
```bash
python3 src/main.py --transport stdio
```

---

### Option B: Docker Setup

We provide a lightweight setup to build and run the MCP server in a Docker container.

#### 1. Build the Docker Image
```bash
docker build -t nouverse/nouva-mcp-server:latest .
```

#### 2. Run with Docker Compose
Ensure you have mapped your config files inside `docker-compose.yml`:
```bash
docker compose up -d
```

---

## Client Integration

### 1. OpenClaw (Local Stdio Transport)
Add the following configuration to your OpenClaw MCP config (path depends on your installation):
```json
{
  "mcpServers": {
    "nouva-mcp": {
      "command": "python3",
      "args": [
        "/absolute/path/to/nouva-mcp-server/src/main.py",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

### 2. Cursor

Cursor reads MCP server configs from:
- Project-scoped: `.cursor/mcp.json`
- User-scoped: `~/.cursor/mcp.json`

Option A — Connect via SSE (recommended if the server runs separately, e.g. Docker):
1) Start the server in SSE mode on the host:
```bash
python3 src/main.py --transport sse --port 8000
```

2) Add this to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "nouva-mcp": {
      "url": "http://<host>:8000/sse"
    }
  }
}
```

Option B — Run via stdio (Cursor spawns the process locally):

```json
{
  "mcpServers": {
    "nouva-mcp": {
      "command": "python3",
      "args": [
        "/absolute/path/to/nouva-mcp-server/src/main.py",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

Cursor MCP docs: https://cursor.com/docs/mcp

### 3. Zed

Zed stores MCP server configs in its settings file under `context_servers`. You can add this via UI ("Add Context Server") or edit settings manually.

Manual configuration example (`~/.config/zed/settings.json`), using stdio:

```json
{
  "context_servers": {
    "nouva-mcp": {
      "command": "python3",
      "args": [
        "/absolute/path/to/nouva-mcp-server/src/main.py",
        "--transport",
        "stdio"
      ],
      "env": {}
    }
  }
}
```

Zed MCP docs: https://zed.dev/docs/ai/mcp.html

### 4. Other clients (Windsurf, Hermes, etc.)

Start the server in SSE mode:

```bash
python3 src/main.py --transport sse --port 8000
```

Then connect using:
- URL: `http://<host>:8000/sse`
- Transport: SSE

### Do you need additional editor guidelines?

Connecting to the MCP server is enough for tool discovery. For best results, add a short routing rule in your agent instructions:
- Use `mcp_query_analytics` for aggregation/time-series questions, but call it with structured arguments only after the agent parses the user's natural-language request.
- Use `mcp_query_memory` for detailed recall and context.

---

## Memory Engine Integration
For detailed setup instructions regarding the 2-lane memory architecture, pgvector recall, SQL analytics, embedding settings, database initialization, and memory sync operations, please refer to the [Memory Engine README](src/skills/memory_engine/README.md).
