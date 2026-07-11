import os
import sys
import re
import datetime

sys.path.insert(0, os.path.dirname(__file__))

from db import db_helper
from util.load_config import load_memory_config
from util.llm_client import call_chat_completions, extract_json_object
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

_PROJECT_PATTERNS = [
    r"(?:which|what)\s+days\s+(?:did\s+we\s+)?(?:work|worked)\s+on\s+(?:the\s+)?project\s+(.+?)(?:\?|$)",
    r"on\s+which\s+days\s+(?:did\s+we\s+)?(?:work|worked)\s+on\s+(?:the\s+)?project\s+(.+?)(?:\?|$)",
]

_WEEKDAY_PATTERNS = [
    r"(?:every|each)\s+([a-z]+)",
]


def _parse_iso_date(value: str) -> datetime.date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _normalize_array_column(value: str) -> str | None:
    if not value or not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in ["projects", "project"]:
        return "projects"
    if v in ["tags", "tag", "topics", "topic"]:
        return "tags"
    if v in ["people", "person", "persons", "personas"]:
        return "people"
    if v in ["technologies", "technology", "tech", "stack"]:
        return "technologies"
    return None


def _llm_parse_analytics_question(question: str, config: dict) -> dict | None:
    today = datetime.date.today().strftime("%Y-%m-%d")
    prompt = f"""
You convert a user's analytics question about daily summaries into a STRICT JSON object only.

Reference date (today): {today}

Supported intents (choose exactly one):
- "dates_for_value": find which dates contain a value in an array column.
  Required: column, value. Optional: start_date, end_date.
- "top_values": top values in an array column within a date range.
  Required: column. Optional: start_date, end_date, limit.
- "mood_timeseries": mood over time.
  Required: start_date, end_date.
- "mood_distribution_by_weekday": mood distribution for a weekday.
  Required: weekday (0=Monday .. 6=Sunday) OR weekday_name ("monday".."sunday").

Output schema:
{{
  "intent": "dates_for_value|top_values|mood_timeseries|mood_distribution_by_weekday|unknown",
  "column": "projects|tags|people|technologies|null",
  "value": "string|null",
  "start_date": "YYYY-MM-DD|null",
  "end_date": "YYYY-MM-DD|null",
  "weekday": 0-6|null,
  "weekday_name": "monday|tuesday|...|sunday|null",
  "limit": 1-50|null,
  "reason": "string|null"
}}

Date interpretation rules (Indonesian + English):
- "3 hari yang lalu" / "3 days ago": that exact date (start_date=end_date).
- "2 bulan yang lalu" / "2 months ago": the CALENDAR month N months before the current month (start=1st, end=last day).
- "bulan Mei" / "May": choose the most recent such month not in the future relative to today.
- "bulan Mei 2025" / "May 2025": that calendar month (start=2025-05-01, end=2025-05-31).
- "2 minggu terakhir" / "last 2 weeks": inclusive range of 14 days (end=today, start=today-13).
- "antara X dan Y" / "between X and Y" / "dari X sampai Y": exact inclusive range.
- If no date range is provided:
  - dates_for_value: keep start_date/end_date as null.
  - top_values: default to last 30 days (end=today, start=today-29).

Column inference hints:
- projects: project names
- technologies: tech stack, tools, frameworks
- tags: discussion topics
- people: names

Return "unknown" if you cannot confidently map the question to the supported intents.

Question: {question}
""".strip()

    content = call_chat_completions([{"role": "user", "content": prompt}], config, temperature=0.1, timeout_s=60)
    parsed = extract_json_object(content or "")
    return parsed if isinstance(parsed, dict) else None


def _map_query_value(value: str, category: str, config: dict) -> list[str]:
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


def _previous_month_range(today: datetime.date) -> tuple[datetime.date, datetime.date]:
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - datetime.timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    return first_of_prev_month, last_of_prev_month


def _render_date_list(dates: list[datetime.date]) -> str:
    if not dates:
        return "(empty)"
    return "\n".join([f"- {d.strftime('%Y-%m-%d')}" for d in dates])


