import os
import sys
import subprocess

metadata = {
    "name": "mcp_query_analytics",
    "description": "Run deterministic analytics over daily summaries stored in Postgres (daily_summaries). Use for trends, counts, distributions, top values, and date lists (projects/people/tags/technologies/mood). Use mcp_query_memory for detailed recall."
}


async def handler(question: str) -> str:
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "query_analytics.py"))

    try:
        res = subprocess.run(
            [sys.executable, script_path, question],
            capture_output=True,
            text=True,
            timeout=45
        )
        if res.returncode == 0:
            return res.stdout
        return f"Error executing analytics query: {res.stderr}\nOutput: {res.stdout}"
    except Exception as e:
        return f"Exception executing analytics query: {str(e)}"
