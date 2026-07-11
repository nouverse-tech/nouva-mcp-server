import os
import sys
import logging
import argparse
import importlib.util
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FileResource

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nouva-mcp-server")

# Initialize FastMCP Server
mcp = FastMCP("nouva-mcp-server")

REQUIRED_PERSONA_FILES = ("IDENTITY.md", "SOUL.md", "USER.md")

# --- STATIC TOOLS ---

@mcp.tool()
async def system_status() -> str:
    """Get the local system performance status (CPU, RAM, Disk space)"""
    import anyio
    
    async def run_cmd(cmd):
        import subprocess
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.stdout.strip()

    uptime_res = await run_cmd("uptime")
    mem_res = await run_cmd("free -h")
    disk_res = await run_cmd("df -h /")

    return "\n".join([
        "=== UPTIME & LOAD ===",
        uptime_res,
        "",
        "=== MEMORY USAGE ===",
        mem_res,
        "",
        "=== DISK SPACE (ROOT) ===",
        disk_res
    ])

@mcp.tool()
async def run_safe_command(command: str) -> str:
    """Run a restricted shell command inside the workspace sandbox
    
    Args:
        command: Shell command to run (e.g. 'git status', 'ls -la')
    """
    import subprocess
    
    blocked_keywords = [";", "&&", "||", "|", ">", "<", "&", "rm ", "sudo", "elevated", "chmod", "chown", "mv "]
    has_blocked = [k for k in blocked_keywords if k in command]
    
    if has_blocked:
        return f"Error: Command contains blocked characters/keywords ({', '.join(has_blocked)}). Only simple commands are allowed."

    workspace_root = "/root/.openclaw/workspace"
    try:
        res = subprocess.run(command, shell=True, cwd=workspace_root, capture_output=True, text=True, timeout=30)
        return "\n".join([
            f"Command: {command}",
            f"Directory: {workspace_root}",
            "",
            "=== STDOUT ===",
            res.stdout or "(no output)",
            "",
            "=== STDERR ===",
            res.stderr or "(no error output)"
        ])
    except Exception as e:
        return f"Error executing command: {str(e)}"

# --- DYNAMIC SKILLS LOADER ---

def load_skills():
    src_dir = Path(__file__).parent
    skills_dir = src_dir / "skills"
    
    if not skills_dir.exists():
        logger.warning(f"Skills directory not found at {skills_dir}")
        return

    for skill_folder in skills_dir.iterdir():
        if not skill_folder.is_dir():
            continue
        
        skill_name = skill_folder.name
        
        # 1. Load SKILL.md as Resource
        skill_md = skill_folder / "SKILL.md"
        if skill_md.exists():
            uri = f"metadata://skills/{skill_name}/guidelines"
            res_obj = FileResource(
                uri=uri,
                name=f"{skill_name}-guidelines",
                description=f"How to use the {skill_name} skill and its MCP tools",
                path=skill_md.absolute(),
                mime_type="text/markdown"
            )
            mcp.add_resource(res_obj)
            logger.info(f"Loaded resource guidelines for skill: {skill_name}")

        # 2. Load Tools from tools/ directory
        tools_dir = skill_folder / "tools"
        if tools_dir.exists():
            for tool_file in tools_dir.glob("*.py"):
                if tool_file.name == "__init__.py":
                    continue
                
                try:
                    # Dynamic import of the tool module
                    spec = importlib.util.spec_from_file_location(
                        f"dynamic_tool_{skill_name}_{tool_file.stem}",
                        tool_file
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        if hasattr(module, "handler") and hasattr(module, "metadata"):
                            tool_name = module.metadata.get("name", tool_file.stem)
                            tool_desc = module.metadata.get("description", module.handler.__doc__ or "")
                            
                            # Register tool to FastMCP
                            mcp.add_tool(
                                module.handler,
                                name=tool_name,
                                description=tool_desc
                            )
                            logger.info(f"Loaded dynamic tool: {tool_name} from skill {skill_name}")
                except Exception as e:
                    logger.error(f"Failed to load tool {tool_file.name} from skill {skill_name}: {e}")


def validate_persona_folder(persona_dir: Path):
    """Validate that a persona folder contains all required markdown files."""
    missing_files = [
        required_file
        for required_file in REQUIRED_PERSONA_FILES
        if not (persona_dir / required_file).is_file()
    ]
    if missing_files:
        raise ValueError(
            f"Persona '{persona_dir.name}' is invalid. Missing required files: {', '.join(missing_files)}"
        )


def load_persona_resources(default_persona: str | None = None):
    """Register valid persona markdown files as MCP resources and validate the default persona."""
    project_root = Path(__file__).resolve().parent.parent
    personas_dir = project_root / "personas"
    os.environ["NOUVA_PERSONAS_DIR"] = str(personas_dir)

    if not personas_dir.exists():
        if default_persona:
            raise ValueError(
                f"--default-persona was set to '{default_persona}' but personas directory does not exist: {personas_dir}"
            )
        logger.info("Personas directory not found; persona mode remains disabled.")
        return

    valid_persona_names = set()
    for persona_dir in sorted(personas_dir.iterdir()):
        if not persona_dir.is_dir():
            continue

        try:
            validate_persona_folder(persona_dir)
            valid_persona_names.add(persona_dir.name)
        except ValueError as error:
            logger.warning(f"Skipping invalid persona folder {persona_dir}: {error}")
            continue

        for required_file in REQUIRED_PERSONA_FILES:
            resource_name = required_file.replace(".md", "").lower()
            resource = FileResource(
                uri=f"metadata://personas/{persona_dir.name}/{resource_name}",
                name=f"{persona_dir.name}-{resource_name}",
                description=f"{resource_name.title()} markdown for persona {persona_dir.name}",
                path=(persona_dir / required_file).absolute(),
                mime_type="text/markdown"
            )
            mcp.add_resource(resource)
            logger.info(f"Loaded persona resource: {persona_dir.name}/{required_file}")

    if default_persona:
        if default_persona not in valid_persona_names:
            raise ValueError(
                f"Default persona '{default_persona}' is invalid or missing in {personas_dir}."
            )
        os.environ["NOUVA_DEFAULT_PERSONA"] = default_persona
        logger.info(f"Default persona enabled: {default_persona}")
    else:
        os.environ.pop("NOUVA_DEFAULT_PERSONA", None)
        logger.info("Default persona is disabled.")

# Load dynamic skills before startup
load_skills()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nouva MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport mode")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport")
    parser.add_argument(
        "--default-persona",
        type=str,
        default=None,
        help="Default persona folder name to load for new chats (e.g. --default-persona=nouva)"
    )
    args = parser.parse_args()
    load_persona_resources(args.default_persona)

    if args.transport == "sse":
        logger.info(f"Starting FastMCP server in SSE mode on host 0.0.0.0, port {args.port}...")
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = args.port
        mcp.settings.transport_security.enable_dns_rebinding_protection = False
        mcp.run(transport="sse")
    else:
        logger.info("Starting FastMCP server in STDIO mode...")
        mcp.run(transport="stdio")