def _render_kv_table(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "(empty)"
    return "\n".join([f"- {k}: {v}" for k, v in rows])


def _extract_first_match(patterns: list[str], text: str) -> re.Match | None:
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m
    return None


def _extract_project_from_question(question: str, question_lower: str) -> str | None:
    m = _extract_first_match(_PROJECT_PATTERNS, question_lower)
    if not m:
        return None
    return question[m.start(1):m.end(1)].strip().strip('"').strip("'")


def _extract_weekday_from_question(question_lower: str) -> int | None:
    m = _extract_first_match(_WEEKDAY_PATTERNS, question_lower)
    if not m:
        return None
    return _WEEKDAY_MAP.get(m.group(1))


def _is_last_two_weeks_question(question_lower: str) -> bool:
    return any(
        k in question_lower
        for k in [
            "2 weeks",
            "two weeks",
            "last 2 weeks",
            "past 2 weeks",
            "previous 2 weeks",
        ]
    )


def _is_last_month_question(question_lower: str) -> bool:
    return any(
        k in question_lower
        for k in [
            "last month",
            "previous month",
        ]
    )


def _try_sync_db(config: dict) -> bool:
    try:
        sync_daily_summaries_to_db(config)
        return True
    except Exception:
        return False


def _execute_parsed_query_db(parsed: dict, config: dict, conn) -> str | None:
    if not isinstance(parsed, dict):
        return None

    intent = (parsed.get("intent") or "").strip()
    if intent == "unknown" or not intent:
        return None

    column = _normalize_array_column(parsed.get("column"))
    value = parsed.get("value")
    start_date = _parse_iso_date(parsed.get("start_date"))
    end_date = _parse_iso_date(parsed.get("end_date"))

    if intent == "dates_for_value":
        if not column or not value:
            return None
        variants = _map_query_value(str(value), column, config) or [str(value).strip()]
        all_dates = []
        for v in variants:
            all_dates += get_dates_for_array_value(conn, column, v)
        dates = sorted(set(all_dates))
        if start_date and end_date:
            dates = [d for d in dates if start_date <= d <= end_date]
        range_part = f" ({start_date} to {end_date})" if start_date and end_date else ""
        return f"Dates associated with {column} '{value}'{range_part}:\n{_render_date_list(dates)}"

    if intent == "top_values":
        if not column:
            return None
        if not start_date or not end_date:
            today = datetime.date.today()
            end_date = today
            start_date = today - datetime.timedelta(days=29)
        limit = parsed.get("limit")
        try:
            limit = int(limit) if limit is not None else 20
        except Exception:
            limit = 20
        limit = max(1, min(limit, 50))
        rows = get_top_values(conn, column, start_date, end_date, limit=limit)
        return f"Top {column} ({start_date} to {end_date}):\n{_render_kv_table(rows)}"

    if intent == "mood_timeseries":
        if not start_date or not end_date:
            return None
        series = get_mood_timeseries(conn, start_date, end_date)
        lines = [f"- {d.strftime('%Y-%m-%d')}: {m}" for d, m in series]
        return f"Mood over time ({start_date} to {end_date}):\n" + ("\n".join(lines) if lines else "(empty)")

    if intent == "mood_distribution_by_weekday":
        weekday = parsed.get("weekday")
        if weekday is None:
            weekday_name = (parsed.get("weekday_name") or "").strip().lower()
            weekday = _WEEKDAY_MAP.get(weekday_name)
        try:
            weekday = int(weekday) if weekday is not None else None
        except Exception:
            weekday = None
        if weekday is None or weekday not in _WEEKDAY_DISPLAY:
            return None
        dist = get_mood_distribution_by_weekday(conn, weekday)
        day_name = _WEEKDAY_DISPLAY.get(weekday, str(weekday))
        return f"Mood distribution on {day_name}:\n{_render_kv_table(dist)}"

    return None


def _answer_from_db(question: str, config: dict) -> str | None:
    today = datetime.date.today()
    q = question.strip()
    q_lower = q.lower()

    conn = db_helper.get_db_connection()
    try:
        ensure_schema(conn)

        project = _extract_project_from_question(q, q_lower)
        if project:
            variants = _map_query_value(project, "projects", config)
            all_dates = []
            for v in variants:
                all_dates += get_dates_for_array_value(conn, "projects", v)
            dates = sorted(set(all_dates))
            return f"Dates associated with project '{project}':\n{_render_date_list(dates)}"

        weekday = _extract_weekday_from_question(q_lower)
        if weekday is not None:
            dist = get_mood_distribution_by_weekday(conn, weekday)
            day_name = _WEEKDAY_DISPLAY.get(weekday, str(weekday))
            return f"Mood distribution on {day_name}:\n{_render_kv_table(dist)}"

        if _is_last_two_weeks_question(q_lower):
            end_date = today
            start_date = today - datetime.timedelta(days=13)
            series = get_mood_timeseries(conn, start_date, end_date)
            lines = [f"- {d.strftime('%Y-%m-%d')}: {m}" for d, m in series]
            return f"Mood over the last 2 weeks ({start_date} to {end_date}):\n" + ("\n".join(lines) if lines else "(empty)")

        if _is_last_month_question(q_lower):
            start_date, end_date = _previous_month_range(today)
            top_tags = get_top_values(conn, "tags", start_date, end_date, limit=20)
            top_projects = get_top_values(conn, "projects", start_date, end_date, limit=10)
            top_tech = get_top_values(conn, "technologies", start_date, end_date, limit=10)
            parts = [
                f"Top topics (tags) last month ({start_date} to {end_date}):\n{_render_kv_table(top_tags)}",
                f"\nTop projects last month:\n{_render_kv_table(top_projects)}",
                f"\nTop technologies last month:\n{_render_kv_table(top_tech)}",
            ]
            return "\n".join(parts).strip()

        return None
    finally:
        conn.close()


def _answer_from_files(question: str, config: dict) -> str | None:
    today = datetime.date.today()
    q = question.strip()
    q_lower = q.lower()

    summaries = load_daily_summaries_from_files(config)
    if not summaries:
        return "No daily summaries are available for analytics."

    project = _extract_project_from_question(q, q_lower)
    if project:
        variants = _map_query_value(project, "projects", config)
        variants_lower = {v.lower() for v in variants}
        dates = sorted(
            [
                s["date"]
                for s in summaries
                if any(p.lower() in variants_lower for p in (s.get("projects") or []))
            ]
        )
        return f"Dates associated with project '{project}':\n{_render_date_list(dates)}"

    weekday = _extract_weekday_from_question(q_lower)
    if weekday is not None:
        counts = {}
        for s in summaries:
            if s.get("weekday") != weekday:
                continue
            mood = s.get("mood") or "(none)"
            counts[mood] = counts.get(mood, 0) + 1
        dist = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        day_name = _WEEKDAY_DISPLAY.get(weekday, str(weekday))
        return f"Mood distribution on {day_name}:\n{_render_kv_table(dist)}"

    if _is_last_two_weeks_question(q_lower):
        end_date = today
        start_date = today - datetime.timedelta(days=13)
        series = sorted([s for s in summaries if start_date <= s["date"] <= end_date], key=lambda x: x["date"])
        lines = [f"- {s['date'].strftime('%Y-%m-%d')}: {s.get('mood') or '(none)'}" for s in series]
        return f"Mood over the last 2 weeks ({start_date} to {end_date}):\n" + ("\n".join(lines) if lines else "(empty)")

    if _is_last_month_question(q_lower):
        start_date, end_date = _previous_month_range(today)
        month_summaries = [s for s in summaries if start_date <= s["date"] <= end_date]

        def top_from_key(key: str, limit: int):
            counts = {}
            for s in month_summaries:
                for v in (s.get(key) or []):
                    counts[v] = counts.get(v, 0) + 1
            return sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]

        top_tags = top_from_key("tags", 20)
        top_projects = top_from_key("projects", 10)
        top_tech = top_from_key("technologies", 10)
        parts = [
            f"Top topics (tags) last month ({start_date} to {end_date}):\n{_render_kv_table(top_tags)}",
            f"\nTop projects last month:\n{_render_kv_table(top_projects)}",
            f"\nTop technologies last month:\n{_render_kv_table(top_tech)}",
        ]
        return "\n".join(parts).strip()

    return None


