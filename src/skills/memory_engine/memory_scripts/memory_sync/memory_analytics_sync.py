import os
import re
import datetime
import yaml

from memory_db import memory_db_helper as db_helper
from memory_util.memory_load_config import resolve_paths
from memory_db.memory_analytics_repo import ensure_schema, upsert_daily_summary


def _dedupe_list(values: list) -> list:
    if not isinstance(values, list):
        return []
    result = []
    seen = set()
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(s)
    return result


def _parse_frontmatter_yaml(text: str) -> dict:
    if not isinstance(text, str):
        return {}
    text = text.strip()
    if not text:
        return {}

    patterns = [
        r"^`{3,}yaml\n(.*?)\n`{3,}",
        r"^---\n(.*?)\n---",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, re.DOTALL)
        if not match:
            continue
        try:
            metadata = yaml.safe_load(match.group(1))
            if isinstance(metadata, dict):
                return metadata
        except Exception:
            return {}
    return {}


def _normalize_daily_summary(metadata: dict, summary_path: str, config: dict) -> dict | None:
    if not isinstance(metadata, dict):
        return None

    date_val = metadata.get("date")
    dt = None
    if isinstance(date_val, datetime.datetime):
        dt = date_val.date()
    elif isinstance(date_val, datetime.date):
        dt = date_val
    elif isinstance(date_val, str):
        date_str = date_val.strip()
        if not date_str:
            return None
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
    else:
        return None

    mood = metadata.get("mood")
    mood = str(mood).strip() if mood is not None else ""

    mood_taxonomy = config.get("mood_taxonomy", {}) if isinstance(config, dict) else {}
    mood_allowed = mood_taxonomy.get("allowed", []) if isinstance(mood_taxonomy, dict) else []
    mood_default = mood_taxonomy.get("default", "mixed") if isinstance(mood_taxonomy, dict) else "mixed"
    if isinstance(mood_allowed, list) and mood_allowed:
        allowed_set = {str(x).strip().lower() for x in mood_allowed if str(x).strip()}
        if mood.strip().lower() not in allowed_set:
            mood = str(mood_default).strip() if mood_default else "mixed"

    uncategorized = metadata.get("uncategorized", {}) or {}
    unc_projects = uncategorized.get("projects", []) if isinstance(uncategorized, dict) else []
    unc_tech = uncategorized.get("technologies", []) if isinstance(uncategorized, dict) else []

    projects = _dedupe_list((metadata.get("projects") or []) + (unc_projects or []))
    technologies = _dedupe_list((metadata.get("technologies") or []) + (unc_tech or []))
    tags = _dedupe_list(metadata.get("tags") or [])
    people = _dedupe_list(metadata.get("people") or [])

    importance = metadata.get("importance")
    try:
        importance_val = int(importance) if importance is not None else None
    except Exception:
        importance_val = None

    return {
        "date": dt,
        "weekday": dt.weekday(),
        "mood": mood or None,
        "projects": projects,
        "tags": tags,
        "people": people,
        "technologies": technologies,
        "importance": importance_val,
        "summary_path": summary_path,
    }


def load_daily_summaries_from_files(config: dict = None) -> list:
    if config is None:
        config = {}
    active_memory_dir, archived_memory_dir = resolve_paths(config)
    default_active_dir, default_archived_dir = resolve_paths({})

    active_summaries_dir = os.path.join(active_memory_dir, "_summaries")
    archived_summaries_dir = os.path.join(archived_memory_dir, "daily_sessions", "_summaries")
    default_active_summaries_dir = os.path.join(default_active_dir, "_summaries")
    default_archived_summaries_dir = os.path.join(default_archived_dir, "daily_sessions", "_summaries")

    summary_files = []
    if os.path.isdir(archived_summaries_dir):
        summary_files += [
            os.path.join(archived_summaries_dir, f)
            for f in os.listdir(archived_summaries_dir)
            if f.endswith(".summary.md") and not f.startswith(".")
        ]
    if os.path.isdir(active_summaries_dir):
        summary_files += [
            os.path.join(active_summaries_dir, f)
            for f in os.listdir(active_summaries_dir)
            if f.endswith(".summary.md") and not f.startswith(".")
        ]
    if not summary_files:
        if os.path.isdir(default_archived_summaries_dir):
            summary_files += [
                os.path.join(default_archived_summaries_dir, f)
                for f in os.listdir(default_archived_summaries_dir)
                if f.endswith(".summary.md") and not f.startswith(".")
            ]
        if os.path.isdir(default_active_summaries_dir):
            summary_files += [
                os.path.join(default_active_summaries_dir, f)
                for f in os.listdir(default_active_summaries_dir)
                if f.endswith(".summary.md") and not f.startswith(".")
            ]

    results = []
    for path in sorted(set(summary_files)):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            metadata = _parse_frontmatter_yaml(content)
            normalized = _normalize_daily_summary(metadata, path, config)
            if normalized:
                results.append(normalized)
        except Exception:
            continue
    return results


def sync_daily_summaries_to_db(config: dict = None) -> dict:
    if config is None:
        config = {}

    summaries = load_daily_summaries_from_files(config)
    if not summaries:
        return {"ok": True, "synced": 0}

    conn = db_helper.get_db_connection()
    try:
        ensure_schema(conn)
        for s in summaries:
            upsert_daily_summary(conn, s)
        conn.commit()
        return {"ok": True, "synced": len(summaries)}
    finally:
        conn.close()
