import os
import sys
import json
import datetime

sys.path.insert(0, os.path.dirname(__file__))

from db import db_helper
from util.load_config import load_memory_config
from sync.analytics_sync import load_daily_summaries_from_files, sync_daily_summaries_to_db
from db.analytics_repo import (
    ensure_schema,
    get_dates_for_array_value,
    get_mood_distribution_by_weekday,
    get_mood_timeseries,
    get_top_values,
)


_WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_WEEKDAY_DISPLAY = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

_VALID_INTENTS = {
    "dates_for_value",
    "top_values",
    "mood_timeseries",
    "mood_distribution_by_weekday",
}

_SCHEMA_HELP = (
    "Structured analytics query required. Supported intents: "
    "dates_for_value, top_values, mood_timeseries, mood_distribution_by_weekday.\n"
    "Fields: intent, column, value, start_date, end_date, weekday, weekday_name, limit.\n"
    "Examples:\n"
    '- {"intent":"top_values","column":"tags","start_date":"2025-05-01","end_date":"2025-05-31","limit":10}\n'
    '- {"intent":"dates_for_value","column":"projects","value":"Nouverse"}\n'
    '- {"intent":"mood_distribution_by_weekday","weekday":1}'
)


def _parse_iso_date(value: str | None) -> datetime.date | None:
    """Parse an ISO date string into a date object."""
    if not value:
        return None
    try:
        return datetime.datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except Exception as exc:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def _normalize_array_column(value: str | None) -> str | None:
    """Normalize supported analytics array columns."""
    if not value:
        return None
    v = str(value).strip().lower()
    if v in ["projects", "project"]:
        return "projects"
    if v in ["tags", "tag", "topics", "topic"]:
        return "tags"
    if v in ["people", "person", "persons"]:
        return "people"
    if v in ["technologies", "technology", "tech", "stack"]:
        return "technologies"
    return None


def _map_query_value(value: str, category: str, config: dict) -> list[str]:
    """Expand a query value using configured link mappings."""
    v = (value or "").strip()
    if not v:
        return []
    variants = [v]
    mappings = (config.get("link_mappings", {}) or {}).get(category, {}) if isinstance(config, dict) else {}
    if isinstance(mappings, dict):
        mapped = mappings.get(v.lower())
        if mapped and mapped not in variants:
            variants.append(mapped)
    return variants


def _render_date_list(dates: list[datetime.date]) -> str:
    """Render a list of dates as markdown bullets."""
    if not dates:
        return "(empty)"
    return "\n".join([f"- {d.strftime('%Y-%m-%d')}" for d in dates])


def _render_kv_table(rows: list[tuple[str, int]]) -> str:
    """Render key/value analytics rows as markdown bullets."""
    if not rows:
        return "(empty)"
    return "\n".join([f"- {k}: {v}" for k, v in rows])


def _default_top_values_range() -> tuple[datetime.date, datetime.date]:
    """Return the default date window for top_values when none is provided."""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=29)
    return start_date, end_date


def _normalize_weekday(weekday: int | str | None, weekday_name: str | None) -> int | None:
    """Normalize weekday from integer or weekday name."""
    if weekday is not None:
        try:
            parsed = int(weekday)
        except Exception as exc:
            raise ValueError("weekday must be an integer between 0 and 6.") from exc
        if parsed not in _WEEKDAY_DISPLAY:
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday).")
        return parsed

    if weekday_name:
        parsed = _WEEKDAY_MAP.get(str(weekday_name).strip().lower())
        if parsed is None:
            raise ValueError("weekday_name must be one of monday..sunday.")
        return parsed

    return None


def _validate_request(request: dict) -> dict:
    """Validate and normalize a structured analytics request."""
    if not isinstance(request, dict):
        raise ValueError("Analytics input must be a JSON object.")

    intent = str(request.get("intent") or "").strip()
    if intent not in _VALID_INTENTS:
        raise ValueError(f"Unsupported intent '{intent}'.")

    start_date = _parse_iso_date(request.get("start_date"))
    end_date = _parse_iso_date(request.get("end_date"))
    if (start_date and not end_date) or (end_date and not start_date):
        raise ValueError("start_date and end_date must be provided together.")
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date cannot be after end_date.")

    column = _normalize_array_column(request.get("column"))
    value = request.get("value")
    weekday = _normalize_weekday(request.get("weekday"), request.get("weekday_name"))
    limit = request.get("limit")

    if intent in {"dates_for_value", "top_values"} and not column:
        raise ValueError(f"intent '{intent}' requires column.")
    if intent == "dates_for_value" and not value:
        raise ValueError("intent 'dates_for_value' requires value.")
    if intent == "mood_timeseries" and not (start_date and end_date):
        raise ValueError("intent 'mood_timeseries' requires start_date and end_date.")
    if intent == "mood_distribution_by_weekday" and weekday is None:
        raise ValueError("intent 'mood_distribution_by_weekday' requires weekday or weekday_name.")

    if limit is not None:
        try:
            limit = int(limit)
        except Exception as exc:
            raise ValueError("limit must be an integer between 1 and 50.") from exc
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50.")

    if intent == "top_values" and limit is None:
        limit = 20
    if intent == "top_values" and not (start_date and end_date):
        start_date, end_date = _default_top_values_range()

    return {
        "intent": intent,
        "column": column,
        "value": str(value).strip() if value is not None else None,
        "start_date": start_date,
        "end_date": end_date,
        "weekday": weekday,
        "limit": limit,
    }


