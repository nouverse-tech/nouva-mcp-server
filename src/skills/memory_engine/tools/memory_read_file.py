import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../memory_scripts")))
from memory_util.memory_load_config import load_memory_config, resolve_paths

metadata = {
    "name": "memory_read_file",
    "description": "Read a memory file by location and path. IMPORTANT: Only use paths that appear EXACTLY in grep/search results. Never guess or fabricate filenames. The 'location' and 'path' must match what was returned by memory_grep (e.g. '[archived] daily_sessions/2026-07-14/2026-07-14-0903.md' means location='archived', path='daily_sessions/2026-07-14/2026-07-14-0903.md')."
}


def load_paths():
    config = load_memory_config()
    return resolve_paths(config)


async def handler(location: str, path: str) -> str:
    """Read a memory file.

    Args:
        location: 'active' or 'archived' — matches the prefix shown in search/grep results.
        path: Relative path after the base directory (e.g. 'daily_sessions/2026-07-14/2026-07-14-0903.md', '_summaries/2026-07-06.summary.md', 'MEMORY_INDEX.md').
    """
    active_dir, archived_dir = load_paths()

    if location == "active":
        base_dir = active_dir
    elif location == "archived":
        base_dir = archived_dir
    else:
        return f"Error: location must be 'active' or 'archived', got '{location}'."

    clean_rel = os.path.normpath(path).lstrip("/")
    if clean_rel.startswith("..") or os.path.isabs(clean_rel):
        return "Error: Invalid path."

    target_path = os.path.join(base_dir, clean_rel)
    if not os.path.abspath(target_path).startswith(os.path.abspath(base_dir)):
        return "Error: Invalid path."

    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        return f"Error: File not found at [{location}] {clean_rel}"

    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"
