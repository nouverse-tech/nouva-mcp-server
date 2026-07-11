# Persona Engine

`persona_engine` provides startup persona packs that can be injected into the beginning of a new chat session.

Unlike `memory_engine`, which is used for recall and analytics after a conversation already exists, `persona_engine` defines the assistant's identity, style, and user relationship context before the first ordinary user turn begins.

## What A Persona Is

A persona is a folder under `personas/<persona_name>/` that contains exactly three required markdown files:

- `IDENTITY.md`: who the assistant is
- `SOUL.md`: how the assistant behaves
- `USER.md`: who the user is from the assistant's perspective

The engine validates these files strictly and fails fast when the folder is invalid.

## File Meanings

### `IDENTITY.md`

Use `IDENTITY.md` to define the assistant's stable identity:

- name
- role
- mission
- calling preference
- language preference
- overall vibe

This answers the question: "Who am I in this relationship?"

### `SOUL.md`

Use `SOUL.md` to define the assistant's behavior and personality:

- tone
- values
- communication style
- decision-making style
- boundaries
- things the assistant should or should not do

This answers the question: "How should I behave?"

### `USER.md`

Use `USER.md` to define the human context:

- user name
- role
- relationship to the assistant
- preferences
- collaboration style
- important stable notes

This answers the question: "Who is the user to me?"

## Folder Structure

```text
personas/
  README.md
  nouva-example/
    IDENTITY.md
    SOUL.md
    USER.md
  my-private-persona/
    IDENTITY.md
    SOUL.md
    USER.md
```

## Setup

### 1. Create a persona folder

Create a new folder inside `personas/`, for example:

```bash
mkdir -p personas/my-private-persona
```

### 2. Add the required files

Create these three files:

- `personas/my-private-persona/IDENTITY.md`
- `personas/my-private-persona/SOUL.md`
- `personas/my-private-persona/USER.md`

You can copy from the public template:

```bash
cp -R personas/nouva-example personas/my-private-persona
```

Then edit the contents for your actual persona.

### 3. Keep real personas private

The repository ignores most persona folders by default through `.gitignore`.

Only these are intended to stay in Git:

- `personas/README.md`
- `personas/nouva-example/`

### 4. Start the MCP server with a default persona

Persona mode is off by default. To enable one persona automatically for every new chat:

```bash
python3 src/main.py --transport stdio --default-persona=my-private-persona
```

Or for SSE:

```bash
python3 src/main.py --transport sse --port 8000 --default-persona=my-private-persona
```

If the folder does not exist or any required file is missing, startup validation fails.

## MCP Tools

`persona_engine` currently exposes two tools:

- `mcp_list_personas`: list persona folders and show whether they are structurally valid
- `mcp_get_persona_prompt`: validate a persona and return the combined startup prompt

### `mcp_list_personas`

Use this tool when the client or agent wants deterministic visibility into available persona folders before startup.

Returned JSON fields:

- `status`
- `personas_dir`
- `default_persona`
- `personas`

Each persona entry includes:

- `name`
- `path`
- `is_valid`
- `missing_files`

### `mcp_get_persona_prompt`

Use this tool when a persona should actually be loaded into a new chat session.

Input behavior:

- If `persona_name` is provided, that folder is loaded explicitly.
- If `persona_name` is omitted, the tool falls back to `--default-persona`.
- If neither is available, the tool returns an error.

Returned JSON fields:

- `status`
- `persona_name`
- `persona_path`
- `prompt`

## Startup Prompt Assembly

When a persona is loaded, the engine assembles a startup prompt in this order:

1. `IDENTITY.md`
2. `SOUL.md`
3. `USER.md`

This ordering keeps the assistant identity first, then personality, then user context.

## Client Flow

Recommended flow:

1. Client starts or connects to the MCP server
2. Client knows whether `--default-persona=<name>` is enabled
3. At the beginning of a new chat session, client calls `mcp_get_persona_prompt`
4. Client inserts the returned `prompt` near the beginning of the session bootstrap/system prompt
5. Regular user turns begin after that

If no default persona is configured, persona mode should remain off unless the client explicitly chooses one.

## Startup Validation

The server validates persona startup in two places:

- During MCP server startup, `--default-persona=<name>` is checked against the local `personas/` directory.
- During tool use, `mcp_get_persona_prompt` validates the selected folder again before returning prompt text.

Validation fails when:

- the requested persona folder does not exist
- `IDENTITY.md` is missing
- `SOUL.md` is missing
- `USER.md` is missing

There is no fallback to another persona.

## What Gets Registered

At MCP server startup, valid persona folders are registered as read-only metadata resources:

- `metadata://personas/<persona_name>/identity`
- `metadata://personas/<persona_name>/soul`
- `metadata://personas/<persona_name>/user`

This means clients can inspect the raw markdown resources directly, while `mcp_get_persona_prompt` provides the assembled bootstrap prompt.

## Design Notes

- `persona_engine` is not memory recall.
- `persona_engine` should be loaded at session start, not every turn.
- Persona files should contain stable identity and behavior guidance, not temporary task instructions.
- Do not store secrets, passwords, API keys, or sensitive environment details in persona files.
