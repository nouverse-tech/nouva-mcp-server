import os
import sys
import json
import re
import datetime
import uuid

metadata = {
    "name": "mcp_write_transcript",
    "description": (
        "Create or append to a session transcript file in active memory. "
        "Use mode='create' at the start of a new conversation to initialize a new transcript (YYYY-MM-DD-XXXX.md). "
        "Use mode='append' to log subsequent exchanges to the active transcript. "
        "On create, you can also pass session_key, stable_session_id, and source to match the archived session header format. "
        "Example session_key patterns: agent:main:{provider}:direct:{user_identifier_from_provider} (e.g. agent:main:trae:direct:gadingnst, agent:main:antigravity:direct:xxxxxx)."
    )
}


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
from util.load_config import load_memory_config, resolve_paths


def load_active_memory_dir():
    config = load_memory_config()
    active_dir, _ = resolve_paths(config)
    return active_dir


def get_next_session_id(memory_dir, date_str):
    """Find the next sequential session ID for the given date."""
    pattern = re.compile(rf"^{re.escape(date_str)}-(\d{{4}})\.md$")
    max_id = 0

    if os.path.exists(memory_dir):
        for f in os.listdir(memory_dir):
            match = pattern.match(f)
            if match:
                file_id = int(match.group(1))
                if file_id > max_id:
                    max_id = file_id

    return max_id + 1


def find_latest_transcript(memory_dir, date_str):
    """Find the latest transcript file for the given date."""
    pattern = re.compile(rf"^{re.escape(date_str)}-(\d{{4}})\.md$")
    latest_id = 0
    latest_file = None

    if os.path.exists(memory_dir):
        for f in os.listdir(memory_dir):
            match = pattern.match(f)
            if match:
                file_id = int(match.group(1))
                if file_id > latest_id:
                    latest_id = file_id
                    latest_file = f

    return latest_file


async def handler(
    mode: str,
    content: str,
    filename: str = None,
    session_key: str = None,
    stable_session_id: str = None,
    source: str = None,
    timestamp_utc: str = None,
    parent_day: str = None
) -> str:
    """Create or append to a session transcript.

    Args:
        mode: 'create' to start a new session transcript, 'append' to add to an existing one
        content: The content to write (initial content for create, additional content for append)
        filename: Optional target filename for append mode (e.g. '2026-07-09-0001.md'). If omitted, appends to the latest transcript of today.
        session_key: Optional session key identifier (e.g. 'agent:main:whatsapp:direct:+6289...')
        stable_session_id: Optional stable session UUID. If omitted, a new UUID is generated on create.
        source: Optional source label (e.g. 'whatsapp', 'telegram', 'webchat')
        timestamp_utc: Optional timestamp string for the session header (UTC). If omitted, current UTC time is used.
        parent_day: Optional parent day override (YYYY-MM-DD). If omitted, uses the UTC date of the run.
    """
    memory_dir = load_active_memory_dir()
    os.makedirs(memory_dir, exist_ok=True)

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    if mode == "create":
        session_id = get_next_session_id(memory_dir, today)
        new_filename = f"{today}-{session_id:04d}.md"
        file_path = os.path.join(memory_dir, new_filename)

        now_utc_str = timestamp_utc or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        stable_session_id_val = stable_session_id or str(uuid.uuid4())
        session_key_val = session_key or "agent:main:unknown"
        source_val = source or "unknown"
        parent_day_val = parent_day or today
        header = (
            f"# Session: {now_utc_str}\n"
            f"Parent Day: [[{parent_day_val}]]\n\n"
            f"- **Session Key**: {session_key_val}\n"
            f"- **Session ID**: {stable_session_id_val}\n"
            f"- **Source**: {source_val}\n\n"
            f"## Conversation Summary\n\n"
        )

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(header + content)
            return json.dumps({
                "status": "ok",
                "message": f"Created transcript: {new_filename}",
                "filename": new_filename,
                "session_id": f"{session_id:04d}",
                "stable_session_id": stable_session_id_val
            })
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to create transcript: {str(e)}"})

    elif mode == "append":
        if filename:
            # Sanitize: only use basename to prevent path traversal
            clean_name = os.path.basename(filename)
            file_path = os.path.join(memory_dir, clean_name)
        else:
            # Auto-detect latest transcript for today
            latest = find_latest_transcript(memory_dir, today)
            if not latest:
                return json.dumps({
                    "status": "error",
                    "message": "No active transcript found for today. Use mode='create' first."
                })
            file_path = os.path.join(memory_dir, latest)
            clean_name = latest

        # Verify path stays within memory_dir
        if not os.path.abspath(file_path).startswith(os.path.abspath(memory_dir)):
            return json.dumps({"status": "error", "message": "Invalid file path (path traversal detected)."})

        if not os.path.exists(file_path):
            return json.dumps({"status": "error", "message": f"Transcript file '{clean_name}' not found."})

        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n\n" + content)
            return json.dumps({
                "status": "ok",
                "message": f"Appended to transcript: {clean_name}",
                "filename": clean_name
            })
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to append to transcript: {str(e)}"})

    else:
        return json.dumps({"status": "error", "message": "Invalid mode. Use 'create' or 'append'."})
