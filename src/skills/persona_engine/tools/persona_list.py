import json
import os
import sys

metadata = {
  "name": "persona_list",
  "description": (
    "List persona folders from the personas directory and report whether each persona "
    "is structurally valid. Returns JSON with the configured default persona and a "
    "per-folder validation summary. Use before choosing a persona or validating "
    "--default-persona at startup."
  )
}


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
from persona_util.persona_loader import get_default_persona_name, get_personas_dir, list_persona_statuses


async def handler() -> str:
  """List persona folders and their validation status.
  
  Returns:
    JSON object with:
    - status: ok|error
    - personas_dir: resolved persona base directory
    - default_persona: current startup default persona or null
    - personas: list of {name, path, is_valid, missing_files}
  """
  try:
    return json.dumps({
      "status": "ok",
      "personas_dir": str(get_personas_dir()),
      "default_persona": get_default_persona_name(),
      "personas": list_persona_statuses(),
    })
  except Exception as error:
    return json.dumps({
      "status": "error",
      "message": f"Failed to list personas: {str(error)}",
    })
