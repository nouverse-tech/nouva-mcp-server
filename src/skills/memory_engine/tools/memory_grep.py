import os

metadata = {
    "name": "memory_grep",
    "description": "Search for a specific keyword or pattern inside all memory markdown files (active and/or archived). IMPORTANT: Always search using English keywords, since all memory content is stored in English."
}

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../memory_scripts")))
from memory_util.memory_load_config import load_memory_config, resolve_paths

def load_paths():
    config = load_memory_config()
    return resolve_paths(config)

async def handler(query: str, location: str = "all") -> str:
    """Grep memory files.
    
    Args:
        query: The text/pattern to search for (case-insensitive)
        location: Location to search ('active', 'archived', or 'all')
    """
    active_dir, archived_dir = load_paths()
    
    targets = []
    if location in ("active", "all"):
        targets.append((active_dir, "active"))
    if location in ("archived", "all"):
        targets.append((archived_dir, "archived"))

    if not targets:
        return "Error: Invalid location specified. Use 'active', 'archived', or 'all'."

    query_lower = query.lower()
    results = []
    max_results = 100  # Cap results to avoid blowing up context

    for base_dir, loc_name in targets:
        if not os.path.exists(base_dir):
            continue
        for root, _, files in os.walk(base_dir):
            for file in files:
                if not file.endswith(".md"):
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)
                
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if query_lower in line.lower():
                                results.append(f"[{loc_name}] {rel_path}:{line_num}: {line.strip()}")
                                if len(results) >= max_results:
                                    break
                except Exception:
                    pass
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

    if not results:
        return f"No matches found for '{query}' in {location} memory."
    
    header = f"Found {len(results)} matches for '{query}' in {location} memory:"
    if len(results) >= max_results:
        header += " (capped to top 100)"

    # Extract unique file paths for easy reference
    seen_paths = []
    for r in results:
        # Format: [loc] path:line: content
        try:
            after_bracket = r.split("] ", 1)[1]
            file_path = after_bracket.split(":", 1)[0]
            loc = r.split("]", 1)[0].lstrip("[")
            entry = f"  - [{loc}] {file_path}"
            if entry not in seen_paths:
                seen_paths.append(entry)
        except Exception:
            pass

    footer = "\n\nFiles found (use these EXACT paths with memory_read_file):\n" + "\n".join(seen_paths)
    return header + "\n\n" + "\n".join(results) + footer
