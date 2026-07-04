# ROADMAP_PLAN.md - Nouva MCP Server

Rencana pengembangan **Nouva MCP (Model Context Protocol) Server** sebagai repositori terpusat untuk *Personalized Skills* dan *Memory* yang bersifat modular, portable, dan *detachable* dari framework AI agent manapun (OpenClaw, Hermes, Claude Code, Cursor, dll.).

---

## Arsitektur Umum

```
[AI Agent / IDE Client]
  (Claude Code, Cursor, OpenClaw)
        │
        ▼ (via stdio / SSE)
┌─────────────────────────────────┐
│        Nouva MCP Server         │
│  ┌───────────────────────────┐  │
│  │       Skills Engine       │  │ (Porting dari local workspace skills)
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │   Memory Engine (RAG)     │  │ (SQLite / Vector DB lokal)
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

---

## Rencana Fase Pengembangan

### 🚀 Fase 1: Inisialisasi & Core Skills (Sedang Berjalan)
Fokus pada pembuatan fondasi server MCP yang stabil menggunakan Bun & TypeScript, serta mengimplementasikan skill dasar.
- [ ] **Setup Project**: Inisialisasi project Bun di folder `projects/nouva-mcp-server/`.
- [ ] **MCP SDK Integration**: Integrasi `@modelcontextprotocol/sdk` dengan transport `stdio`.
- [ ] **Core Skill - System Status**: Membuat tool `system_status` untuk mengecek kesehatan host local (load, RAM, disk).
- [ ] **Core Skill - Safe Shell Command**: Membuat tool `run_safe_command` untuk menjalankan command shell terbatas di sandbox workspace.
- [ ] **Integration Verification**: Menguji koneksi MCP server dengan Claude Code / OpenClaw lokal.

### 🛠️ Fase 2: Migrasi Advanced Skills
Memindahkan skill-skill operasional yang saat ini ada di workspace OpenClaw ke dalam modul MCP Server agar bisa dipakai di agent lain.
- [ ] **TTS Local Mac (`mac_tts_speak`)**: Porting skill TTS menggunakan SSH ke MacBook Gading.
- [ ] **Google Workspace Helper**: Integrasi auth OAuth2 untuk memanipulasi Google Docs/Slides via MCP.
- [ ] **Server Management (Proxmox/LXC)**: Porting tool untuk mengontrol LXC container via command Proxmox.
- [ ] **Morning Report Trigger**: Tool untuk men-trigger pembuatan report sistem.

### 🧠 Fase 3: Memory & RAG Integration
Menambahkan ingatan jangka panjang personal (Personalized Memory) ke dalam MCP Server.
- [ ] **SQLite-vec / Local Vector DB Setup**: Setup database vector ringan berbasis file.
- [ ] **Auto-indexing Memory**: Script untuk memindai file markdown di folder `memory/` dan menyimpannya sebagai embeddings.
- [ ] **Memory Retrieval Tool (`search_memory`)**: Tool bagi AI agent untuk mencari konteks masa lalu berdasarkan query semantik sebelum menjawab user.

---

## Panduan Integrasi Client

### 1. Claude Code (`~/.config/claude/config.json`)
```json
{
  "mcpServers": {
    "nouva-mcp": {
      "command": "bun",
      "args": ["run", "/root/.openclaw/workspace/projects/nouva-mcp-server/src/index.ts"]
    }
  }
}
```

### 2. Cursor / Windsurf
Tambahkan MCP Server baru di settings UI:
- **Name**: `nouva-mcp`
- **Type**: `stdio`
- **Command**: `bun run /root/.openclaw/workspace/projects/nouva-mcp-server/src/index.ts`
