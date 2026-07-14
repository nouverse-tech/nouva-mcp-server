import datetime
import json
import os
import re
import uuid

from memory_util.memory_load_config import load_memory_config, resolve_paths


def load_active_memory_dir():
  """Load the active writable memory directory from config."""
  config = load_memory_config()
  active_dir, _ = resolve_paths(config)
  return active_dir


def get_session_registry_path(memory_dir):
  """Return the session registry path stored inside active memory."""
  return os.path.join(memory_dir, "_session_registry.json")


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
  return display_timestamp, iso_timestamp, now


def get_today_utc_date():
  """Return today's UTC date in YYYY-MM-DD format."""
  return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def get_unique_hhmm_filename(memory_dir, date_str, now_dt):
  """Generate a unique filename using HHMM format.
  
  If the file YYYY-MM-DD-HHMM.md already exists, it increments the minute
  until a free filename is found.
  """
  # Ambil HH dan MM awal dari now_dt
  current_time = now_dt
  while True:
    hhmm = current_time.strftime("%H%M")
    filename = f"{date_str}-{hhmm}.md"
    file_path = os.path.join(memory_dir, filename)
    if not os.path.exists(file_path):
      return filename
    # Jika bentrok, tambahkan 1 menit
    current_time += datetime.timedelta(minutes=1)


def validate_turns(turns):
  """Validate and normalize the turns list.

  Each turn must be an object with 'role' ('user' or 'assistant') and 'text' (non-empty string).
  Returns the validated list.
  """
  if not isinstance(turns, list) or not turns:
    raise ValueError("'turns' is required and must be a non-empty list.")

  for index, turn in enumerate(turns):
    if not isinstance(turn, dict):
      raise ValueError(f"turns[{index}] must be an object with 'role' and 'text'.")

    role = turn.get("role", "")
    if role not in ("user", "assistant"):
      raise ValueError(f"turns[{index}].role must be 'user' or 'assistant', got '{role}'.")

    text = turn.get("text", "")
    if not isinstance(text, str) or not text.strip():
      raise ValueError(f"turns[{index}].text must be a non-empty string.")

  return turns


def render_turns_body(turns):
  """Render validated turns into the raw transcript body format.

  Output format:
    user: <text>
    assistant: <text>

    user: <text>
    assistant: <text>
  """
  blocks = []
  for turn in turns:
    role = turn["role"]
    text = turn["text"].strip()
    blocks.append(f"{role}: {text}")

  return "\n\n".join(blocks)


def build_transcript_header(now_utc_str, transcript_day, session_key, stable_session_id, source):
  """Render the standard transcript file header."""
  return (
    f"# Session: {now_utc_str}\n"
    f"Parent Day: [[{transcript_day}]]\n\n"
    f"- **Session Key**: {session_key}\n"
    f"- **Session ID**: {stable_session_id}\n"
    f"- **Source**: {source}\n\n"
  )


def resolve_file_path(memory_dir, filename):
  """Resolve a transcript filename within active memory and prevent traversal."""
  file_path = os.path.join(memory_dir, filename)
  if not os.path.abspath(file_path).startswith(os.path.abspath(memory_dir)):
    raise ValueError("Invalid file path resolved from registry.")
  return file_path


def write_batch_session(
  memory_dir,
  session_registry,
  turns,
  session_key=None,
  source=None,
  timestamp_utc=None,
  parent_day=None
):
  """Write a full conversation as a new session transcript file.

  This is a batch/manual operation: it always creates a new transcript file
  with all turns written at once. No append, no auto-write, no incremental logic.

  Args:
    memory_dir: Active memory directory path.
    session_registry: The loaded session registry dict.
    turns: List of turn objects [{"role": "user"|"assistant", "text": "..."}].
    session_key: Session key string (e.g. agent:main:zed:direct:gadingnst).
    source: Source platform string (e.g. 'zed', 'whatsapp').
    timestamp_utc: Optional display timestamp override.
    parent_day: Optional date string YYYY-MM-DD. Defaults to today UTC.

  Returns:
    dict with status, message, filename, stable_session_id, session_key, turn_count.
  """
  validated_turns = validate_turns(turns)
  now_utc_str, now_iso, now_dt = build_now_utc_strings(timestamp_utc)
  transcript_day = parent_day if parent_day else get_today_utc_date()
  resolved_session_id = str(uuid.uuid4())
  resolved_session_key = session_key if session_key else "agent:main:unknown:direct:unknown"
  resolved_source = source if source else "unknown"

  # Generate unique HHMM filename
  filename = get_unique_hhmm_filename(memory_dir, transcript_day, now_dt)

  # Build file content
  header = build_transcript_header(
    now_utc_str, transcript_day, resolved_session_key, resolved_session_id, resolved_source
  )
  body = render_turns_body(validated_turns)

  # Write file
  file_path = resolve_file_path(memory_dir, filename)
  with open(file_path, "w", encoding="utf-8") as file:
    file.write(header + body)

  # Update registry
  entry = {
    "filename": filename,
    "parent_day": transcript_day,
    "session_key": resolved_session_key,
    "source": resolved_source,
    "session_timestamp_utc": now_utc_str,
    "turn_count": len(validated_turns),
    "created_at": now_iso
  }
  session_registry[resolved_session_id] = entry
  save_session_registry(memory_dir, session_registry)

  return {
    "status": "ok",
    "message": f"Created transcript: {filename}",
    "filename": filename,
    "stable_session_id": resolved_session_id,
    "session_key": resolved_session_key,
    "turn_count": len(validated_turns)
  }
