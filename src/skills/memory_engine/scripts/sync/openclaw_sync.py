import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Root of the OpenClaw workspace on the server
WORKSPACE_ROOT = "/root/.openclaw/workspace"

# Maps each core file → list of (nas_subfolder, nas_filename, title, tags)
CORE_MAPPINGS = {
    "USER.md": [
        ("cores", "USER.md", "User Profile", ["system-core"]),
        ("entities", "Gading.md", "Gading", ["person", "human"]),
    ],
    "INFRASTRUCTURE.md": [
        ("cores", "INFRASTRUCTURE.md", "Infrastructure Info", ["system-core"]),
        ("entities", "Homelab.md", "Homelab", ["infrastructure"]),
    ],
    "SOUL.md": [
        ("cores", "SOUL.md", "Agent Soul", ["system-core"]),
        ("entities", "Nouva.md", "Nouva", ["agent", "ai"]),
    ],
    "MEMORY.md": [
        ("cores", "MEMORY.md", "Long-Term Memory", ["durable-memory"]),
    ],
    "AGENTS.md": [
        ("cores", "AGENTS.md", "Agents Workspace", ["workspace"]),
    ],
    "IDENTITY.md": [
        ("cores", "IDENTITY.md", "Identity", ["identity"]),
    ],
}


def sync_core_files_to_nas(nas) -> None:
    """Copy OpenClaw core files (USER.md, SOUL.md, etc.) to NAS, with YAML frontmatter prepended."""
    print("--- Syncing OpenClaw Core Files to NAS ---")

    for local_name, targets in CORE_MAPPINGS.items():
        local_path = os.path.join(WORKSPACE_ROOT, local_name)
        if not os.path.exists(local_path):
            print(f"⏭️ Core file {local_name} not found locally.")
            continue

        with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        for subfolder, nas_name, title, tags in targets:
            yaml_fm = f'---\nschema_version: 1\ntitle: "{title}"\ntags: {json.dumps(tags)}\n---\n'
            full_content = yaml_fm + content
            tmp_path = f"/tmp/{nas_name}"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(full_content)
                if nas.copy_to(tmp_path, subfolder, nas_name):
                    print(f"✅ Synced {local_name} → NAS:{subfolder}/{nas_name}")
                else:
                    print(f"❌ Failed to sync {local_name} to NAS")
            except Exception as e:
                print(f"❌ Exception syncing {local_name}: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
