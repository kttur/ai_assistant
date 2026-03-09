from __future__ import annotations

import logging

from ai_assistant.core.interfaces import (
    MPCController,
    MediaController,
    OutputController,
    PermissionAdminStore,
    PermissionChecker,
    TerminalCommandExecutor,
    TranslationService,
    UserSettingsStore,
)
from ai_assistant.core.service import AssistantService
from ai_assistant.modules.telegram.handler_constants import (
    MPC_AUDIO_NEXT,
    MPC_AUDIO_PREVIOUS,
    MPC_AUDIO_RU,
    MPC_FULLSCREEN_OFF,
    MPC_FULLSCREEN_ON,
    MPC_SUBTITLE_NEXT,
    MPC_SUBTITLE_RU,
    PLAYER_NEXT,
    PLAYER_OUTPUT_TOGGLE,
    PLAYER_PLAY_PAUSE,
    PLAYER_PREVIOUS,
    SETTINGS_HOME,
)
from ai_assistant.modules.telegram.handler_types import PendingTextSettingInput as _PendingTextSettingInput
from ai_assistant.providers.remote.remote_device_service import RemoteDeviceService
from ai_assistant.providers.remote.ws_hub import RemoteWebSocketHub
from ai_assistant.providers.i18n.file_translation_service import FileTranslationService

logger = logging.getLogger(__name__)


class TelegramHandlers:
    def __init__(
        self,
        assistant_service: AssistantService,
        user_settings_store: UserSettingsStore | None = None,
        media_controller: MediaController | None = None,
        mpc_controller: MPCController | None = None,
        output_controller: OutputController | None = None,
        terminal_executor: TerminalCommandExecutor | None = None,
        permission_checker: PermissionChecker | None = None,
        permission_admin: PermissionAdminStore | None = None,
        admin_telegram_id: int | None = None,
        translation_service: TranslationService | None = None,
        remote_device_service: RemoteDeviceService | None = None,
        remote_ws_hub: RemoteWebSocketHub | None = None,
    ) -> None:
        self._assistant_service = assistant_service
        self._user_settings_store = user_settings_store
        self._media_controller = media_controller
        self._mpc_controller = mpc_controller
        self._output_controller = output_controller
        self._terminal_executor = terminal_executor
        self._permission_checker = permission_checker
        self._permission_admin = permission_admin
        self._admin_telegram_id = admin_telegram_id
        self._remote_device_service = remote_device_service
        self._remote_ws_hub = remote_ws_hub
        self._translation_service = translation_service or FileTranslationService(
            default_locale="ru",
            fallback_locale="en",
        )
        self._terminal_mode_users: set[int] = set()
        self._pending_text_setting_inputs: dict[int, _PendingTextSettingInput] = {}
        logger.info(
            "Telegram handlers initialized: admin_telegram_id=%s terminal_runtime=%s remote_runtime=%s",
            self._admin_telegram_id,
            "enabled" if self._terminal_executor is not None else "disabled",
            "enabled" if self._remote_device_service is not None else "disabled",
        )


from ai_assistant.modules.telegram.handler_helpers import (
    _answer_callback,
    _build_start_command_lines,
    _build_start_message,
    _clear_text_setting_value,
    _edit_setting_page_message,
    _edit_settings_home_message,
    _format_setting_value,
    _get_visible_settings_sections,
    _handle_pending_text_setting_input,
    _has_optional_permission,
    _has_permission,
    _is_command_runtime_available,
    _localize_settings_section_name,
    _mpc_keyboard,
    _normalize_settings_section_key,
    _player_keyboard,
    _reject_callback_if_not_allowed,
    _reject_if_no_callback_permission,
    _reject_if_no_message_permission,
    _reject_if_not_allowed,
    _reject_if_permission_admin_unavailable,
    _render_setting_text,
    _render_settings_home_text,
    _resolve_active_llm_provider,
    _resolve_setting_for_write,
    _resolve_setting_page,
    _resolve_user_locale,
    _send_settings_home_message,
    _set_choice_setting_value,
    _settings_home_keyboard,
    _settings_nav_row,
    _settings_setting_keyboard,
    _start_text_setting_input,
    _sync_llm_model_with_provider,
    _t,
    _toggle_bool_setting,
)
from ai_assistant.modules.telegram.handler_methods import (
    _handle_terminal_command,
    _reply_with_llm,
    _send_llm_reply,
    _typing_heartbeat,
    handle_ask,
    handle_cancel,
    handle_clear,
    handle_echo,
    handle_exit_terminal_mode,
    handle_grant,
    handle_id,
    handle_mpc,
    handle_mpc_button,
    handle_pc_default,
    handle_pc_link,
    handle_pc_list,
    handle_pc_run,
    handle_pc_share,
    handle_pc_unlink,
    handle_pc_unshare,
    handle_ping,
    handle_player,
    handle_player_button,
    handle_revoke,
    handle_role_add,
    handle_role_assign,
    handle_set_setting,
    handle_settings,
    handle_settings_callback,
    handle_settings_raw,
    handle_start,
    handle_terminal_mode,
    handle_text_message,
    handle_user_permissions,
    handle_user_roles,
)

