import json
import os
import sys

metadata = {
  "name": "session_manage",
  "description": (
    "Handle transcript logging commands for one chat session. Supported commands map to "
    "slash commands such as /nouva-session-auto-on, /nouva-session-auto-off, "
    "/nouva-session-status, and /nouva-session-write. The write command "
    "accepts a full session transcript snapshot as JSON and writes or rewrites the "
    "session file in raw 'user:'/'assistant:' format. Default auto-write mode is off. "
    "Use this tool to route explicit nouva-session commands and to decide whether "
    "per-turn transcript writes should remain disabled or enabled for the session."
  )
}


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../memory_scripts")))
from memory_util.memory_transcript_store import (
  get_auto_write_state,
  load_active_memory_dir,
  load_session_registry,
  require_non_empty_string,
  set_auto_write_state,
  sync_full_session_transcript,
)


SUPPORTED_COMMANDS = {
  "nouva-session-auto-on",
  "nouva-session-auto-off",
  "nouva-session-status",
  "nouva-session-write",
}


def normalize_command(command):
  """Normalize slash command input into the canonical command token."""
  normalized_command = require_non_empty_string(command, "command").lower()
  return normalized_command[1:] if normalized_command.startswith("/") else normalized_command


def parse_turns_json(turns_json):
  """Parse the full-session transcript JSON payload."""
  normalized_turns_json = require_non_empty_string(turns_json, "turns_json")
  try:
    turns = json.loads(normalized_turns_json)
  except json.JSONDecodeError as error:
    raise ValueError(f"'turns_json' must be valid JSON. {str(error)}") from error

  if not isinstance(turns, list):
    raise ValueError("'turns_json' must decode into a list of turn objects.")

  return turns


async def handler(
  command: str,
  stable_session_id: str,
  turns_json: str = None,
  session_key: str = None,
  source: str = None,
  timestamp_utc: str = None,
  parent_day: str = None
) -> str:
  """Handle transcript session commands such as auto on/off/status and full-session write."""
  try:
    normalized_command = normalize_command(command)
    if normalized_command not in SUPPORTED_COMMANDS:
      return json.dumps({
        "status": "error",
        "message": (
          "Unsupported command. Use one of: /nouva-session-auto-on, "
          "/nouva-session-auto-off, /nouva-session-status, /nouva-session-write."
        )
      })

    memory_dir = load_active_memory_dir()
    os.makedirs(memory_dir, exist_ok=True)

    if normalized_command == "nouva-session-auto-on":
      state = set_auto_write_state(
        memory_dir=memory_dir,
        stable_session_id=stable_session_id,
        enabled=True,
        session_key=session_key,
        source=source
      )
      return json.dumps({
        "status": "ok",
        "message": "Auto transcript write enabled for this session.",
        "command": normalized_command,
        **state
      })

    if normalized_command == "nouva-session-auto-off":
      state = set_auto_write_state(
        memory_dir=memory_dir,
        stable_session_id=stable_session_id,
        enabled=False,
        session_key=session_key,
        source=source
      )
      return json.dumps({
        "status": "ok",
        "message": "Auto transcript write disabled for this session.",
        "command": normalized_command,
        **state
      })

    if normalized_command == "nouva-session-status":
      state = get_auto_write_state(memory_dir, stable_session_id)
      return json.dumps({
        "status": "ok",
        "message": "Transcript logging session status retrieved.",
        "command": normalized_command,
        **state
      })

    turns = parse_turns_json(turns_json)
    session_registry = load_session_registry(memory_dir)
    result = sync_full_session_transcript(
      memory_dir=memory_dir,
      session_registry=session_registry,
      stable_session_id=stable_session_id,
      turns=turns,
      session_key=session_key,
      source=source,
      timestamp_utc=timestamp_utc,
      parent_day=parent_day
    )
    state = get_auto_write_state(memory_dir, stable_session_id)
    return json.dumps({
      **result,
      "command": normalized_command,
      "auto_write_enabled": state["auto_write_enabled"]
    })
  except Exception as error:
    return json.dumps({
      "status": "error",
      "message": f"Failed to manage transcript session: {str(error)}"
    })
