import datetime
import json
import os
import re

from util.load_config import load_memory_config, resolve_paths


def load_active_memory_dir():
  """Load the active writable memory directory from config."""
  config = load_memory_config()
  active_dir, _ = resolve_paths(config)
  return active_dir


def get_session_registry_path(memory_dir):
  """Return the session registry path stored inside active memory."""
  return os.path.join(memory_dir, "_session_registry.json")


def get_logging_state_path(memory_dir):
  """Return the logging state path stored inside active memory."""
  return os.path.join(memory_dir, "_transcript_logging_state.json")


def load_json_registry(path):
  """Load a JSON object registry, returning an empty object when missing."""
  if not os.path.exists(path):
    return {}

  with open(path, "r", encoding="utf-8") as file:
    raw_data = json.load(file)

  if not isinstance(raw_data, dict):
    raise ValueError(f"Registry is invalid at '{path}'. Expected a JSON object.")

  return raw_data


def save_json_registry(path, registry):
  """Persist a JSON object registry atomically."""
  temp_path = f"{path}.tmp"
  with open(temp_path, "w", encoding="utf-8") as file:
    json.dump(registry, file, indent=2, ensure_ascii=True, sort_keys=True)
  os.replace(temp_path, path)


def load_session_registry(memory_dir):
  """Load the persisted active transcript registry."""
  return load_json_registry(get_session_registry_path(memory_dir))


def save_session_registry(memory_dir, registry):
  """Persist the active transcript registry atomically."""
  save_json_registry(get_session_registry_path(memory_dir), registry)


def load_logging_state(memory_dir):
  """Load the persisted per-session transcript logging preferences."""
  return load_json_registry(get_logging_state_path(memory_dir))


def save_logging_state(memory_dir, registry):
  """Persist the per-session transcript logging preferences atomically."""
  save_json_registry(get_logging_state_path(memory_dir), registry)


def require_non_empty_string(value, field_name):
  """Validate that a required input is a non-empty string."""
  if not isinstance(value, str) or not value.strip():
    raise ValueError(f"'{field_name}' is required and must be a non-empty string.")
  return value.strip()


def build_now_utc_strings(timestamp_utc=None):
  """Return display and ISO timestamps for the current write operation."""
  now = datetime.datetime.now(datetime.timezone.utc)
  display_timestamp = timestamp_utc or now.strftime("%Y-%m-%d %H:%M:%S UTC")
  iso_timestamp = now.isoformat()
  return display_timestamp, iso_timestamp


def get_today_utc_date():
  """Return today's UTC date in YYYY-MM-DD format."""
  return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def get_next_session_id(memory_dir, date_str):
  """Find the next sequential session ID for the given date."""
  pattern = re.compile(rf"^{re.escape(date_str)}-(\d{{4}})\.md$")
  max_id = 0

  if os.path.exists(memory_dir):
    for file_name in os.listdir(memory_dir):
      match = pattern.match(file_name)
      if match:
        file_id = int(match.group(1))
        if file_id > max_id:
          max_id = file_id

  return max_id + 1


def render_turn_block(user_message, assistant_message):
  """Render one transcript turn using the raw archive-style format."""
  normalized_user_message = require_non_empty_string(user_message, "user_message")
  normalized_assistant_message = require_non_empty_string(assistant_message, "assistant_message")
  return (
    f"user: {normalized_user_message}\n"
    f"assistant: {normalized_assistant_message}"
  )


def render_turn_blocks(turns):
  """Render multiple transcript turns into a single document body."""
  if not isinstance(turns, list) or not turns:
    raise ValueError("'turns' is required and must be a non-empty list.")

  rendered_turns = []
  for index, turn in enumerate(turns, start=1):
    if not isinstance(turn, dict):
      raise ValueError(f"'turns[{index}]' must be an object.")
    rendered_turns.append(
      render_turn_block(
        turn.get("user_message"),
        turn.get("assistant_message")
      )
    )
  return "\n\n".join(rendered_turns)


def build_transcript_header(now_utc_str, transcript_day, session_key, stable_session_id, source):
  """Render the standard transcript file header."""
  normalized_day = require_non_empty_string(transcript_day, "parent_day")
  normalized_session_key = require_non_empty_string(session_key, "session_key")
  normalized_session_id = require_non_empty_string(stable_session_id, "stable_session_id")
  normalized_source = require_non_empty_string(source, "source")
  return (
    f"# Session: {now_utc_str}\n"
    f"Parent Day: [[{normalized_day}]]\n\n"
    f"- **Session Key**: {normalized_session_key}\n"
    f"- **Session ID**: {normalized_session_id}\n"
    f"- **Source**: {normalized_source}\n\n"
  )


