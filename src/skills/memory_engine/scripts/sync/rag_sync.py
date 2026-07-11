import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db import db_helper


def sync_core_files(filenames: list, workspace_root: str) -> None:
    """Sync OpenClaw core files (MEMORY_INDEX.md, USER.md, SOUL.md, etc.) to pgvector."""
    print("--- Syncing Core Files to pgvector ---")
    for filename in filenames:
        file_path = os.path.join(workspace_root, filename)
        if not os.path.exists(file_path):
            print(f"⏭️ Core file not found: {filename}")
            continue
        print(f"🔄 Syncing {filename} to pgvector...")
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            db_helper.sync_file_to_vector_db(f"cores/{filename}", content, {"title": filename, "type": "core"})
        except Exception as e:
            print(f"❌ Core file {filename} sync FAILED: {e}")
