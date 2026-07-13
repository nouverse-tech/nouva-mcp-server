import os
import sys
import json

metadata = {
  "name": "session_write",
  "description": (
    "Create or append to a session transcript file in active memory using a strict "
    "stable_session_id-based contract. Use mode='create' exactly once for the first "
    "user turn of a chat session, then use mode='append' for all later turns with the "
    "same stable_session_id. The tool stores an active registry so append never guesses "
    "by latest file. Each write stores a raw transcript turn using 'user:' and "
    "'assistant:' blocks. Default auto-write mode is off: do not call this tool unless "
    "the user explicitly requested a nouva-session transcript command or the current "
    "session has already enabled auto-write. session_key MUST strictly follow "
    "agent:main:{provider}:direct:{user_identifier_from_provider} where {provider} is the "
    "host platform/app (e.g. 'zed', 'whatsapp', 'trae', 'cursor', 'claudecode') and NEVER "
    "the AI model name (like gemini, claude, etc)."
  )
}


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
from util.transcript_store import load_active_memory_dir, load_session_registry, write_session_turn


async def handler(
  mode: str,
  stable_session_id: str,
  user_message: str,
  assistant_message: str,
  session_key: str = None,
  source: str = None,
  timestamp_utc: str = None,
  parent_day: str = None
) -> str:
  """Create or append to a session transcript using stable_session_id lookup."""
  try:
    memory_dir = load_active_memory_dir()
    os.makedirs(memory_dir, exist_ok=True)
    registry = load_session_registry(memory_dir)
    result = write_session_turn(
      memory_dir=memory_dir,
      session_registry=registry,
      stable_session_id=stable_session_id,
      user_message=user_message,
      assistant_message=assistant_message,
      mode=mode,
      session_key=session_key,
      source=source,
      timestamp_utc=timestamp_utc,
      parent_day=parent_day
    )
    return json.dumps(result)
  except Exception as error:
    return json.dumps({
      "status": "error",
      "message": f"Failed to write transcript: {str(error)}"
    })