def read_existing_header_timestamp(file_path):
  """Read the persisted '# Session:' header timestamp from an existing transcript."""
  if not os.path.exists(file_path):
    return None

  with open(file_path, "r", encoding="utf-8") as file:
    first_line = file.readline().strip()

  if first_line.startswith("# Session: "):
    return first_line[len("# Session: "):].strip()

  return None


def resolve_file_path(memory_dir, filename):
  """Resolve a transcript filename within active memory and prevent traversal."""
  normalized_filename = require_non_empty_string(filename, "filename")
  file_path = os.path.join(memory_dir, normalized_filename)
  if not os.path.abspath(file_path).startswith(os.path.abspath(memory_dir)):
    raise ValueError("Invalid file path resolved from registry.")
  return file_path


def create_session_entry(memory_dir, session_registry, stable_session_id, session_key, source, parent_day, now_iso,
                         session_timestamp_utc):
  """Create a new session registry entry and return its metadata."""
  normalized_session_id = require_non_empty_string(stable_session_id, "stable_session_id")
  if session_registry.get(normalized_session_id):
    raise ValueError(
      f"Transcript already exists for stable_session_id '{normalized_session_id}'. "
      "Use append or full-session sync for subsequent writes."
    )

  transcript_day = require_non_empty_string(parent_day, "parent_day")
  session_id = get_next_session_id(memory_dir, transcript_day)
  filename = f"{transcript_day}-{session_id:04d}.md"
  entry = {
    "filename": filename,
    "parent_day": transcript_day,
    "session_key": require_non_empty_string(session_key, "session_key"),
    "source": require_non_empty_string(source, "source"),
    "session_timestamp_utc": require_non_empty_string(session_timestamp_utc, "session_timestamp_utc"),
    "created_at": now_iso,
    "updated_at": now_iso
  }
  session_registry[normalized_session_id] = entry
  return entry, f"{session_id:04d}"


def get_existing_session_entry(session_registry, stable_session_id):
  """Return the existing session registry entry or None."""
  normalized_session_id = require_non_empty_string(stable_session_id, "stable_session_id")
  return session_registry.get(normalized_session_id)


def write_session_turn(memory_dir, session_registry, stable_session_id, user_message, assistant_message,
                       mode, session_key=None, source=None, timestamp_utc=None, parent_day=None):
  """Create or append exactly one transcript turn for a session."""
  normalized_mode = require_non_empty_string(mode, "mode")
  normalized_session_id = require_non_empty_string(stable_session_id, "stable_session_id")
  now_utc_str, now_iso = build_now_utc_strings(timestamp_utc)
  transcript_day = require_non_empty_string(parent_day, "parent_day") if parent_day else get_today_utc_date()
  turn_block = render_turn_block(user_message, assistant_message)

  if normalized_mode == "create":
    entry, session_id = create_session_entry(
      memory_dir,
      session_registry,
      normalized_session_id,
      session_key,
      source,
      transcript_day,
      now_iso,
      now_utc_str
    )
    header = build_transcript_header(
      entry["session_timestamp_utc"],
      entry["parent_day"],
      entry["session_key"],
      normalized_session_id,
      entry["source"]
    )
    file_path = resolve_file_path(memory_dir, entry["filename"])
    with open(file_path, "w", encoding="utf-8") as file:
      file.write(header + turn_block)
    save_session_registry(memory_dir, session_registry)
    return {
      "status": "ok",
      "message": f"Created transcript: {entry['filename']}",
      "filename": entry["filename"],
      "session_id": session_id,
      "stable_session_id": normalized_session_id,
      "session_key": entry["session_key"]
    }

  if normalized_mode == "append":
    entry = get_existing_session_entry(session_registry, normalized_session_id)
    if not entry:
      return {
        "status": "error",
        "message": (
          f"No active transcript found for stable_session_id '{normalized_session_id}'. "
          "Use mode='create' on the first user turn of the session."
        ),
        "stable_session_id": normalized_session_id
      }

    file_path = resolve_file_path(memory_dir, entry.get("filename"))
    if not os.path.exists(file_path):
      return {
        "status": "error",
        "message": (
          f"Registry points to missing transcript '{entry.get('filename')}' for "
          f"stable_session_id '{normalized_session_id}'."
        ),
        "stable_session_id": normalized_session_id,
        "filename": entry.get("filename")
      }

    with open(file_path, "a", encoding="utf-8") as file:
      file.write("\n\n" + turn_block)

    entry["updated_at"] = now_iso
    save_session_registry(memory_dir, session_registry)
    return {
      "status": "ok",
      "message": f"Appended to transcript: {entry['filename']}",
      "filename": entry["filename"],
      "stable_session_id": normalized_session_id
    }

  return {
    "status": "error",
    "message": "Invalid mode. Use 'create' or 'append'."
  }


