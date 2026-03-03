# Architecture

## Purpose

Home AI assistant with pluggable channels, LLM providers, settings backends, and permission management.

## Layering

- `core/`: domain models, interfaces, and orchestration (`AssistantService`).
- `providers/`: infrastructure adapters (LLM, settings storage, permissions, terminal, system control).
- `modules/`: transport/channel implementations (currently Telegram).
- `config/`: environment parsing and runtime settings.
- `bootstrap*`: composition root and dependency wiring.

## Composition Root

- Main composition entry: `src/ai_assistant/bootstrap.py`.
- LLM wiring: `src/ai_assistant/bootstrap_llm/`.
- Infra wiring: `src/ai_assistant/bootstrap_infra/`.

## Telegram Module Structure

- Thin facade class: `src/ai_assistant/modules/telegram/handlers.py`.
- Handler methods split by file: `handler_methods/`.
- Internal helper methods split by file: `handler_helpers/`.
- Shared constants/types:
  - `handler_constants.py`
  - `handler_types.py`
  - `handler_functions/` (pure utility helpers)

## Current Architectural Strengths

- Clear dependency direction (`core` independent from transport/infrastructure details).
- Composition centralized in bootstrap layer.
- Large transport logic split into smaller files (better local reasoning for LLM agents).
- Pluggable LLM/settings/permissions backends.

## Current Risks

- Telegram module uses runtime method binding in `handlers.py` (function-to-class assignment), which is flexible but less explicit for static navigation.
- Settings callback flow remains one of the densest logic areas (`handle_settings_callback` + related helpers).
- Documentation was previously fragmented between README and `context/`; now consolidated but requires sync discipline.

## Architecture Direction (Recommended)

- Keep transport adapters thin and move business rules toward service/helper functions.
- Prefer pure functions for parsing/formatting decisions.
- Keep all composition logic in bootstrap packages.
- Limit file size growth with:
  - one handler per file,
  - one helper per file (for non-trivial helpers),
  - generated project map checked in.