def query_analytics(question: str) -> str:
    config = load_memory_config()
    if not isinstance(config, dict):
        config = {}

    try:
        synced = _try_sync_db(config)
        if synced:
            answer = _answer_from_db(question, config)
            if answer:
                return answer

            conn = db_helper.get_db_connection()
            try:
                ensure_schema(conn)
                parsed = _llm_parse_analytics_question(question, config)
                llm_answer = _execute_parsed_query_db(parsed, config, conn)
                if llm_answer:
                    return llm_answer
            finally:
                conn.close()
    except Exception:
        pass

    answer = _answer_from_files(question, config)
    if answer:
        return answer

    try:
        parsed = _llm_parse_analytics_question(question, config)
        if not isinstance(parsed, dict):
            raise ValueError("LLM parse failed")

        intent = (parsed.get("intent") or "").strip()
        if intent and intent != "unknown":
            summaries = load_daily_summaries_from_files(config)
            if summaries:
                column = _normalize_array_column(parsed.get("column"))
                value = parsed.get("value")
                start_date = _parse_iso_date(parsed.get("start_date"))
                end_date = _parse_iso_date(parsed.get("end_date"))

                if intent == "dates_for_value" and column and value:
                    variants = _map_query_value(str(value), column, config) or [str(value).strip()]
                    variants_lower = {v.lower() for v in variants}
                    dates = sorted(
                        [
                            s["date"]
                            for s in summaries
                            if any(p.lower() in variants_lower for p in (s.get(column) or []))
                        ]
                    )
                    if start_date and end_date:
                        dates = [d for d in dates if start_date <= d <= end_date]
                    range_part = f" ({start_date} to {end_date})" if start_date and end_date else ""
                    return f"Dates associated with {column} '{value}'{range_part}:\n{_render_date_list(dates)}"

                if intent == "top_values" and column:
                    if not start_date or not end_date:
                        end_date = datetime.date.today()
                        start_date = end_date - datetime.timedelta(days=29)
                    limit = parsed.get("limit")
                    try:
                        limit = int(limit) if limit is not None else 20
                    except Exception:
                        limit = 20
                    limit = max(1, min(limit, 50))
                    window = [s for s in summaries if start_date <= s["date"] <= end_date]
                    counts = {}
                    for s in window:
                        for v in (s.get(column) or []):
                            if not v:
                                continue
                            counts[v] = counts.get(v, 0) + 1
                    rows = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]
                    return f"Top {column} ({start_date} to {end_date}):\n{_render_kv_table(rows)}"

                if intent == "mood_timeseries" and start_date and end_date:
                    series = sorted([s for s in summaries if start_date <= s["date"] <= end_date], key=lambda x: x["date"])
                    lines = [f"- {s['date'].strftime('%Y-%m-%d')}: {s.get('mood') or '(none)'}" for s in series]
                    return f"Mood over time ({start_date} to {end_date}):\n" + ("\n".join(lines) if lines else "(empty)")

                if intent == "mood_distribution_by_weekday":
                    weekday = parsed.get("weekday")
                    if weekday is None:
                        weekday_name = (parsed.get("weekday_name") or "").strip().lower()
                        weekday = _WEEKDAY_MAP.get(weekday_name)
                    try:
                        weekday = int(weekday) if weekday is not None else None
                    except Exception:
                        weekday = None
                    if weekday is not None:
                        counts = {}
                        for s in summaries:
                            if s.get("weekday") != weekday:
                                continue
                            mood = s.get("mood") or "(none)"
                            counts[mood] = counts.get(mood, 0) + 1
                        dist = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
                        day_name = _WEEKDAY_DISPLAY.get(weekday, str(weekday))
                        return f"Mood distribution on {day_name}:\n{_render_kv_table(dist)}"
    except Exception:
        pass

    return (
        "Unsupported analytics question. Try formats like: "
        "'Which days did we work on project <name>?', "
        "'What is my mood distribution on every Tuesday?', "
        "'What is my mood over the last 2 weeks?', "
        "or 'What topics did I talk about most last month?'."
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 query_analytics.py \"question\"")
        sys.exit(1)
    question = " ".join(sys.argv[1:]).strip()
    print(query_analytics(question))


if __name__ == "__main__":
    main()
