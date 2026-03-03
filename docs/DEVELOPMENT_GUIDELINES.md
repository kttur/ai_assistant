# Development Guidelines

## Goals

- Keep code easy to navigate for humans and LLM agents.
- Favor small, purpose-specific files over monoliths.
- Keep behavioral changes test-covered and explicit.

## Structural Rules

- Avoid growing single files beyond practical reading size.
- For Telegram module:
  - `handle_*` methods belong to `handler_methods/`.
  - internal utility methods belong to `handler_helpers/`.
  - reusable pure helpers belong to `handler_functions/`.
- Bootstrap logic should stay split by domain (`bootstrap_llm/`, `bootstrap_infra/`).

## Refactoring Rules

- Preserve public API compatibility (especially imports used by tests/integration).
- If moving symbols, provide transition aliases/re-exports where practical.
- Perform refactors in small, testable steps.

## Testing Rules

- Run full suite after structural changes:
  - `python -m pytest -q`
- Keep tests split by feature area; avoid oversized monolithic test files.

## Documentation Rules

- Canonical docs live in `docs/`.
- Runtime/context docs live in `context/`.
- Generated docs must be synced after structure changes:
  - `python -m ai_assistant.devtools.sync_docs`
- Freshness check:
  - `python -m ai_assistant.devtools.sync_docs --check`

## Scan Efficiency Rules

- During large code reads, exclude `.venv` and cache directories.
- Prefer targeted reads by folder (`src/ai_assistant`, `tests`, `docs`, `context`).
