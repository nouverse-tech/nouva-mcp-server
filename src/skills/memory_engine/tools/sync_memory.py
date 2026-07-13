import os
import sys
import subprocess

metadata = {
    "name": "memory_sync",
    "description": "Run the memory_engine sync pipeline (auto_sync). Generates/reconciles daily summaries, updates Postgres (pgvector + analytics), generates MEMORY_INDEX, and archives daily sessions to the archived memory directory."
}

async def handler() -> str:
    """Trigger memory sync."""
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "auto_sync.py"))
    
    try:
        res = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=180
        )
        if res.returncode == 0:
            return res.stdout
        else:
            return f"Error executing sync: {res.stderr}\nOutput: {res.stdout}"
    except Exception as e:
        return f"Exception executing sync: {str(e)}"
