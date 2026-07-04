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

### Aturan Emas Migrasi Skill ke MCP
* **Python-Based & Dockerized**: Server MCP utama ditulis menggunakan Python (FastMCP / MCP Python SDK) dan dideploy menggunakan Docker di container host `ai-engine` (LXC 106).
* **Self-Contained & Native**: Semua logic, parser, auth, dan eksekusi skill yang dimigrasi harus ditulis/dikonversi menjadi script **native** di dalam repositori MCP server.
* **Gak Boleh Numpuk / Reference External**: Dilarang keras membuat tool MCP yang hanya bertindak sebagai wrapper untuk memanggil script Python/Bash/JS di luar repositori (misalnya memanggil file di folder root `/root/.openclaw/workspace/skills/...`). Seluruh dependencies, logic, dan helper file harus dideklarasikan di dalam folder skill masing-masing di bawah `src/skills/` agar server MCP bener-bener portable dan detachable.
* **Secrets Management**: Semua secrets (seperti Google API tokens, credentials) disimpan di dalam folder `.secrets/` di root repositori MCP server dan **wajib dimasukkan ke `.gitignore`**. Jangan pernah melakukan hardcode credentials di dalam file skill, dan hindari membaca file credential dari path global sistem (seperti `/root/.openclaw/workspace/secrets/`) agar server MCP tetap portable.
* **SSH Keys Exception**: Untuk SSH key default host (seperti `/root/.ssh/id_ed25519_nouva`), diperbolehkan untuk dibaca langsung dari default path-nya karena sifatnya adalah konfigurasi environment host, bukan application-level secret.

---

## Rencana Fase Pengembangan

### 🚀 Fase 1: Inisialisasi & Core Skills (TypeScript -> Python & Docker Migration)
Migrasi fondasi server MCP dari TypeScript ke Python dan containerization dengan Docker.
- [ ] **Setup Project & Dockerfile**: Inisialisasi project Python dengan `Dockerfile` dan `docker-compose.yml` di folder `projects/nouva-mcp-server/`.
- [ ] **Dual Transport Support**:
  - **Opsi 1 (Stdio)**: Konfigurasi docker/ssh agar OpenClaw bisa memanggil container lewat SSH stdin/stdout.
  - **Opsi 2 (SSE)**: Menjalankan mode SSE HTTP server di port `8000` agar bisa diakses oleh client eksternal (Cursor/Hermes).
- [ ] **Core Skill - System Status**: Porting tool `system_status` ke Python.
- [ ] **Core Skill - Safe Shell Command**: Porting tool `run_safe_command` ke Python.
- [ ] **Skill - Contributing Gading Dev**: Porting tool `gading_dev_review` dan `gading_dev_publish` ke Python.
- [ ] **Integration Verification**: Menguji koneksi dengan OpenClaw (via SSH stdio) dan Cursor (via SSE HTTP).

### 🛠️ Fase 2: Migrasi Advanced Skills
Memindahkan skill-skill operasional yang saat ini ada di workspace OpenClaw ke dalam modul MCP Server agar bisa dipakai di agent lain.
- [ ] **TTS Local Mac (`mac_tts_speak`)**: Porting skill TTS menggunakan SSH ke MacBook Gading.
- [ ] **Google Workspace Helper**: Integrasi auth OAuth2 untuk memanipulasi Google Docs/Slides via MCP.
- [ ] **Server Management (Proxmox/LXC)**: Porting tool untuk mengontrol LXC container via command Proxmox.
- [ ] **Morning Report Trigger**: Porting logic morning-report full python.

### 🧠 Fase 3: Memory & RAG Integration
Menambahkan ingatan jangka panjang personal (Personalized Memory) ke dalam MCP Server.
- [ ] **SQLite-vec / Local Vector DB Setup**: Setup database vector ringan berbasis file.
- [ ] **Auto-indexing Memory**: Script untuk memindai file markdown di folder `memory/` dan menyimpannya sebagai embeddings.
- [ ] **Memory Retrieval Tool (`search_memory`)**: Tool bagi AI agent untuk mencari konteks masa lalu berdasarkan query semantik sebelum menjawab user.

---

## Panduan Integrasi Client

### 1. OpenClaw (Via SSH Stdio Transport)
Menggunakan `docker exec` melalui SSH ke LXC 106:
```json
{
  "mcpServers": {
    "nouva-mcp": {
      "command": "ssh",
      "args": [
        "-o", "StrictHostKeyChecking=no",
        "-i", "/root/.ssh/id_ed25519_nouva",
        "root@10.18.1.5",
        "pct exec 106 -- docker exec -i nouva-mcp-server python src/main.py --transport stdio"
      ]
    }
  }
}
```

### 2. Cursor / Windsurf / Hermes (Via SSE HTTP Transport)
Hubungkan ke server HTTP yang terekspos dari Docker di LXC 106:
- **URL**: `http://10.18.1.106:8000/sse`
