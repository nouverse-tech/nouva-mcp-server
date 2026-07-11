import os
import sys
import subprocess
import json

metadata = {
    "name": "mcp_query_analytics",
    "description": (
        "Run deterministic analytics over daily summaries using STRUCTURED INPUT ONLY. "
        "Do not pass natural-language questions. Supported intents: dates_for_value, "
        "top_values, mood_timeseries, mood_distribution_by_weekday. Supported fields: "
        "intent, column, value, start_date, end_date, weekday, weekday_name, limit. "
        "Use mcp_query_memory for detailed recall."
    )
}


async def handler(
    intent: str,
    column: str | None = None,
    value: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    weekday: int | None = None,
    weekday_name: str | None = None,
    limit: int | None = None,
) -> str:
    """Run deterministic analytics with structured arguments only.

    Supported intents:
    - dates_for_value: requires column, value. Optional start_date, end_date.
    - top_values: requires column. Optional start_date, end_date, limit.
    - mood_timeseries: requires start_date, end_date.
    - mood_distribution_by_weekday: requires weekday or weekday_name.

    Example calls:
    - {"intent":"top_values","column":"tags","start_date":"2025-05-01","end_date":"2025-05-31","limit":10}
    - {"intent":"dates_for_value","column":"projects","value":"Nouverse"}
    - {"intent":"mood_distribution_by_weekday","weekday":1}
    """
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "query_analytics.py"))
    payload = {
        "intent": intent,
        "column": column,
        "value": value,
        "start_date": start_date,
        "end_date": end_date,
        "weekday": weekday,
        "weekday_name": weekday_name,
        "limit": limit,
    }

    try:
        res = subprocess.run(
            [sys.executable, script_path, json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=45
        )
        if res.returncode == 0:
            return res.stdout
        return f"Error executing analytics query: {res.stderr}\nOutput: {res.stdout}"
    except Exception as e:
        return f"Exception executing analytics query: {str(e)}"
