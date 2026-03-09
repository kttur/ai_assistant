from __future__ import annotations

PLAYER_PLAY_PAUSE = "player:play_pause"
PLAYER_PREVIOUS = "player:previous"
PLAYER_NEXT = "player:next"
PLAYER_OUTPUT_TOGGLE = "player:output_toggle"

MPC_AUDIO_PREVIOUS = "mpc:audio_previous"
MPC_AUDIO_NEXT = "mpc:audio_next"
MPC_SUBTITLE_PREVIOUS = "mpc:subtitle_previous"
MPC_SUBTITLE_NEXT = "mpc:subtitle_next"
MPC_AUDIO_RU = "mpc:audio_ru"
MPC_AUDIO_EN = "mpc:audio_en"
MPC_SUBTITLE_RU = "mpc:subtitle_ru"
MPC_SUBTITLE_EN = "mpc:subtitle_en"
MPC_FULLSCREEN_ON = "mpc:fullscreen_on"
MPC_FULLSCREEN_OFF = "mpc:fullscreen_off"
SETTINGS_HOME = "settings:home"
VALID_PERMISSION_TYPES = {"general", "command", "assistant"}
START_COMMAND_HELP: tuple[dict[str, object], ...] = (
    {
        "name": "start",
        "description_key": "start.command.start",
        "usage": "/start",
    },
    {
        "name": "id",
        "description_key": "start.command.id",
        "usage": "/id",
    },
    {
        "name": "ping",
        "description_key": "start.command.ping",
        "usage": "/ping",
    },
    {
        "name": "echo",
        "description_key": "start.command.echo",
        "usage": "/echo <текст>",
    },
    {
        "name": "ask",
        "description_key": "start.command.ask",
        "usage": "/ask <вопрос>",
        "requires_assistant": True,
    },
    {
        "name": "clear",
        "description_key": "start.command.clear",
        "usage": "/clear",
    },
    {
        "name": "set",
        "description_key": "start.command.set",
        "usage": "/set <key> <value>",
    },
    {
        "name": "settings",
        "description_key": "start.command.settings",
        "usage": "/settings",
    },
    {
        "name": "settings_raw",
        "description_key": "start.command.settings_raw",
        "usage": "/settings_raw",
    },
    {
        "name": "terminal",
        "description_key": "start.command.terminal",
        "usage": "/terminal",
    },
    {
        "name": "exit",
        "description_key": "start.command.exit",
        "usage": "/exit",
    },
    {
        "name": "cancel",
        "description_key": "start.command.cancel",
        "usage": "/cancel",
    },
    {
        "name": "player",
        "description_key": "start.command.player",
        "usage": "/player",
    },
    {
        "name": "mpc",
        "description_key": "start.command.mpc",
        "usage": "/mpc",
    },
    {
        "name": "pc_link",
        "description_key": "start.command.pc_link",
        "usage": "/pc_link <one_time_code>",
    },
    {
        "name": "pc_list",
        "description_key": "start.command.pc_list",
        "usage": "/pc_list",
    },
    {
        "name": "pc_default",
        "description_key": "start.command.pc_default",
        "usage": "/pc_default <client_id|none>",
    },
    {
        "name": "pc_run",
        "description_key": "start.command.pc_run",
        "usage": "/pc_run <command> [args_json]",
    },
    {
        "name": "pc_share",
        "description_key": "start.command.pc_share",
        "usage": "/pc_share <client_id> <telegram_user_id>",
    },
    {
        "name": "pc_unshare",
        "description_key": "start.command.pc_unshare",
        "usage": "/pc_unshare <client_id> <telegram_user_id>",
    },
    {
        "name": "pc_unlink",
        "description_key": "start.command.pc_unlink",
        "usage": "/pc_unlink <client_id>",
    },
    {
        "name": "grant",
        "description_key": "start.command.grant",
        "usage": "/grant user <user_id> <type> <name> | /grant role <role_name> <type> <name>",
    },
    {
        "name": "revoke",
        "description_key": "start.command.revoke",
        "usage": "/revoke user <user_id> <type> <name> | /revoke role <role_name> <type> <name>",
    },
    {
        "name": "role_add",
        "description_key": "start.command.role_add",
        "usage": "/role_add <role_name>",
    },
    {
        "name": "role_assign",
        "description_key": "start.command.role_assign",
        "usage": "/role_assign <user_id> <role_name>",
    },
    {
        "name": "user_roles",
        "description_key": "start.command.user_roles",
        "usage": "/user_roles <user_id>",
    },
    {
        "name": "user_permissions",
        "description_key": "start.command.user_permissions",
        "usage": "/user_permissions <user_id>",
    },
)
