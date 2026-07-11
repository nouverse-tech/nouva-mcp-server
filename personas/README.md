# Personas

This directory stores persona folders for `persona_engine`.

For persona concepts, validation rules, prompt assembly, and startup setup such as `--default-persona`, see the [Persona Engine README](../src/skills/persona_engine/README.md).

## Folder Layout

Each persona lives under `personas/<persona_name>/` and stores exactly these files:

- `IDENTITY.md`
- `SOUL.md`
- `USER.md`

## Git Policy

- Real personas in this folder are treated as private and ignored by Git by default.
- The repository keeps only:
  - this `README.md`
  - `nouva-example/` as a public template

## Example Layout

Use `personas/nouva-example/` as the reference structure for creating a new private persona folder.

Example:

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

## Notes

- Real personas should remain local/private.
- Do not store secrets, passwords, API keys, or sensitive environment details in persona files.