def sync_full_session_transcript(memory_dir, session_registry, stable_session_id, turns, session_key=None,
                                 source=None, timestamp_utc=None, parent_day=None):
  """Create or rewrite a full transcript file from the complete session turn list."""
  normalized_session_id = require_non_empty_string(stable_session_id, "stable_session_id")
  now_utc_str, now_iso = build_now_utc_strings(timestamp_utc)
  transcript_day = require_non_empty_string(parent_day, "parent_day") if parent_day else get_today_utc_date()
  body = render_turn_blocks(turns)
  entry = get_existing_session_entry(session_registry, normalized_session_id)

  if entry:
    entry["updated_at"] = now_iso
    if session_key:
      entry["session_key"] = require_non_empty_string(session_key, "session_key")
    if source:
      entry["source"] = require_non_empty_string(source, "source")
    if parent_day:
      existing_parent_day = require_non_empty_string(entry["parent_day"], "registry.parent_day")
      if transcript_day != existing_parent_day:
        return {
          "status": "error",
          "message": (
            f"Cannot change parent_day for existing stable_session_id '{normalized_session_id}' "
            f"from '{existing_parent_day}' to '{transcript_day}'. Create a new session instead."
          ),
          "stable_session_id": normalized_session_id,
          "filename": entry.get("filename")
        }
  else:
    entry, _ = create_session_entry(
      memory_dir,
      session_registry,
      normalized_session_id,
      session_key,
      source,
      transcript_day,
      now_iso,
      now_utc_str
    )

  file_path = resolve_file_path(memory_dir, entry["filename"])
  session_header_timestamp = entry.get("session_timestamp_utc")
  if not session_header_timestamp:
    session_header_timestamp = read_existing_header_timestamp(file_path) or now_utc_str
    entry["session_timestamp_utc"] = session_header_timestamp
  header = build_transcript_header(
    session_header_timestamp,
    entry["parent_day"],
    entry["session_key"],
    normalized_session_id,
    entry["source"]
  )
  with open(file_path, "w", encoding="utf-8") as file:
    file.write(header + body)

  save_session_registry(memory_dir, session_registry)
  return {
    "status": "ok",
    "message": f"Synchronized transcript: {entry['filename']}",
    "filename": entry["filename"],
    "stable_session_id": normalized_session_id,
    "session_key": entry["session_key"],
    "turn_count": len(turns)
  }


def set_auto_write_state(memory_dir, stable_session_id, enabled, session_key=None, source=None):
  """Enable or disable transcript auto-write for a session."""
  normalized_session_id = require_non_empty_string(stable_session_id, "stable_session_id")
  logging_state = load_logging_state(memory_dir)
  _, now_iso = build_now_utc_strings()
  entry = logging_state.get(normalized_session_id, {})
  entry["auto_write_enabled"] = bool(enabled)
  entry["updated_at"] = now_iso
  if session_key:
    entry["session_key"] = require_non_empty_string(session_key, "session_key")
  if source:
    entry["source"] = require_non_empty_string(source, "source")
  logging_state[normalized_session_id] = entry
  save_logging_state(memory_dir, logging_state)
  return {
    "stable_session_id": normalized_session_id,
    "auto_write_enabled": entry["auto_write_enabled"],
    "session_key": entry.get("session_key"),
    "source": entry.get("source"),
    "updated_at": entry["updated_at"]
  }


def get_auto_write_state(memory_dir, stable_session_id):
  """Return transcript auto-write state for a session."""
  normalized_session_id = require_non_empty_string(stable_session_id, "stable_session_id")
  logging_state = load_logging_state(memory_dir)
  entry = logging_state.get(normalized_session_id, {})
  return {
    "stable_session_id": normalized_session_id,
    "auto_write_enabled": bool(entry.get("auto_write_enabled", False)),
    "session_key": entry.get("session_key"),
    "source": entry.get("source"),
    "updated_at": entry.get("updated_at")
  }
