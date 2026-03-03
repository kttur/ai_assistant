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

## Priority Sources

- Project map: `docs/PROJECT_MAP.md` (auto-generated).
- Architecture guide: `docs/ARCHITECTURE.md`.
- Dev rules: `docs/DEVELOPMENT_GUIDELINES.md`.
- Runtime context: `context/CODEX_CONTEXT.md` (auto-generated).
