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

## Logging Rules

- Use module-level logger in every non-trivial module:
  - `import logging`
  - `logger = logging.getLogger(__name__)`
- Configure logging centrally via `ai_assistant.logging_utils.configure_logging()` at app startup.
- Use `INFO` for lifecycle milestones:
  - service start/finish,
  - selected provider/model,
  - fallback activation,
  - arbiter application.
- Use `DEBUG` for execution trace details:
  - router confidence/risk/complexity/topic,
  - candidate queues and fallback chains,
  - permission checks and skip reasons,
  - response lengths and retries.
- Use `WARNING`/`ERROR` for degraded paths and hard failures.
- Avoid logging full sensitive payloads; prefer `text_preview(...)` and counts/metadata.

### Auto-Logging Checklist (for every new feature)

1. Log entry and exit points at `INFO` with stable identifiers (`user_id`, `provider`, `model`).
2. Log decision branches at `DEBUG` (why this path was chosen, and what alternatives were skipped).
3. Log exceptions with context (`logger.exception(...)` or `logger.warning(..., exc)`).
4. For fallback logic, always log:
   - trigger reason,
   - attempted chain order,
   - final successful target (or full exhaustion).
5. For new LLM or routing code, include:
   - recognized topic/domain label,
   - router confidence,
   - proposed model chain.

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
