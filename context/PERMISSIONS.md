# Permissions Reference

## Permission Types

- `general` - basic permissions to use the bot and assistant.
- `command` - permissions to run specific Telegram commands.
- `assistant` - permissions for system actions that the LLM can perform on behalf of the user.

## Resolution Rules

For a user, permission is resolved as:

`coalesce(user_permissions.is_active, has_role_permission, false)`

where:

- `user_permissions` - per-user override (takes precedence over roles).
- `has_role_permission` - at least one user role has this permission.
- if no record exists in `user_permissions`, role result is used.
- if permission is absent in both overrides and roles, access is denied.

Additionally:

- if `ADMIN_TELEGRAM_ID` matches `user_id`, access is allowed without checking permission tables.
- if `PERMISSIONS_BACKEND=disabled` (or checker is not wired), checks are effectively skipped.

## General Permissions

- `general/usage`
- `general/assistant`

Purpose:

- `general/usage` - required to process any incoming message and callback buttons.
- `general/assistant` - required for AI communication:
  - `/ask` command
  - regular text messages (non-commands) when user is not in terminal mode.

## Command Permissions

Each Telegram command requires `command/<name>`:

- `command/start`
- `command/id`
- `command/ping`
- `command/echo`
- `command/ask`
- `command/clear`
- `command/set`
- `command/settings`
- `command/settings_raw`
- `command/terminal`
- `command/exit`
- `command/cancel`
- `command/player`
- `command/mpc`
- `command/pc_link`
- `command/pc_list`
- `command/pc_default`
- `command/pc_run`
- `command/pc_share`
- `command/pc_unshare`
- `command/pc_unlink`
- `command/grant`
- `command/revoke`
- `command/role_add`
- `command/role_assign`
- `command/user_roles`
- `command/user_permissions`

Notes:

- `command/player` is also checked for `/player` button clicks.
- `command/mpc` is also checked for `/mpc` button clicks.
- `command/settings` is also checked for UI button clicks in `/settings`.
- Admin commands (`grant/revoke/role_add/role_assign/user_roles/user_permissions`) also require an available `PermissionAdminStore` backend.

## Assistant Permissions

LLM tools are checked as `assistant/<action_name>`, where `action_name` is the exact command name from the tool catalog.

Current local set (depends on connected controllers):

- `assistant/media.play_pause`
- `assistant/media.previous_track`
- `assistant/media.next_track`
- `assistant/mpc.audio_next`
- `assistant/mpc.audio_previous`
- `assistant/mpc.subtitle_next`
- `assistant/mpc.subtitle_previous`
- `assistant/mpc.audio_set_language`
- `assistant/mpc.subtitle_set_language`
- `assistant/output.enable`
- `assistant/output.disable`
- `assistant/output.toggle`
- `assistant/output.status`
- `assistant/llm.provider.<provider>` (for example, `assistant/llm.provider.openai`, `assistant/llm.provider.ollama`)
- `assistant/llm.model.<provider>:<model>` (for example, `assistant/llm.model.openai:gpt-4.1-mini`, `assistant/llm.model.ollama:mistral-small3.2:24b`)

Remote tools (when user has linked online devices) are exposed as `remote.<command>` and checked as:

- `assistant/remote.<command>`
- example: `assistant/remote.media.play_pause`
- filesystem commands:
  - `assistant/remote.filesystem.list_directory`
  - `assistant/remote.filesystem.file_info`
  - `assistant/remote.filesystem.read_file`
  - `assistant/remote.filesystem.send_file`
  - `assistant/remote.filesystem.write_file`

For `/pc_run`, filesystem commands have additional fine-grained checks:

- `filesystem.list_directory` -> requires `assistant/remote.filesystem.list_directory`
- `filesystem.file_info`, `filesystem.read_file`, `filesystem.send_file` -> require `assistant/remote.filesystem.read_file`
- `filesystem.write_file` (including `send_to_telegram=true`) -> requires `assistant/remote.filesystem.write_file`

If the corresponding controller/client is not connected, the command is not included in the available LLM catalog.

For LLM selection in `/settings`:

- `llm_provider` option visibility depends on `assistant/llm.provider.<provider>`;
- `llm_model` option visibility depends on `assistant/llm.model.<provider>:<model>`;
- actual runtime provider/model selection also checks these permissions (protection against bypass via raw `/set`).

## Minimal Working Set Examples

Regular user (assistant chat only):

- `general/usage`
- `general/assistant`
- `assistant/llm.provider.<provider>`
- `assistant/llm.model.<provider>:<model>`
- `command/ask` (if `/ask` is needed specifically)

User with media buttons:

- `general/usage`
- `command/player`
- `command/mpc`

Permissions admin:

- `general/usage`
- `command/grant`
- `command/revoke`
- `command/role_add`
- `command/role_assign`
- `command/user_roles`
- `command/user_permissions`
