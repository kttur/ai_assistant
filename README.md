# Home AI Assistant

A modular project for a general-purpose home AI assistant.

Goals:
- one architecture for multiple communication channels (Telegram, Android, voice, photos);
- fast module swapping (LLM platform, database, external connectors);
- control of a local computer and external internet resources;
- gradual addition of memory, dialogue history, and multi-user mode.

## Current Status

Implemented:
- base `src` skeleton split into `core / providers / modules`;
- configuration via environment variables;
- Telegram module based on `python-telegram-bot`;
- Telegram test commands: `/start`, `/id`, `/ping`, `/echo`, `/ask`, `/clear`, `/set`, `/settings`, `/settings_raw`, `/terminal`, `/exit`, `/cancel`, `/player`, `/mpc`, `/grant`, `/revoke`, `/role_add`, `/role_assign`, `/user_roles`, `/user_permissions`;
- MPC-HC control module (audio/subtitle next/prev, RU/EN selection);
- Voicemeeter output toggle support (for example, `Strip(5).A1`) via `.env`;
- terminal mode (powershell/wsl/cmd) with switching via `/terminal` and `/exit`;
- any regular Telegram text messages (non-commands) are sent to the LLM;
- dialogue history is stored per user and used as context;
- user settings are stored via a pluggable backend (`memory` or `postgres`);
- RBAC/permissions layer added (user override + role-based fallback);
- LLM can call system commands (`media/*`, `mpc/*`, `output/*`) via tool-call format;
- Ollama system instructions (English) added for Telegram HTML formatting;
- basic unit tests for Telegram handlers;
- context documents in the `context/` folder.

## Structure

```text
ai_assistant/
  context/
  src/ai_assistant/
    config/
    core/
    modules/telegram/
    providers/llm/
    providers/memory/
  tests/modules/telegram/
  main.py
  pyproject.toml
  .env.example
```

## Quick Start

1. Create/activate `.venv`.
2. Install dependencies:
   - `pip install -e .`
   - for OpenAI/Anthropic: `pip install -e .[openai,anthropic]`
   - for development: `pip install -e .[dev]`
3. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`.
4. Run:
   - `python main.py`
   - or `python -m ai_assistant`

## Key Environment Variables

- `ASSISTANT_CHANNEL` - current channel (`telegram`).
- `TELEGRAM_BOT_TOKEN` - Telegram bot token.
- `LLM_PROVIDER` - model provider (`mock`, `openai`, `anthropic`, `ollama`).
- `LLM_AVAILABLE_PROVIDERS` - list of providers available in settings (CSV).
- `USER_SETTINGS_BACKEND` - settings backend (`memory`, `postgres`).
- `PERMISSIONS_BACKEND` - permissions backend (`auto`, `disabled`, `memory`, `postgres`).
- `ADMIN_TELEGRAM_ID` - Telegram user id with full access (bypasses all permission checks), optional.
- `DEFAULT_LOCALE` - bot UI fallback locale (`ru` by default).
- `POSTGRES_DSN` - PostgreSQL DSN if `postgres` backend is selected.
- `AUDIO_OUTPUT_BACKEND` - audio output backend (`none`, `voicemeeter`).
- `TERMINAL_SHELL` - preferred shell (`powershell`, `wsl`, `cmd`, `auto`), default `powershell`.
- `TERMINAL_TIMEOUT_SECONDS` - command execution timeout in terminal mode.
- `VOICEMEETER_STRIP_INDEX` - strip index for target output (for example, `5`).
- `VOICEMEETER_BUS` - bus (`A1`..`A5`).
- `VOICEMEETER_OUTPUT_PARAM` - explicit Voicemeeter parameter (for example, `Strip[5].A1`), strict override.
- `VOICEMEETER_REMOTE_DLL_PATH` - path to `VoicemeeterRemote*.dll` (optional).
- `AI_ASSISTANT_OPENAI_API_KEY` - OpenAI API key.
- `AI_ASSISTANT_OPENAI_BASE_URL` - optional base URL for OpenAI SDK (for example, a compatible gateway).
- `AI_ASSISTANT_OPENAI_MODEL` - default OpenAI model.
- `AI_ASSISTANT_OPENAI_AVAILABLE_MODELS` - list of OpenAI models available in settings (CSV).
- `AI_ASSISTANT_ANTHROPIC_API_KEY` - Anthropic API key.
- `AI_ASSISTANT_ANTHROPIC_BASE_URL` - optional base URL for Anthropic SDK (for example, a compatible gateway).
- `AI_ASSISTANT_ANTHROPIC_MODEL` - default Anthropic model.
- `AI_ASSISTANT_ANTHROPIC_AVAILABLE_MODELS` - list of Anthropic models available in settings (CSV).
- `OLLAMA_AVAILABLE_MODELS` - list of Ollama models available in settings (CSV).

For backward compatibility, legacy names `OPENAI_*` and `ANTHROPIC_*` are still supported.

## Ollama

To run with a local model:

1. Start the Ollama service.
2. Set in `.env`:
   - `LLM_PROVIDER=ollama`
   - `OLLAMA_BASE_URL=http://localhost:11434`
   - `OLLAMA_MODEL=llama3.1` (or another installed model)
3. Verify that the model is installed (`ollama list`).
4. Start the bot and use `/ask`.

## LLM Tool Calls

The LLM receives the list of available commands and can call them in this format:

