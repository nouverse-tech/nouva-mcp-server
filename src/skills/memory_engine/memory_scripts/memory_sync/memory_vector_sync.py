import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from memory_db import memory_db_helper as db_helper


def sync_vector_files(filenames: list, workspace_root: str) -> None:
    """Sync target files (MEMORY_INDEX.md, etc.) to pgvector."""
    print("--- Syncing Vector Files to pgvector ---")
    for filename in filenames:
        file_path = os.path.join(workspace_root, filename)
        if not os.path.exists(file_path):
            print(f"⏭️ File not found: {filename}")
            continue
        print(f"🔄 Syncing {filename} to pgvector...")
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            db_helper.sync_file_to_vector_db(f"indexes/{filename}", content, {"title": filename, "type": "index"})
        except Exception as e:
            print(f"❌ File {filename} vector sync FAILED: {e}")
