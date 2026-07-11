import os
import re
from pathlib import Path


REQUIRED_PERSONA_FILES = (
  "IDENTITY.md",
  "SOUL.md",
  "USER.md",
)


def get_project_root():
  """Return the repository root for the current workspace."""
  return Path(__file__).resolve().parents[5]


def get_personas_dir():
  """Return the persona base directory, allowing env override."""
  env_personas_dir = os.environ.get("NOUVA_PERSONAS_DIR", "").strip()
  if env_personas_dir:
    return Path(env_personas_dir).expanduser().resolve()
  return get_project_root() / "personas"


def get_default_persona_name():
  """Return the configured default persona name, or None when disabled."""
  default_persona = os.environ.get("NOUVA_DEFAULT_PERSONA", "").strip()
  return default_persona or None


def normalize_persona_name(persona_name):
  """Normalize persona names into a safe folder token."""
  normalized_name = re.sub(r"[^a-zA-Z0-9_-]", "", (persona_name or "").strip())
  if not normalized_name:
    raise ValueError("Persona name must be a non-empty folder name.")
  return normalized_name


def get_persona_dir(persona_name):
  """Resolve a persona folder path from its name."""
  return get_personas_dir() / normalize_persona_name(persona_name)


def read_markdown(file_path):
  """Read a markdown file using UTF-8 text mode."""
  with open(file_path, "r", encoding="utf-8") as handle:
    return handle.read().strip()


def validate_persona_dir(persona_name):
  """Validate that a persona folder exists and contains all required files."""
  normalized_name = normalize_persona_name(persona_name)
  persona_dir = get_persona_dir(normalized_name)
  if not persona_dir.exists() or not persona_dir.is_dir():
    raise ValueError(f"Persona folder '{normalized_name}' does not exist in {get_personas_dir()}.")

  missing_files = [
    required_file
    for required_file in REQUIRED_PERSONA_FILES
    if not (persona_dir / required_file).is_file()
  ]
  if missing_files:
    raise ValueError(
      f"Persona '{normalized_name}' is invalid. Missing required files: {', '.join(missing_files)}."
    )

  return {
    "name": normalized_name,
    "path": str(persona_dir),
    "files": {required_file: str(persona_dir / required_file) for required_file in REQUIRED_PERSONA_FILES},
  }


def list_persona_statuses():
  """List persona folders and report whether each one is structurally valid."""
  personas_dir = get_personas_dir()
  if not personas_dir.exists():
    return []

  statuses = []
  for persona_dir in sorted(personas_dir.iterdir()):
    if not persona_dir.is_dir():
      continue

    missing_files = [
      required_file
      for required_file in REQUIRED_PERSONA_FILES
      if not (persona_dir / required_file).is_file()
    ]
    statuses.append({
      "name": persona_dir.name,
      "path": str(persona_dir),
      "is_valid": len(missing_files) == 0,
      "missing_files": missing_files,
    })

  return statuses


def build_persona_prompt(persona_name):
  """Assemble the startup prompt for a validated persona folder."""
  persona_info = validate_persona_dir(persona_name)
  identity_text = read_markdown(persona_info["files"]["IDENTITY.md"])
  soul_text = read_markdown(persona_info["files"]["SOUL.md"])
  user_text = read_markdown(persona_info["files"]["USER.md"])

  return "\n\n".join([
    f"# Persona Bootstrap: {persona_info['name']}",
    "## Assistant Identity",
    identity_text,
    "## Persona Soul",
    soul_text,
    "## User Context",
    user_text,
  ]).strip()


def resolve_requested_persona(persona_name=None):
  """Resolve an explicit persona, or fall back to the configured default."""
  if persona_name and persona_name.strip():
    return normalize_persona_name(persona_name)

  default_persona_name = get_default_persona_name()
  if default_persona_name:
    return normalize_persona_name(default_persona_name)

  raise ValueError(
    "No persona selected. Pass 'persona_name' explicitly or configure --default-persona at server startup."
  )
