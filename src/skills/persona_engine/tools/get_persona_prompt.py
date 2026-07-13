import json
import os
import sys

metadata = {
  "name": "persona_get_prompt",
  "description": (
    "Load a persona pack from personas/<name> and return the combined startup prompt "
    "assembled from IDENTITY.md, SOUL.md, and USER.md. If persona_name is omitted, "
    "the tool falls back to the configured --default-persona. Use only at session "
    "bootstrap or explicit persona selection time, not for memory recall."
  )
}


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
from persona_util.persona_loader import build_persona_prompt, resolve_requested_persona, validate_persona_dir


async def handler(persona_name: str = None) -> str:
  """Return the assembled startup prompt for a validated persona.
  
  Args:
    persona_name: Optional explicit persona folder name. If omitted, the tool uses
      the configured startup default persona.

  Returns:
    JSON object with:
    - status: ok|error
    - persona_name: resolved persona folder name
    - persona_path: absolute folder path
    - prompt: combined startup prompt text
  """
  try:
    selected_persona = resolve_requested_persona(persona_name)
    persona_info = validate_persona_dir(selected_persona)
    return json.dumps({
      "status": "ok",
      "persona_name": persona_info["name"],
      "persona_path": persona_info["path"],
      "prompt": build_persona_prompt(selected_persona),
    })
  except Exception as error:
    return json.dumps({
      "status": "error",
      "message": f"Failed to load persona prompt: {str(error)}",
    })