TelegramHandlers.handle_start = handle_start
TelegramHandlers.handle_id = handle_id
TelegramHandlers.handle_ping = handle_ping
TelegramHandlers.handle_echo = handle_echo
TelegramHandlers.handle_ask = handle_ask
TelegramHandlers.handle_text_message = handle_text_message
TelegramHandlers.handle_terminal_mode = handle_terminal_mode
TelegramHandlers.handle_exit_terminal_mode = handle_exit_terminal_mode
TelegramHandlers.handle_cancel = handle_cancel
TelegramHandlers._handle_terminal_command = _handle_terminal_command
TelegramHandlers.handle_clear = handle_clear
TelegramHandlers.handle_set_setting = handle_set_setting
TelegramHandlers.handle_settings_raw = handle_settings_raw
TelegramHandlers.handle_settings = handle_settings
TelegramHandlers.handle_settings_callback = handle_settings_callback
TelegramHandlers.handle_pc_link = handle_pc_link
TelegramHandlers.handle_pc_list = handle_pc_list
TelegramHandlers.handle_pc_default = handle_pc_default
TelegramHandlers.handle_pc_run = handle_pc_run
TelegramHandlers.handle_pc_share = handle_pc_share
TelegramHandlers.handle_pc_unshare = handle_pc_unshare
TelegramHandlers.handle_pc_unlink = handle_pc_unlink
TelegramHandlers.handle_role_add = handle_role_add
TelegramHandlers.handle_role_assign = handle_role_assign
TelegramHandlers.handle_grant = handle_grant
TelegramHandlers.handle_revoke = handle_revoke
TelegramHandlers.handle_user_roles = handle_user_roles
TelegramHandlers.handle_user_permissions = handle_user_permissions
TelegramHandlers._reply_with_llm = _reply_with_llm
TelegramHandlers._typing_heartbeat = _typing_heartbeat
TelegramHandlers._send_llm_reply = _send_llm_reply
TelegramHandlers.handle_player = handle_player
TelegramHandlers.handle_player_button = handle_player_button
TelegramHandlers.handle_mpc = handle_mpc
TelegramHandlers.handle_mpc_button = handle_mpc_button

TelegramHandlers._t = _t
TelegramHandlers._resolve_user_locale = _resolve_user_locale
TelegramHandlers._player_keyboard = _player_keyboard
TelegramHandlers._mpc_keyboard = staticmethod(_mpc_keyboard)
TelegramHandlers._reject_if_not_allowed = _reject_if_not_allowed
TelegramHandlers._reject_callback_if_not_allowed = _reject_callback_if_not_allowed
TelegramHandlers._has_permission = _has_permission
TelegramHandlers._reject_if_no_message_permission = _reject_if_no_message_permission
TelegramHandlers._reject_if_no_callback_permission = _reject_if_no_callback_permission
TelegramHandlers._is_command_runtime_available = _is_command_runtime_available
TelegramHandlers._build_start_command_lines = _build_start_command_lines
TelegramHandlers._build_start_message = _build_start_message
TelegramHandlers._normalize_settings_section_key = _normalize_settings_section_key
TelegramHandlers._localize_settings_section_name = _localize_settings_section_name
TelegramHandlers._has_optional_permission = _has_optional_permission
TelegramHandlers._get_visible_settings_sections = _get_visible_settings_sections
TelegramHandlers._settings_home_keyboard = _settings_home_keyboard
TelegramHandlers._render_settings_home_text = _render_settings_home_text
TelegramHandlers._format_setting_value = _format_setting_value
TelegramHandlers._resolve_active_llm_provider = _resolve_active_llm_provider
TelegramHandlers._render_setting_text = _render_setting_text
TelegramHandlers._settings_nav_row = _settings_nav_row
TelegramHandlers._settings_setting_keyboard = _settings_setting_keyboard
TelegramHandlers._resolve_setting_page = _resolve_setting_page
TelegramHandlers._send_settings_home_message = _send_settings_home_message
TelegramHandlers._edit_settings_home_message = _edit_settings_home_message
TelegramHandlers._edit_setting_page_message = _edit_setting_page_message
TelegramHandlers._toggle_bool_setting = _toggle_bool_setting
TelegramHandlers._set_choice_setting_value = _set_choice_setting_value
TelegramHandlers._sync_llm_model_with_provider = _sync_llm_model_with_provider
TelegramHandlers._clear_text_setting_value = _clear_text_setting_value
TelegramHandlers._resolve_setting_for_write = _resolve_setting_for_write
TelegramHandlers._start_text_setting_input = _start_text_setting_input
TelegramHandlers._handle_pending_text_setting_input = _handle_pending_text_setting_input
TelegramHandlers._reject_if_permission_admin_unavailable = _reject_if_permission_admin_unavailable
TelegramHandlers._answer_callback = _answer_callback