def _try_sync_db(config: dict) -> bool:
    """Attempt to refresh analytics rows into Postgres."""
    try:
        sync_daily_summaries_to_db(config)
        return True
    except Exception:
        return False


def _execute_query_db(request: dict, config: dict, conn) -> str | None:
    """Execute a normalized analytics request against Postgres."""
    intent = request["intent"]
    column = request["column"]
    value = request["value"]
    start_date = request["start_date"]
    end_date = request["end_date"]
    weekday = request["weekday"]

    if intent == "dates_for_value":
        variants = _map_query_value(value, column, config) or [value]
        all_dates = []
        for variant in variants:
            all_dates += get_dates_for_array_value(conn, column, variant)
        dates = sorted(set(all_dates))
        if start_date and end_date:
            dates = [d for d in dates if start_date <= d <= end_date]
        range_part = f" ({start_date} to {end_date})" if start_date and end_date else ""
        return f"Dates associated with {column} '{value}'{range_part}:\n{_render_date_list(dates)}"

    if intent == "top_values":
        rows = get_top_values(conn, column, start_date, end_date, limit=request["limit"])
        return f"Top {column} ({start_date} to {end_date}):\n{_render_kv_table(rows)}"

    if intent == "mood_timeseries":
        series = get_mood_timeseries(conn, start_date, end_date)
        lines = [f"- {d.strftime('%Y-%m-%d')}: {m}" for d, m in series]
        return f"Mood over time ({start_date} to {end_date}):\n" + ("\n".join(lines) if lines else "(empty)")

    if intent == "mood_distribution_by_weekday":
        dist = get_mood_distribution_by_weekday(conn, weekday)
        day_name = _WEEKDAY_DISPLAY.get(weekday, str(weekday))
        return f"Mood distribution on {day_name}:\n{_render_kv_table(dist)}"

    return None


def _execute_query_files(request: dict, config: dict) -> str | None:
    """Execute a normalized analytics request against loaded summary files."""
    summaries = load_daily_summaries_from_files(config)
    if not summaries:
        return "No daily summaries are available for analytics."

    intent = request["intent"]
    column = request["column"]
    value = request["value"]
    start_date = request["start_date"]
    end_date = request["end_date"]
    weekday = request["weekday"]

    if intent == "dates_for_value":
        variants = _map_query_value(value, column, config) or [value]
        variants_lower = {v.lower() for v in variants}
        dates = sorted(
            [
                summary["date"]
                for summary in summaries
                if any(item.lower() in variants_lower for item in (summary.get(column) or []))
            ]
        )
        if start_date and end_date:
            dates = [d for d in dates if start_date <= d <= end_date]
        range_part = f" ({start_date} to {end_date})" if start_date and end_date else ""
        return f"Dates associated with {column} '{value}'{range_part}:\n{_render_date_list(dates)}"

    if intent == "top_values":
        window = [summary for summary in summaries if start_date <= summary["date"] <= end_date]
        counts = {}
        for summary in window:
            for item in (summary.get(column) or []):
                if item:
                    counts[item] = counts.get(item, 0) + 1
        rows = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:request["limit"]]
        return f"Top {column} ({start_date} to {end_date}):\n{_render_kv_table(rows)}"

    if intent == "mood_timeseries":
        series = sorted(
            [summary for summary in summaries if start_date <= summary["date"] <= end_date],
            key=lambda x: x["date"]
        )
        lines = [f"- {summary['date'].strftime('%Y-%m-%d')}: {summary.get('mood') or '(none)'}" for summary in series]
        return f"Mood over time ({start_date} to {end_date}):\n" + ("\n".join(lines) if lines else "(empty)")

    if intent == "mood_distribution_by_weekday":
        counts = {}
        for summary in summaries:
            if summary.get("weekday") != weekday:
                continue
            mood = summary.get("mood") or "(none)"
            counts[mood] = counts.get(mood, 0) + 1
        dist = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        day_name = _WEEKDAY_DISPLAY.get(weekday, str(weekday))
        return f"Mood distribution on {day_name}:\n{_render_kv_table(dist)}"

    return None


def query_analytics(request: dict) -> str:
    """Run a structured analytics request against the analytics lane."""
    try:
        normalized = _validate_request(request)
    except ValueError as exc:
        return f"Invalid analytics query: {exc}\n{_SCHEMA_HELP}"

    config = load_memory_config()
    if not isinstance(config, dict):
        config = {}

    try:
        if _try_sync_db(config):
            conn = db_helper.get_db_connection()
            try:
                ensure_schema(conn)
                answer = _execute_query_db(normalized, config, conn)
                if answer:
                    return answer
            finally:
                conn.close()
    except Exception:
        pass

    answer = _execute_query_files(normalized, config)
    if answer:
        return answer

    return "No analytics result was produced for the provided structured query."


def main():
    """CLI entrypoint for structured analytics execution."""
    if len(sys.argv) != 2:
        print(f"Usage: python3 query_analytics.py '<json_object>'\n{_SCHEMA_HELP}")
        sys.exit(1)

    try:
        request = json.loads(sys.argv[1])
    except Exception as exc:
        print(f"Invalid analytics JSON payload: {exc}\n{_SCHEMA_HELP}")
        sys.exit(1)

    print(query_analytics(request))


if __name__ == "__main__":
    main()
