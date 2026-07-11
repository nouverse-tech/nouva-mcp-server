import os
import sys
import subprocess

metadata = {
    "name": "mcp_query_memory",
    "description": "Query Nouva long-term memory for recall (what happened / where was it mentioned). Uses pgvector semantic search to find relevant dates + reads daily summaries (local/NAS) and returns the best matching day summaries with archive path pointers. Use for detail/context recall only. Do not use for counts, trends, top values, grouped analytics, weekday distributions, or time-series aggregation; use mcp_query_analytics instead."
}

async def handler(query: str) -> str:
    """Query Nouva's long-term memory.
    
    Args:
        query: The search query (e.g. 'macbook air m1 specs', 'when is Gading's anniversary')
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "query_memory.py"))
    
    try:
        res = subprocess.run(
            [sys.executable, script_path, query],
            capture_output=True,
            text=True,
            timeout=45
        )
        if res.returncode == 0:
            return res.stdout
        else:
            return f"Error executing query: {res.stderr}\nOutput: {res.stdout}"
    except Exception as e:
        return f"Exception executing query: {str(e)}"
