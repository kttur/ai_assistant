# Implementation Context for Future Work

## Current Tech Stack

- Python 3.11+
- `python-telegram-bot` for Telegram transport
- `pytest` for tests
- optional SDKs: `openai`, `anthropic`

## Important Constraints

- The project must remain modular-first.
- Changes in one channel must not break the rest of the system.
- LLM and memory providers must be replaceable via interfaces.
- Repository scans must exclude `.venv` by default.

## Suggested Next Files to Touch

- `src/ai_assistant/providers/llm/user_selectable_provider.py` (router/auto-mode evolution)
- `src/ai_assistant/modules/telegram/handler_methods/handle_settings_callback.py`
- `src/ai_assistant/providers/settings/` (storage and i18n sync)
- `src/ai_assistant/devtools/sync_docs.py` (documentation automation)

## Coding Guidelines

- keep business logic in `core/service.py`;
- keep transport handlers thin and split by feature files;
- do not couple core to a specific Telegram/OpenAI/Ollama library;
- write unit tests for every new business-logic branch.
- after structural changes run:
  - `python -m ai_assistant.devtools.sync_docs`
