import os

metadata = {
    "name": "mcp_read_memory_file",
    "description": "Read the raw content of a specific memory markdown file using its relative path."
}

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
from util.load_config import load_memory_config, resolve_paths

def load_paths():
    config = load_memory_config()
    return resolve_paths(config)

async def handler(relative_path: str, location: str = None) -> str:
    """Read a memory file.
    
    Args:
        relative_path: Relative path to the file (e.g. 'daily_sessions/2026-06-18/2026-06-18.md', 'MEMORY.md')
        location: Optional location override ('active' or 'archived')
    """
    active_dir, archived_dir = load_paths()
    
    # Clean path to prevent traversal
    clean_rel = os.path.normpath(relative_path).lstrip("/")
    if clean_rel.startswith("..") or os.path.isabs(clean_rel):
        return "Error: Invalid relative path (path traversal detected)."

    candidates = []
    if location == "active":
        candidates.append((active_dir, "active"))
    elif location == "archived":
        candidates.append((archived_dir, "archived"))
    else:
        candidates.append((active_dir, "active"))
        candidates.append((archived_dir, "archived"))

    for base_dir, loc_name in candidates:
        target_path = os.path.join(base_dir, clean_rel)
        # Double check path traversal
        if not os.path.abspath(target_path).startswith(os.path.abspath(base_dir)):
            continue
        if os.path.exists(target_path) and os.path.isfile(target_path):
            try:
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file from {loc_name}: {str(e)}"
    
    return f"Error: File '{clean_rel}' not found in the selected location(s)."
