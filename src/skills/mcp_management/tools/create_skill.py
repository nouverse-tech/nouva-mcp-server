import os
import re
from pathlib import Path

metadata = {
    "name": "mcp_create_skill",
    "description": "Create a new modular skill directory structure along with boilerplate SKILL.md and Python tools"
}

async def handler(skill_name: str, description: str = "", tools: list[str] = None) -> str:
    """Create a new skill with complete boilerplates.
    
    Args:
        skill_name: Name of the skill (snake_case, e.g. 'domain_management')
        description: Short description of the skill
        tools: List of tool names to create boilerplates for (e.g. ['add_domain', 'remove_domain'])
    """
    # Clean skill name to snake_case
    skill_name = re.sub(r'[^a-zA-Z0-9\s_]', '', skill_name).strip().lower()
    skill_name = re.sub(r'[\s-]+', '_', skill_name)
    
    if not skill_name:
        return "Error: Invalid skill name."

    # Resolve paths relative to this file
    project_root = Path(__file__).parent.parent.parent.parent
    skill_dir = project_root / "src" / "skills" / skill_name
    tools_dir = skill_dir / "tools"

    if skill_dir.exists():
        return f"Error: Skill '{skill_name}' already exists at {skill_dir.relative_to(project_root)}."

    try:
        # 1. Create directories
        tools_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Write SKILL.md
        skill_md_content = f"""# Guidelines for {skill_name.replace('_', ' ').title()}

{description or 'Write detailed instructions for the LLM regarding this skill here.'}

## Tools
"""
        if tools:
            for t in tools:
                clean_t = re.sub(r'[^a-zA-Z0-9_]', '', t.strip().lower())
                skill_md_content += f"- `{clean_t}`: Description of tool {clean_t}\n"
        
        with open(skill_dir / "SKILL.md", "w") as f:
            f.write(skill_md_content)

        # 3. Write boilerplate tools
        created_tools = []
        if tools:
            for t in tools:
                clean_t = re.sub(r'[^a-zA-Z0-9_]', '', t.strip().lower())
                if not clean_t:
                    continue
                
                tool_content = f"""metadata = {{
    "name": "{clean_t}",
    "description": "Boilerplate description for {clean_t}"
}}

async def handler(param1: str) -> str:
    \"\"\"Boilerplate handler for {clean_t}.
    
    Args:
        param1: First parameter
    \"\"\"
    # TODO: Implement tool logic
    return f"Hello from {clean_t}! Received param1: {{param1}}"
"""
                tool_file_path = tools_dir / f"{clean_t}.py"
                with open(tool_file_path, "w") as f:
                    f.write(tool_content)
                created_tools.append(f"src/skills/{skill_name}/tools/{clean_t}.py")

        status_msg = [
            f"Successfully created modular skill '{skill_name}'!",
            f"- Created: src/skills/{skill_name}/SKILL.md"
        ]
        for ct in created_tools:
            status_msg.append(f"- Created: {ct}")

        return "\n".join(status_msg)

    except Exception as e:
        return f"Error creating skill: {str(e)}"
