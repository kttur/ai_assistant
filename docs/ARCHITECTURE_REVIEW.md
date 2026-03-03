# Architecture Review (Codex-Oriented)

## Scope

Repository-level review focused on:

- readability,
- change safety,
- maintainability by LLM coding agents (Codex-like workflows).

## Findings

1. `Medium`: Runtime method binding in Telegram handlers reduces static discoverability.
   - Current pattern: methods are distributed across `handler_methods/` and attached to `TelegramHandlers` in `handlers.py`.
   - Impact: harder static grep/navigation for new contributors and some IDE inspections.
   - Mitigation: documented in architecture docs and centralized bindings in one file.

2. `Medium`: Several infra/provider files remain relatively large.
   - Largest files are mostly in `providers/*` and dense settings callback logic.
   - Impact: slower comprehension for newcomers and LLM context windows.
   - Mitigation: tracked in `docs/PROJECT_MAP.md` largest-files section.

3. `Low`: Historical context files had drift from current implementation.
   - Impact: onboarding confusion.
   - Mitigation: generated context file + explicit read order in `docs/CODEX_START.md`.

## Strengths

- Clear layered boundaries (`core` separated from transport and providers).
- Composition root is explicit and modularized (`bootstrap*` packages).
- Tests are now feature-split (no large monolithic handler test file).
- Codex entrypoint and generated structure map now exist.

## Recommendations (Next Iterations)

1. Consider replacing runtime method binding with explicit composition classes/mixins per domain (`SettingsHandlers`, `MediaHandlers`, `AdminHandlers`).
2. Continue splitting dense provider/store modules when line count > ~350 and mixed responsibilities appear.
3. Keep generated docs in CI/commit flow to prevent context drift.
