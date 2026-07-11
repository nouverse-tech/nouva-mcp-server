# Guidelines for Persona Engine

This skill provides startup persona packs from the repository `personas/` folder.

## Purpose

Use `persona_engine` when the client or agent wants to bootstrap a new chat session with a predefined persona. A persona is stored as a folder in `personas/<persona_name>/` and must contain exactly these required files:

- `IDENTITY.md`: assistant identity and role
- `SOUL.md`: persona style, values, and behavior
- `USER.md`: user profile and relationship context

`persona_engine` is for startup prompt assembly only. It is not a memory recall mechanism, not a long-term profile database, and not a per-turn behavior override system.

## When To Use

Use this skill when:

- the MCP server is started with `--default-persona=<name>`
- the client explicitly chooses a persona for a new chat
- the user explicitly asks to start or switch into a specific persona
- the client needs to validate whether a persona folder is complete before startup

Do not use this skill when:

- the task is memory recall, analytics, or transcript logging
- the chat is already running and no persona switch was requested
- the client just needs general repository documentation unrelated to persona startup

## Default Policy

- Default persona mode is off.
- Do not assume a persona should be loaded unless it was explicitly selected or configured via `--default-persona`.
- Do not silently fall back to another persona.
- Do not generate a synthetic persona if the requested folder is invalid.

## Validation Rules

- Fail fast if the persona folder does not exist.
- Fail fast if any required file is missing.
- Treat `IDENTITY.md`, `SOUL.md`, and `USER.md` as mandatory.
- Treat persona content as startup context, not as a substitute for memory recall or analytics data.

## Files

- `IDENTITY.md`: who the assistant is, such as name, role, mission, and stable identity
- `SOUL.md`: how the assistant behaves, such as tone, values, style, and boundaries
- `USER.md`: who the user is from the assistant's perspective, such as relationship and stable collaboration notes

## Tools

### `mcp_list_personas`

Use this tool to inspect what persona folders exist and whether they are structurally valid.

Returns JSON with:

- `status`
- `personas_dir`
- `default_persona`
- `personas`: a list of objects with `name`, `path`, `is_valid`, and `missing_files`

Use it before persona selection when the client needs deterministic validation.

### `mcp_get_persona_prompt`

Use this tool to load one persona and return the fully assembled startup prompt.

Behavior:

- If `persona_name` is provided, load that persona explicitly.
- If `persona_name` is omitted, fall back to the configured `--default-persona`.
- If neither exists, return an error.

Returns JSON with:

- `status`
- `persona_name`
- `persona_path`
- `prompt`

The `prompt` is assembled in this order:

1. `IDENTITY.md`
2. `SOUL.md`
3. `USER.md`

## Client Integration

Recommended flow for a new chat session:

1. Client starts or connects to the MCP server.
2. Client determines whether persona mode is off or whether `--default-persona=<name>` is active.
3. If a persona should be loaded, call `mcp_get_persona_prompt`.
4. Insert the returned `prompt` near the beginning of the session bootstrap/system prompt.
5. Begin ordinary user turns only after the startup prompt is assembled.

If no default persona is configured, keep persona mode off unless the client explicitly selects one.