`<tool_call>{"command":"media.play_pause","args":{}}</tool_call>`

Supported commands:
- `media.play_pause`
- `media.previous_track`
- `media.next_track`
- `mpc.audio_next`
- `mpc.audio_previous`
- `mpc.subtitle_next`
- `mpc.subtitle_previous`
- `mpc.audio_set_language` (args: `{"language":"ru|en"}`)
- `mpc.subtitle_set_language` (args: `{"language":"ru|en"}`)
- `output.enable`
- `output.disable`
- `output.toggle`
- `output.status`

## Voicemeeter Output

If `.env` sets `AUDIO_OUTPUT_BACKEND=voicemeeter`:
- `/player` shows an additional output toggle button;
- LLM gets `output.*` commands to enable/disable/toggle output.

Minimal configuration:
- `AUDIO_OUTPUT_BACKEND=voicemeeter`
- `VOICEMEETER_STRIP_INDEX=5`
- `VOICEMEETER_BUS=A1`

If toggle does not affect the real output, set the parameter explicitly:
- `VOICEMEETER_OUTPUT_PARAM=Strip[5].A1`

## User Settings in Postgres

1. Install PostgreSQL dependencies:
   - `pip install -e .[postgres]`
2. Set in `.env`:
   - `USER_SETTINGS_BACKEND=postgres`
   - `POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/ai_assistant`
3. Restart the bot.
4. Use:
   - `/set <key> <value>`
   - `/settings` (section-based UI)
   - `/settings_raw` (raw key/value)

At startup, i18n tables for settings are also created:
- `setting_translations (setting_key, locale, section, title, description)`
- `setting_choice_translations (setting_id, option_name, locale, name, description)`

Bot UI texts come from `src/ai_assistant/resources/i18n/*.json`,
and setting/option names and descriptions come from PostgreSQL i18n tables.

## LLM Provider And Model Per User

`/settings` now includes choice settings:
- `llm_provider` - model backend;
- `llm_model` - model in `provider:model` format.

The list of available options comes from `.env`:
- providers: `LLM_AVAILABLE_PROVIDERS`;
- OpenAI models: `AI_ASSISTANT_OPENAI_AVAILABLE_MODELS`;
- Anthropic models: `AI_ASSISTANT_ANTHROPIC_AVAILABLE_MODELS`;
- Ollama models: `OLLAMA_AVAILABLE_MODELS`.

Option visibility is restricted by permissions:
- `assistant/llm.provider.<provider>`
- `assistant/llm.model.<provider>:<model>`

Actual LLM call selection is resolved per user request:
- first, the user's `llm_provider`/`llm_model` are used;
- if value is invalid or unavailable, fallback to `.env` defaults (`LLM_PROVIDER`, `AI_ASSISTANT_OPENAI_MODEL`, `AI_ASSISTANT_ANTHROPIC_MODEL`, `OLLAMA_MODEL`).

## Permissions

With `PERMISSIONS_BACKEND=postgres`, tables are created automatically:
- `permissions (id, type, name)`
- `user_permissions (user_id, permission_id, is_active)`
- `roles (id, name)`
- `role_permissions (role_id, permission_id)`
- `user_roles (user_id, role_id)`

Supported `permissions.type`:
- `general`
- `command`
- `assistant`

Permission check for a user:
- `coalesce(user_permissions.is_active, has_role_permission, false)`
- `has_role_permission` = at least one user role contains this permission.
- if `user_id == ADMIN_TELEGRAM_ID`, access is allowed without checking permission tables.

Applied checks:
- any incoming message processing: `general/usage`
- Telegram command `/X` execution: `command/X`
- AI chat (regular text and `/ask`): `general/assistant`
- AI tool command to system (for example `media.play_pause`): `assistant/<action>`
- LLM provider selection: `assistant/llm.provider.<provider>`
- LLM model selection: `assistant/llm.model.<provider>:<model>`

Permission administration commands:
- `/id` (show your own `user_id`; when replying to a message, also shows author data, and for forwarded/contact messages also shows original author/contact data)
- `/role_add <role_name>`
- `/role_assign <user_id> <role_name>`
- `/grant user <user_id> <type> <name>`
- `/grant role <role_name> <type> <name>`
- `/revoke user <user_id> <type> <name>` (sets `user_permissions.is_active=false`)
- `/revoke role <role_name> <type> <name>` (removes `role_permissions` link)
- `/user_roles <user_id>` (get user roles)
- `/user_permissions <user_id>` (get user overrides, role permissions, and effective permissions)

## Terminal Mode

- `/terminal` enables terminal mode for the current user.
- While mode is active, regular text messages run as shell commands in one live session.
- Shell state is preserved between commands (for example, `cd` affects subsequent commands).
- `ssh` is supported in interactive mode: first message starts a session, next messages are sent as stdin to active `ssh` process.
- To stop an interactive SSH session, send `exit` (inside ssh) or `/exit` (close terminal mode entirely).
- `/exit` disables terminal mode.
- Shell priority:
  - by `TERMINAL_SHELL`;
  - if unavailable, fallback is used (`powershell -> wsl -> cmd`).

## Next Steps

- extend OpenAI/Anthropic/Ollama providers (streaming, tool use);
- add adapters for Android, voice, image;
- add persistent memory (PostgreSQL/SQLite/Redis);
- add authorization/roles layer for multi-user.
