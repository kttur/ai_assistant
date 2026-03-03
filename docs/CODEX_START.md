# Codex Start Guide

This file is the canonical entry point for new Codex chats in this repository.

## Read Order

1. `context/CODEX_CONTEXT.md` (auto-generated session context and scan rules).
2. `docs/ARCHITECTURE.md` (system boundaries and composition).
3. `docs/DEVELOPMENT_GUIDELINES.md` (coding and refactoring rules).
4. `docs/PROJECT_MAP.md` (auto-generated structure map).

## Mandatory Scan Exclusions

Always exclude these directories from deep scans unless explicitly required:

- `.venv`
- `.git`
- `__pycache__`
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `.idea`

Reason: these paths are high-volume and low-signal for code reasoning.

## Auto-Sync Documentation

- Update generated docs:
  - `python -m ai_assistant.devtools.sync_docs`
- Validate freshness without writing:
  - `python -m ai_assistant.devtools.sync_docs --check`

Generated files:

- `docs/PROJECT_MAP.md`
- `context/CODEX_CONTEXT.md`
