# AGENTS

## Start-Of-Chat Checklist

1. Read `docs/CODEX_START.md`.
2. Read `context/CODEX_CONTEXT.md`.
3. Do **not** deep-scan `.venv` (or `.git`/cache dirs) during project analysis.

## Documentation Sync Rule

- After structural changes in `src/`, `tests/`, `docs/`, or `context/`, run:
  - `python -m ai_assistant.devtools.sync_docs`
- Before finalizing substantial changes, ensure check mode passes:
  - `python -m ai_assistant.devtools.sync_docs --check`

## Environment Variable Sync Rule

- If you add, remove, or rename any environment variable used by the app, update `.env.example` in the same change.
- Keep default values and comments in `.env.example` aligned with `src/ai_assistant/config/settings.py`.

## Priority Sources

- Project map: `docs/PROJECT_MAP.md` (auto-generated).
- Architecture guide: `docs/ARCHITECTURE.md`.
- Dev rules: `docs/DEVELOPMENT_GUIDELINES.md`.
- Runtime context: `context/CODEX_CONTEXT.md` (auto-generated).
