import json
import os
import sys

metadata = {
  "name": "session_write",
  "description": (
    "Write a full conversation transcript as a new session file in active memory. "
    "Accepts a batch of turns as JSON array with format: "
    '[{"role": "user", "text": "..."}, {"role": "assistant", "text": "..."}]. '
    "Each call creates a new .md transcript file. This is a manual-only tool: "
    "only call it when the user explicitly asks to save/record the conversation. "
    "stable_session_id is optional and auto-generated if omitted. "
    "session_key should follow the pattern agent:main:{provider}:direct:{user_id} "
    "where {provider} is the host platform (e.g. 'zed', 'whatsapp', 'cursor') "
    "and NEVER an AI model name."
  )
}


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../memory_scripts")))
from memory_util.memory_transcript_store import load_active_memory_dir, load_session_registry, write_batch_session


async def handler(
  turns_json: str,
  stable_session_id: str = None,
  session_key: str = None,
  source: str = None,
  timestamp_utc: str = None,
  parent_day: str = None
) -> str:
  """Write a full conversation as a new session transcript file."""
  try:
    # Parse turns_json
    try:
      turns = json.loads(turns_json)
    except json.JSONDecodeError as error:
      return json.dumps({
        "status": "error",
        "message": f"'turns_json' must be valid JSON: {str(error)}"
      })

    if not isinstance(turns, list):
      return json.dumps({
        "status": "error",
        "message": "'turns_json' must decode into a JSON array of turn objects."
      })

    memory_dir = load_active_memory_dir()
    os.makedirs(memory_dir, exist_ok=True)
    registry = load_session_registry(memory_dir)

    result = write_batch_session(
      memory_dir=memory_dir,
      session_registry=registry,
      turns=turns,
      stable_session_id=stable_session_id,
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
