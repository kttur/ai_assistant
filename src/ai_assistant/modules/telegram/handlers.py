from __future__ import annotations

import asyncio
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

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
from ai_assistant.core.models import SettingChoiceOption, SettingDefinition, TerminalCommandResult
from ai_assistant.core.service import AssistantService
from ai_assistant.providers.i18n.file_translation_service import FileTranslationService

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


@dataclass(slots=True, frozen=True)
class _VisibleSetting:
    key: str
    value_type: str
    section: str
    title: str
    description: str
    current_value: str | None
    can_write: bool
    options: tuple[SettingChoiceOption, ...]


@dataclass(slots=True, frozen=True)
class _PendingTextSettingInput:
    setting_key: str


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
        self._translation_service = translation_service or FileTranslationService(
            default_locale="ru",
            fallback_locale="en",
        )
        self._terminal_mode_users: set[int] = set()
        self._pending_text_setting_inputs: dict[int, _PendingTextSettingInput] = {}

    def _t(self, message_key: str, locale: str | None = None, **params: object) -> str:
        return self._translation_service.translate(message_key, locale=locale, **params)

    async def _resolve_user_locale(self, user_id: int) -> str:
        locale = self._translation_service.get_default_locale()
        if not self._user_settings_store:
            return locale
        try:
            setting_value = await self._user_settings_store.get_setting(user_id=user_id, key="language")
        except Exception:
            return locale
        if setting_value:
            return self._translation_service.resolve_locale(setting_value)
        return locale

    def _player_keyboard(self) -> InlineKeyboardMarkup:
        row = [
            InlineKeyboardButton("⏮", callback_data=PLAYER_PREVIOUS),
            InlineKeyboardButton("⏯", callback_data=PLAYER_PLAY_PAUSE),
            InlineKeyboardButton("⏭", callback_data=PLAYER_NEXT),
        ]
        if self._output_controller is not None:
            row.append(InlineKeyboardButton("🔊", callback_data=PLAYER_OUTPUT_TOGGLE))
        return InlineKeyboardMarkup([row])

    @staticmethod
    def _mpc_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Аудио ⬅", callback_data=MPC_AUDIO_PREVIOUS),
                    InlineKeyboardButton("Аудио ➡", callback_data=MPC_AUDIO_NEXT),
                ],
                [
                    InlineKeyboardButton("Сабы ⬅", callback_data=MPC_SUBTITLE_PREVIOUS),
                    InlineKeyboardButton("Сабы ➡", callback_data=MPC_SUBTITLE_NEXT),
                ],
                [
                    InlineKeyboardButton("Аудио RU", callback_data=MPC_AUDIO_RU),
                    InlineKeyboardButton("Аудио EN", callback_data=MPC_AUDIO_EN),
                ],
                [
                    InlineKeyboardButton("Сабы RU", callback_data=MPC_SUBTITLE_RU),
                    InlineKeyboardButton("Сабы EN", callback_data=MPC_SUBTITLE_EN),
                ],
            ]
        )

    async def _reject_if_not_allowed(self, update: Update) -> bool:
        del update
        return False

    async def _reject_callback_if_not_allowed(self, update: Update) -> bool:
        del update
        return False

    async def _has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        if self._admin_telegram_id is not None and user_id == self._admin_telegram_id:
            return True
        if not self._permission_checker:
            return True
        return await self._permission_checker.has_permission(
            user_id=user_id,
            permission_type=permission_type,
            name=name,
        )

    async def _reject_if_no_message_permission(
        self,
        update: Update,
        permission_type: str,
        name: str,
    ) -> bool:
        user = update.effective_user
        if not user:
            return True
        if await self._has_permission(
            user_id=user.id,
            permission_type=permission_type,
            name=name,
        ):
            return False
        locale = await self._resolve_user_locale(user.id)
        if update.effective_message:
            await update.effective_message.reply_text(
                self._t(
                    "errors.permission_denied",
                    locale=locale,
                    permission=f"{permission_type}/{name}",
                )
            )
        return True

    async def _reject_if_no_callback_permission(
        self,
        update: Update,
        permission_type: str,
        name: str,
    ) -> bool:
        user = update.effective_user
        if not user:
            return True
        if await self._has_permission(
            user_id=user.id,
            permission_type=permission_type,
            name=name,
        ):
            return False
        locale = await self._resolve_user_locale(user.id)
        if update.callback_query:
            await self._answer_callback(
                update.callback_query,
                self._t(
                    "errors.permission_denied",
                    locale=locale,
                    permission=f"{permission_type}/{name}",
                ),
                show_alert=True,
            )
        return True

    @staticmethod
    def _normalize_permission_type(value: str) -> str | None:
        normalized = value.strip().lower()
        if normalized in VALID_PERMISSION_TYPES:
            return normalized
        return None

    @staticmethod
    def _format_username(username: str | None) -> str:
        if username:
            return f"@{username}"
        return "(no username)"

    @classmethod
    def _render_user_section(cls, title: str, user) -> str:
        user_id = getattr(user, "id", None)
        username = getattr(user, "username", None)
        first_name = getattr(user, "first_name", None)
        last_name = getattr(user, "last_name", None)
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()

        lines = [title]
        if user_id is None:
            lines.append("ID: (unknown)")
        else:
            lines.append(f"ID: {user_id}")
        lines.append(f"Username: {cls._format_username(username)}")
        if full_name:
            lines.append(f"Name: {full_name}")
        return "\n".join(lines)

    @staticmethod
    def _has_forward_metadata(message) -> bool:
        return any(
            getattr(message, attr, None) is not None
            for attr in ("forward_origin", "forward_from", "forward_sender_name")
        )

    @classmethod
    def _render_forward_origin_section(cls, message) -> str | None:
        forward_origin = getattr(message, "forward_origin", None)
        if forward_origin is not None:
            origin_user = getattr(forward_origin, "user", None)
            if origin_user is not None:
                return cls._render_user_section("Original author:", origin_user)

            sender_name = getattr(forward_origin, "sender_user_name", None)
            if sender_name:
                return f"Original author:\nID: (hidden)\nName: {sender_name}"

            origin_chat = getattr(forward_origin, "chat", None)
            if origin_chat is not None:
                title = (
                    getattr(origin_chat, "title", None)
                    or getattr(origin_chat, "username", None)
                    or "(unknown)"
                )
                lines = ["Original source chat:", f"Title: {title}"]
                chat_username = getattr(origin_chat, "username", None)
                if chat_username:
                    lines.append(f"Username: @{chat_username}")
                chat_id = getattr(origin_chat, "id", None)
                if chat_id is not None:
                    lines.append(f"ID: {chat_id}")
                author_signature = getattr(forward_origin, "author_signature", None)
                if author_signature:
                    lines.append(f"Author: {author_signature}")
                return "\n".join(lines)

        forward_from = getattr(message, "forward_from", None)
        if forward_from is not None:
            return cls._render_user_section("Original author:", forward_from)

        forward_sender_name = getattr(message, "forward_sender_name", None)
        if forward_sender_name:
            return f"Original author:\nID: (hidden)\nName: {forward_sender_name}"

        return None

    @staticmethod
    def _render_contact_section(contact) -> str:
        lines = ["Contact in message:"]
        contact_user_id = getattr(contact, "user_id", None)
        if contact_user_id is None:
            lines.append("ID: (not linked)")
        else:
            lines.append(f"ID: {contact_user_id}")
        first_name = getattr(contact, "first_name", None)
        last_name = getattr(contact, "last_name", None)
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()
        if full_name:
            lines.append(f"Name: {full_name}")
        phone = getattr(contact, "phone_number", None)
        if phone:
            lines.append(f"Phone: {phone}")
        return "\n".join(lines)

    def _is_command_runtime_available(self, command_name: str) -> bool:
        if command_name in {"set", "settings", "settings_raw"}:
            return self._user_settings_store is not None
        if command_name in {"grant", "revoke", "role_add", "role_assign", "user_roles", "user_permissions"}:
            return self._permission_admin is not None
        if command_name in {"terminal", "exit"}:
            return self._terminal_executor is not None
        if command_name == "mpc":
            return self._mpc_controller is not None
        if command_name == "player":
            return self._media_controller is not None or self._output_controller is not None
        return True

    async def _build_start_command_lines(self, user_id: int, locale: str) -> list[str]:
        lines: list[str] = []
        has_assistant_access = await self._has_permission(user_id, "general", "assistant")

        for item in START_COMMAND_HELP:
            command_name = str(item.get("name", "")).strip()
            if not command_name:
                continue
            if not self._is_command_runtime_available(command_name):
                continue
            if bool(item.get("requires_assistant")) and not has_assistant_access:
                continue
            if not await self._has_permission(
                user_id=user_id,
                permission_type="command",
                name=command_name,
            ):
                continue

            description_key = str(item.get("description_key", "")).strip()
            description = self._t(description_key, locale=locale) if description_key else ""
            usage = str(item.get("usage", "")).strip()
            line = f"/{command_name} - {description}" if description else f"/{command_name}"
            lines.append(line)
            if usage and usage != f"/{command_name}":
                lines.append(f"  usage: {usage}")

        return lines

    async def _build_start_message(self, user_id: int) -> str:
        locale = await self._resolve_user_locale(user_id)
        lines: list[str] = [self._t("start.title", locale=locale)]
        is_admin = self._admin_telegram_id is not None and user_id == self._admin_telegram_id
        if is_admin:
            lines.append(self._t("start.admin_mode", locale=locale))

        if self._permission_admin is not None:
            try:
                roles = await self._permission_admin.get_user_roles(user_id)
                roles_label = ", ".join(roles) if roles else self._t("start.roles_none", locale=locale)
                lines.append(self._t("start.roles", locale=locale, roles=roles_label))
            except Exception:
                lines.append(self._t("start.roles_unavailable", locale=locale))

        command_lines = await self._build_start_command_lines(user_id=user_id, locale=locale)
        lines.append("")
        lines.append(self._t("start.commands_header", locale=locale))
        if command_lines:
            lines.extend(command_lines)
        else:
            lines.append(self._t("start.no_commands", locale=locale))

        has_assistant_access = await self._has_permission(user_id, "general", "assistant")
        if has_assistant_access:
            lines.append("")
            lines.append(self._t("start.ai_header", locale=locale))
            lines.append(self._t("start.ai_text_message", locale=locale))

            ask_available = (
                self._is_command_runtime_available("ask")
                and await self._has_permission(user_id, "command", "ask")
            )
            if ask_available:
                lines.append(self._t("start.ai_ask_available", locale=locale))

            clear_available = (
                self._is_command_runtime_available("clear")
                and await self._has_permission(user_id, "command", "clear")
            )
            if clear_available:
                lines.append(self._t("start.ai_clear_available", locale=locale))

        return "\n".join(lines)

    @staticmethod
    def _is_truthy_value(value: str | None) -> bool:
        if value is None:
            return False
        normalized = value.strip().lower()
        return normalized in {"1", "true", "on", "yes", "enabled"}

    @staticmethod
    def _bool_to_storage_value(enabled: bool) -> str:
        return "on" if enabled else "off"

    def _normalize_settings_section_key(self, section_name: str) -> str:
        normalized = section_name.strip().lower()
        if normalized in {"", "general", "общие"}:
            return "general"
        if normalized in {"assistant", "ассистент"}:
            return "assistant"
        return normalized

    def _localize_settings_section_name(self, section_name: str, locale: str) -> str:
        section_key = self._normalize_settings_section_key(section_name)
        if section_key == "assistant":
            return self._t("settings.section.assistant", locale=locale)
        if section_key == "general":
            return self._t("settings.section.general", locale=locale)
        stripped = section_name.strip()
        if stripped:
            return stripped
        return self._t("settings.section.default", locale=locale)

    async def _has_optional_permission(
        self,
        user_id: int,
        permission_type: str | None,
        permission_name: str | None,
    ) -> bool:
        if not permission_type or not permission_name:
            return True
        return await self._has_permission(user_id, permission_type, permission_name)

    async def _get_visible_settings_sections(
        self,
        user_id: int,
        ui_only: bool,
        locale: str,
    ) -> list[tuple[str, list[_VisibleSetting]]]:
        store = self._user_settings_store
        if store is None:
            return []

        definitions = await store.get_setting_definitions(locale=locale)
        values_map = await store.get_all_settings(user_id)
        grouped: dict[str, list[_VisibleSetting]] = {}
        section_labels: dict[str, str] = {}

        for definition in definitions:
            if ui_only and not definition.is_shown_in_ui:
                continue

            if not await self._has_optional_permission(
                user_id,
                definition.read_permission_type,
                definition.read_permission_name,
            ):
                continue

            can_write = await self._has_optional_permission(
                user_id,
                definition.write_permission_type,
                definition.write_permission_name,
            )

            options: tuple[SettingChoiceOption, ...] = ()
            if definition.value_type == "choice":
                raw_options = await store.get_setting_choice_options(
                    definition.key,
                    locale=locale,
                )
                visible_options: list[SettingChoiceOption] = []
                for option in raw_options:
                    if await self._has_optional_permission(
                        user_id,
                        option.permission_type,
                        option.permission_name,
                    ):
                        visible_options.append(option)
                if definition.key == "llm_model":
                    active_provider = self._resolve_active_llm_provider(
                        values_map=values_map,
                        llm_model_value=values_map.get(definition.key),
                    )
                    if active_provider:
                        exact_matches: list[SettingChoiceOption] = []
                        ambiguous: list[SettingChoiceOption] = []
                        for option in visible_options:
                            provider_name = self._extract_model_provider_from_option(option)
                            if provider_name is None:
                                ambiguous.append(option)
                            elif provider_name == active_provider:
                                exact_matches.append(option)
                        if exact_matches:
                            visible_options = [*exact_matches, *ambiguous]
                        else:
                            visible_options = ambiguous
                options = tuple(visible_options)

            section_key = self._normalize_settings_section_key(definition.section)
            section_name = section_labels.setdefault(
                section_key,
                self._localize_settings_section_name(definition.section, locale=locale),
            )
            grouped.setdefault(section_key, []).append(
                _VisibleSetting(
                    key=definition.key,
                    value_type=definition.value_type,
                    section=section_name,
                    title=definition.title,
                    description=definition.description,
                    current_value=values_map.get(definition.key),
                    can_write=can_write,
                    options=options,
                )
            )

        sections: list[tuple[str, list[_VisibleSetting]]] = []
        for section_key in sorted(grouped.keys(), key=lambda item: section_labels[item].lower()):
            settings_list = sorted(
                grouped[section_key],
                key=lambda item: (item.title.lower(), item.key),
            )
            if settings_list:
                sections.append((section_labels[section_key], settings_list))
        return sections

    def _settings_home_keyboard(self, sections: list[tuple[str, list[_VisibleSetting]]]) -> InlineKeyboardMarkup | None:
        if not sections:
            return None
        rows: list[list[InlineKeyboardButton]] = []
        for index, (section_name, settings_list) in enumerate(sections):
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{section_name} ({len(settings_list)})",
                        callback_data=f"settings:section:{index}",
                    )
                ]
            )
        return InlineKeyboardMarkup(rows)

    def _render_settings_home_text(self, sections: list[tuple[str, list[_VisibleSetting]]], locale: str) -> str:
        if not sections:
            return self._t("settings.home.empty", locale=locale)
        lines = [self._t("settings.home.title", locale=locale)]
        for section_name, settings_list in sections:
            lines.append(f"- {section_name}: {len(settings_list)}")
        lines.append("")
        lines.append(self._t("settings.home.choose_section", locale=locale))
        return "\n".join(lines)

    def _format_setting_value(self, setting: _VisibleSetting, locale: str) -> str:
        if setting.value_type == "bool":
            return "ON" if TelegramHandlers._is_truthy_value(setting.current_value) else "OFF"
        if setting.current_value is None or not setting.current_value:
            return self._t("settings.value.not_set", locale=locale)
        return setting.current_value

    @staticmethod
    def _option_display_name(option: SettingChoiceOption) -> str:
        return option.display_name or option.name

    @staticmethod
    def _extract_model_provider(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or ":" not in normalized:
            return None
        provider, _ = normalized.split(":", 1)
        normalized_provider = provider.strip().lower()
        return normalized_provider or None

    @staticmethod
    def _extract_model_provider_from_permission(permission_name: str | None) -> str | None:
        if permission_name is None:
            return None
        normalized = permission_name.strip().lower()
        prefix = "llm.model."
        if not normalized.startswith(prefix):
            return None
        tail = normalized[len(prefix) :]
        if ":" not in tail:
            return None
        provider, _ = tail.split(":", 1)
        provider_name = provider.strip()
        return provider_name or None

    def _extract_model_provider_from_option(self, option: SettingChoiceOption) -> str | None:
        by_name = self._extract_model_provider(option.name)
        if by_name is not None:
            return by_name

        by_permission = self._extract_model_provider_from_permission(option.permission_name)
        if by_permission is not None:
            return by_permission

        normalized_description = option.description.strip().lower()
        if normalized_description in {"openai", "ollama", "mock"}:
            return normalized_description

        return None

    def _resolve_active_llm_provider(
        self,
        values_map: dict[str, str],
        llm_model_value: str | None,
    ) -> str | None:
        selected_provider = values_map.get("llm_provider", "").strip().lower()
        if selected_provider:
            return selected_provider
        return self._extract_model_provider(llm_model_value)

    def _render_setting_text(
        self,
        setting: _VisibleSetting,
        setting_index: int,
        total_settings: int,
        locale: str,
    ) -> str:
        lines = [f"{setting.title} ({setting_index + 1}/{total_settings})"]
        lines.append(self._t("settings.page.key", locale=locale, key=setting.key))
        lines.append(
            self._t(
                "settings.page.current_value",
                locale=locale,
                value=self._format_setting_value(setting, locale=locale),
            )
        )
        if setting.description:
            lines.append("")
            lines.append(setting.description)

        if setting.value_type == "choice":
            lines.append("")
            lines.append(self._t("settings.page.options", locale=locale))
            if setting.options:
                for option in setting.options:
                    option_line = f"- {self._option_display_name(option)}"
                    if option.description:
                        option_line += f": {option.description}"
                    lines.append(option_line)
            else:
                lines.append(self._t("settings.page.option_empty", locale=locale))
        elif setting.value_type == "text":
            lines.append("")
            lines.append(self._t("settings.page.text_hint", locale=locale))

        return "\n".join(lines)

    def _settings_nav_row(
        self,
        section_index: int,
        setting_index: int,
        total_settings: int,
        locale: str,
    ) -> list[InlineKeyboardButton]:
        row: list[InlineKeyboardButton] = []
        if setting_index > 0:
            row.append(
                InlineKeyboardButton(
                    "⬅",
                    callback_data=f"settings:view:{section_index}:{setting_index - 1}",
                )
            )
        row.append(
            InlineKeyboardButton(
                self._t("settings.nav.sections", locale=locale),
                callback_data=SETTINGS_HOME,
            )
        )
        if setting_index < total_settings - 1:
            row.append(
                InlineKeyboardButton(
                    "➡",
                    callback_data=f"settings:view:{section_index}:{setting_index + 1}",
                )
            )
        return row

    def _settings_setting_keyboard(
        self,
        setting: _VisibleSetting,
        section_index: int,
        setting_index: int,
        total_settings: int,
        locale: str,
    ) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if setting.can_write:
            if setting.value_type == "bool":
                enabled = self._is_truthy_value(setting.current_value)
                icon = "✅" if enabled else "❌"
                state = "ON" if enabled else "OFF"
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"{icon} {state}",
                            callback_data=f"settings:toggle:{section_index}:{setting_index}",
                        )
                    ]
                )
            elif setting.value_type == "choice":
                for option_index, option in enumerate(setting.options):
                    mark = "✅ " if option.name == (setting.current_value or "") else ""
                    rows.append(
                        [
                            InlineKeyboardButton(
                                f"{mark}{self._option_display_name(option)}",
                                callback_data=(
                                    f"settings:choice:{section_index}:{setting_index}:{option_index}"
                                ),
                            )
                        ]
                    )
            elif setting.value_type == "text":
                text_row = [
                    InlineKeyboardButton(
                        f"✍️ {self._t('settings.nav.enter_value', locale=locale)}",
                        callback_data=f"settings:text:{section_index}:{setting_index}",
                    )
                ]
                if setting.current_value is not None and setting.current_value != "":
                    text_row.append(
                        InlineKeyboardButton(
                            f"🗑 {self._t('settings.nav.clear', locale=locale)}",
                            callback_data=f"settings:text_clear:{section_index}:{setting_index}",
                        )
                    )
                rows.append(text_row)

        rows.append(self._settings_nav_row(section_index, setting_index, total_settings, locale=locale))
        return InlineKeyboardMarkup(rows)

    async def _resolve_setting_page(
        self,
        user_id: int,
        section_index: int,
        setting_index: int,
        locale: str,
    ) -> tuple[str, InlineKeyboardMarkup] | None:
        sections = await self._get_visible_settings_sections(
            user_id=user_id,
            ui_only=True,
            locale=locale,
        )
        if section_index < 0 or section_index >= len(sections):
            return None
        _, settings_list = sections[section_index]
        if setting_index < 0 or setting_index >= len(settings_list):
            return None
        setting = settings_list[setting_index]
        text = self._render_setting_text(
            setting=setting,
            setting_index=setting_index,
            total_settings=len(settings_list),
            locale=locale,
        )
        markup = self._settings_setting_keyboard(
            setting=setting,
            section_index=section_index,
            setting_index=setting_index,
            total_settings=len(settings_list),
            locale=locale,
        )
        return text, markup

    async def _send_settings_home_message(self, update: Update) -> None:
        if not update.effective_message or not update.effective_user:
            return
        locale = await self._resolve_user_locale(update.effective_user.id)
        if not self._user_settings_store:
            await update.effective_message.reply_text(
                self._t("errors.settings_store_unconfigured", locale=locale)
            )
            return

        sections = await self._get_visible_settings_sections(
            user_id=update.effective_user.id,
            ui_only=True,
            locale=locale,
        )
        text = self._render_settings_home_text(sections, locale=locale)
        markup = self._settings_home_keyboard(sections)
        await update.effective_message.reply_text(text, reply_markup=markup)

    async def _edit_settings_home_message(self, query, user_id: int, locale: str) -> None:
        sections = await self._get_visible_settings_sections(
            user_id=user_id,
            ui_only=True,
            locale=locale,
        )
        text = self._render_settings_home_text(sections, locale=locale)
        markup = self._settings_home_keyboard(sections)
        try:
            await query.edit_message_text(text=text, reply_markup=markup)
        except BadRequest:
            pass

    async def _edit_setting_page_message(
        self,
        query,
        user_id: int,
        section_index: int,
        setting_index: int,
        locale: str,
    ) -> None:
        resolved = await self._resolve_setting_page(
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        if resolved is None:
            await self._answer_callback(
                query,
                self._t("settings.callback.list_changed", locale=locale),
                show_alert=True,
            )
            return
        text, markup = resolved
        try:
            await query.edit_message_text(text=text, reply_markup=markup)
        except BadRequest:
            pass

    async def _toggle_bool_setting(
        self,
        user_id: int,
        section_index: int,
        setting_index: int,
        locale: str,
    ) -> str | None:
        resolved = await self._resolve_setting_for_write(
            user_id,
            section_index,
            setting_index,
            locale=locale,
        )
        if resolved is None:
            return None
        setting = resolved
        if setting.value_type != "bool":
            return None
        current = self._is_truthy_value(setting.current_value)
        new_value = self._bool_to_storage_value(not current)
        if not self._user_settings_store:
            return None
        await self._user_settings_store.set_setting(user_id=user_id, key=setting.key, value=new_value)
        return new_value

    async def _set_choice_setting_value(
        self,
        user_id: int,
        section_index: int,
        setting_index: int,
        option_index: int,
        locale: str,
    ) -> SettingChoiceOption | None:
        resolved = await self._resolve_setting_for_write(
            user_id,
            section_index,
            setting_index,
            locale=locale,
        )
        if resolved is None:
            return None
        setting = resolved
        if setting.value_type != "choice":
            return None
        if option_index < 0 or option_index >= len(setting.options):
            return None
        option = setting.options[option_index]
        if not self._user_settings_store:
            return None
        await self._user_settings_store.set_setting(user_id=user_id, key=setting.key, value=option.name)
        if setting.key == "llm_provider":
            await self._sync_llm_model_with_provider(
                user_id=user_id,
                provider_name=option.name,
                locale=locale,
            )
        return option

    async def _sync_llm_model_with_provider(
        self,
        user_id: int,
        provider_name: str,
        locale: str,
    ) -> None:
        if not self._user_settings_store:
            return
        target_provider = provider_name.strip().lower()
        if not target_provider:
            return

        sections = await self._get_visible_settings_sections(
            user_id=user_id,
            ui_only=True,
            locale=locale,
        )
        llm_model_setting: _VisibleSetting | None = None
        for _, settings_list in sections:
            for item in settings_list:
                if item.key == "llm_model":
                    llm_model_setting = item
                    break
            if llm_model_setting is not None:
                break

        if llm_model_setting is None:
            return
        if self._extract_model_provider(llm_model_setting.current_value) == target_provider:
            return

        exact_matches: list[SettingChoiceOption] = []
        ambiguous: list[SettingChoiceOption] = []
        for option in llm_model_setting.options:
            option_provider = self._extract_model_provider_from_option(option)
            if option_provider is None:
                ambiguous.append(option)
                continue
            if option_provider == target_provider:
                exact_matches.append(option)

        preferred = exact_matches[0] if exact_matches else (ambiguous[0] if ambiguous else None)
        if preferred is None:
            return
        await self._user_settings_store.set_setting(user_id=user_id, key="llm_model", value=preferred.name)

    async def _clear_text_setting_value(
        self,
        user_id: int,
        section_index: int,
        setting_index: int,
        locale: str,
    ) -> bool:
        resolved = await self._resolve_setting_for_write(
            user_id,
            section_index,
            setting_index,
            locale=locale,
        )
        if resolved is None:
            return False
        setting = resolved
        if setting.value_type != "text":
            return False
        if not self._user_settings_store:
            return False
        await self._user_settings_store.set_setting(user_id=user_id, key=setting.key, value="")
        return True

    async def _resolve_setting_for_write(
        self,
        user_id: int,
        section_index: int,
        setting_index: int,
        locale: str,
    ) -> _VisibleSetting | None:
        sections = await self._get_visible_settings_sections(
            user_id=user_id,
            ui_only=True,
            locale=locale,
        )
        if section_index < 0 or section_index >= len(sections):
            return None
        _, settings_list = sections[section_index]
        if setting_index < 0 or setting_index >= len(settings_list):
            return None
        setting = settings_list[setting_index]
        if not setting.can_write:
            return None
        return setting

    async def _start_text_setting_input(
        self,
        update: Update,
        section_index: int,
        setting_index: int,
        locale: str,
    ) -> bool:
        user = update.effective_user
        query = update.callback_query
        if user is None or query is None:
            return False
        setting = await self._resolve_setting_for_write(
            user_id=user.id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        if setting is None or setting.value_type != "text":
            return False
        self._pending_text_setting_inputs[user.id] = _PendingTextSettingInput(setting_key=setting.key)
        await self._answer_callback(
            query,
            self._t("settings.text_input.alert", locale=locale),
            show_alert=True,
        )
        if query.message:
            await query.message.reply_text(
                self._t("settings.text_input.prompt", locale=locale, key=setting.key),
                parse_mode=ParseMode.MARKDOWN,
            )
        return True

    async def _handle_pending_text_setting_input(
        self,
        update: Update,
        user_id: int,
        new_value: str,
    ) -> bool:
        pending = self._pending_text_setting_inputs.get(user_id)
        if pending is None:
            return False
        locale = await self._resolve_user_locale(user_id)
        if not self._user_settings_store or not update.effective_message:
            self._pending_text_setting_inputs.pop(user_id, None)
            return True

        definitions = await self._user_settings_store.get_setting_definitions(locale=locale)
        target_definition: SettingDefinition | None = None
        for item in definitions:
            if item.key == pending.setting_key:
                target_definition = item
                break

        if target_definition is None or target_definition.value_type != "text":
            self._pending_text_setting_inputs.pop(user_id, None)
            await update.effective_message.reply_text(
                self._t("settings.text_input.unavailable", locale=locale)
            )
            return True

        can_write = await self._has_optional_permission(
            user_id,
            target_definition.write_permission_type,
            target_definition.write_permission_name,
        )
        if not can_write:
            self._pending_text_setting_inputs.pop(user_id, None)
            await update.effective_message.reply_text(
                self._t("settings.text_input.no_permission", locale=locale)
            )
            return True

        await self._user_settings_store.set_setting(
            user_id=user_id,
            key=pending.setting_key,
            value=new_value,
        )
        self._pending_text_setting_inputs.pop(user_id, None)
        await update.effective_message.reply_text(
            self._t(
                "settings.text_input.saved",
                locale=locale,
                key=pending.setting_key,
                value=new_value,
            )
        )
        return True

    async def _reject_if_permission_admin_unavailable(self, update: Update) -> bool:
        if self._permission_admin is not None:
            return False
        if update.effective_message:
            locale = None
            if update.effective_user:
                locale = await self._resolve_user_locale(update.effective_user.id)
            await update.effective_message.reply_text(
                self._t("errors.permission_admin_unavailable", locale=locale)
            )
        return True

    async def _answer_callback(self, query, text: str, show_alert: bool = False) -> None:
        safe_text = text
        if len(safe_text) > 180:
            safe_text = safe_text[:177] + "..."
        try:
            await query.answer(safe_text, show_alert=show_alert)
        except BadRequest:
            # Fallback with minimal text if Telegram rejects content/length.
            fallback = "Operation failed." if show_alert else "Failed."
            await query.answer(fallback, show_alert=show_alert)

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "start"):
            return
        if not update.effective_message or not update.effective_user:
            return
        text = await self._build_start_message(user_id=update.effective_user.id)
        await update.effective_message.reply_text(text)

    async def handle_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "id"):
            return
        if not update.effective_message or not update.effective_user:
            return

        message = update.effective_message
        replied = getattr(message, "reply_to_message", None)
        if replied:
            sections: list[str] = []
            replied_from = getattr(replied, "from_user", None)
            replied_contact = getattr(replied, "contact", None)
            has_forward = self._has_forward_metadata(replied)

            if replied_from is not None:
                if has_forward:
                    sections.append(self._render_user_section("Forwarded by:", replied_from))
                elif replied_contact is not None:
                    sections.append(self._render_user_section("Contact sent by:", replied_from))
                else:
                    sections.append(self._render_user_section("Reply sender:", replied_from))

            forward_section = self._render_forward_origin_section(replied)
            if forward_section:
                sections.append(forward_section)

            if replied_contact is not None:
                sections.append(self._render_contact_section(replied_contact))

            if sections:
                await message.reply_text("\n\n".join(sections))
                return

        user = update.effective_user
        await message.reply_text(self._render_user_section("Your account:", user))

    async def handle_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "ping"):
            return
        if update.effective_message:
            await update.effective_message.reply_text("pong")

    async def handle_echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "echo"):
            return
        if not update.effective_message:
            return

        if context.args:
            text = " ".join(context.args)
        else:
            text = "Использование: /echo <текст>"
        await update.effective_message.reply_text(text)

    async def handle_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "ask"):
            return
        if await self._reject_if_no_message_permission(update, "general", "assistant"):
            return
        if not update.effective_message or not update.effective_user:
            return

        incoming_text = update.effective_message.text or ""
        user_text = incoming_text.replace("/ask", "", 1).strip()
        if not user_text:
            await update.effective_message.reply_text("Использование: /ask <вопрос>")
            return

        await self._reply_with_llm(
            user_id=update.effective_user.id,
            user_text=user_text,
            update=update,
            context=context,
        )

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if not update.effective_message or not update.effective_user:
            return

        user_text = (update.effective_message.text or "").strip()
        if not user_text:
            return

        user_id = update.effective_user.id
        if user_id in self._terminal_mode_users:
            await self._handle_terminal_command(
                update=update,
                command=user_text,
                context=context,
            )
            return

        if await self._handle_pending_text_setting_input(
            update=update,
            user_id=user_id,
            new_value=user_text,
        ):
            return

        if await self._reject_if_no_message_permission(update, "general", "assistant"):
            return

        await self._reply_with_llm(
            user_id=user_id,
            user_text=user_text,
            update=update,
            context=context,
        )

    async def handle_terminal_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "terminal"):
            return
        if not update.effective_message or not update.effective_user:
            return

        if not self._terminal_executor:
            await update.effective_message.reply_text("Терминал недоступен в текущем окружении.")
            return

        user_id = update.effective_user.id
        try:
            await self._terminal_executor.start_session(user_id)
        except Exception as exc:
            await update.effective_message.reply_text(f"Не удалось запустить терминал: {exc}")
            return
        self._terminal_mode_users.add(user_id)
        shell = self._terminal_executor.describe_shell()
        await update.effective_message.reply_text(
            f"Terminal mode ON ({shell}). Отправляй команды как обычные сообщения. /exit для выхода."
        )

    async def handle_exit_terminal_mode(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "exit"):
            return
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        if user_id in self._terminal_mode_users:
            self._terminal_mode_users.discard(user_id)
            if self._terminal_executor and self._terminal_executor.is_session_active(user_id):
                try:
                    await self._terminal_executor.close_session(user_id)
                except Exception:
                    pass
            await update.effective_message.reply_text("Terminal mode OFF.")
            return
        await update.effective_message.reply_text("Terminal mode already OFF.")

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "cancel"):
            return
        if not update.effective_message or not update.effective_user:
            return

        user_id = update.effective_user.id
        locale = await self._resolve_user_locale(user_id)
        pending = self._pending_text_setting_inputs.pop(user_id, None)
        if pending is None:
            await update.effective_message.reply_text(self._t("cancel.none", locale=locale))
            return
        await update.effective_message.reply_text(
            self._t("cancel.done", locale=locale, key=pending.setting_key),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _handle_terminal_command(
        self,
        update: Update,
        command: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not update.effective_message:
            return
        if not self._terminal_executor:
            await update.effective_message.reply_text("Терминал недоступен.")
            return

        bot = getattr(context, "bot", None)
        chat = getattr(update, "effective_chat", None)
        if bot is not None and chat is not None:
            try:
                await bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
            except Exception:
                pass

        result = await self._terminal_executor.run_command(update.effective_user.id, command)
        for chunk in self._format_terminal_result_chunks(result):
            await update.effective_message.reply_text(chunk)

    @staticmethod
    def _format_terminal_result_chunks(
        result: TerminalCommandResult, chunk_size: int = 3500
    ) -> list[str]:
        header = f"[{result.shell}] $ {result.command}"
        parts = [header]
        if result.timed_out and result.error:
            parts.append(result.error)
        elif result.error:
            parts.append(f"Execution error: {result.error}")
        elif result.running:
            parts.append("Interactive process is running. Send next input or /exit to stop terminal mode.")
            if result.stdout.strip():
                parts.append(result.stdout.rstrip())
            if result.stderr.strip():
                parts.append("[stderr]")
                parts.append(result.stderr.rstrip())
        else:
            parts.append(f"Exit code: {result.exit_code}")
            if result.stdout.strip():
                parts.append(result.stdout.rstrip())
            if result.stderr.strip():
                parts.append("[stderr]")
                parts.append(result.stderr.rstrip())

        full_text = "\n".join(parts).strip()
        if not full_text:
            full_text = "(no output)"

        chunks: list[str] = []
        while full_text:
            chunks.append(full_text[:chunk_size])
            full_text = full_text[chunk_size:]
        return chunks

    async def handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "clear"):
            return
        if not update.effective_message or not update.effective_user:
            return

        locale = await self._resolve_user_locale(update.effective_user.id)
        await self._assistant_service.clear_context(user_id=update.effective_user.id)
        await update.effective_message.reply_text(self._t("clear.done", locale=locale))

    async def handle_set_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "set"):
            return
        if not update.effective_message or not update.effective_user:
            return
        locale = await self._resolve_user_locale(update.effective_user.id)
        if not self._user_settings_store:
            await update.effective_message.reply_text(
                self._t("errors.settings_store_unconfigured", locale=locale)
            )
            return
        if len(context.args) < 2:
            await update.effective_message.reply_text(self._t("set.usage", locale=locale))
            return

        key = context.args[0].strip().lower()
        value = " ".join(context.args[1:]).strip()
        if not key or not value:
            await update.effective_message.reply_text(self._t("set.usage", locale=locale))
            return

        await self._user_settings_store.set_setting(
            user_id=update.effective_user.id,
            key=key,
            value=value,
        )
        await update.effective_message.reply_text(
            self._t("set.saved", locale=locale, key=key, value=value)
        )

    async def handle_settings_raw(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "settings_raw"):
            return
        if not update.effective_message or not update.effective_user:
            return
        locale = await self._resolve_user_locale(update.effective_user.id)
        if not self._user_settings_store:
            await update.effective_message.reply_text(
                self._t("errors.settings_store_unconfigured", locale=locale)
            )
            return

        settings_map = await self._user_settings_store.get_all_settings(update.effective_user.id)
        if not settings_map:
            await update.effective_message.reply_text(self._t("settings_raw.empty", locale=locale))
            return

        lines = [self._t("settings_raw.header", locale=locale)]
        for key, value in sorted(settings_map.items()):
            lines.append(f"- {key}: {value}")
        await update.effective_message.reply_text("\n".join(lines))

    async def handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "settings"):
            return
        await self._send_settings_home_message(update)

    async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        query = update.callback_query
        if not query:
            return
        if await self._reject_callback_if_not_allowed(update):
            return
        if await self._reject_if_no_callback_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_callback_permission(update, "command", "settings"):
            return
        if not self._user_settings_store or not update.effective_user:
            locale = None
            if update.effective_user:
                locale = await self._resolve_user_locale(update.effective_user.id)
            await self._answer_callback(
                query,
                self._t("errors.settings_store_unconfigured", locale=locale),
                show_alert=True,
            )
            return

        data = query.data or ""
        parts = data.split(":")
        if len(parts) < 2 or parts[0] != "settings":
            locale = await self._resolve_user_locale(update.effective_user.id)
            await self._answer_callback(
                query,
                self._t("settings.callback.unknown_action", locale=locale),
                show_alert=True,
            )
            return

        user_id = update.effective_user.id
        locale = await self._resolve_user_locale(user_id)
        action = parts[1]

        if action == "home":
            await self._edit_settings_home_message(query=query, user_id=user_id, locale=locale)
            await self._answer_callback(query, self._t("settings.callback.ready", locale=locale))
            return

        if action == "section":
            if len(parts) != 3:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_section_request", locale=locale),
                    show_alert=True,
                )
                return
            try:
                section_index = int(parts[2])
            except ValueError:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_section_index", locale=locale),
                    show_alert=True,
                )
                return
            await self._edit_setting_page_message(
                query=query,
                user_id=user_id,
                section_index=section_index,
                setting_index=0,
                locale=locale,
            )
            await self._answer_callback(query, self._t("settings.callback.ready", locale=locale))
            return

        if action == "view":
            if len(parts) != 4:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_view_request", locale=locale),
                    show_alert=True,
                )
                return
            try:
                section_index = int(parts[2])
                setting_index = int(parts[3])
            except ValueError:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_setting_index", locale=locale),
                    show_alert=True,
                )
                return
            await self._edit_setting_page_message(
                query=query,
                user_id=user_id,
                section_index=section_index,
                setting_index=setting_index,
                locale=locale,
            )
            await self._answer_callback(query, self._t("settings.callback.ready", locale=locale))
            return

        if action == "toggle":
            if len(parts) != 4:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_toggle_request", locale=locale),
                    show_alert=True,
                )
                return
            try:
                section_index = int(parts[2])
                setting_index = int(parts[3])
            except ValueError:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_setting_index", locale=locale),
                    show_alert=True,
                )
                return
            new_value = await self._toggle_bool_setting(
                user_id=user_id,
                section_index=section_index,
                setting_index=setting_index,
                locale=locale,
            )
            if new_value is None:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.write_forbidden", locale=locale),
                    show_alert=True,
                )
                return
            await self._edit_setting_page_message(
                query=query,
                user_id=user_id,
                section_index=section_index,
                setting_index=setting_index,
                locale=locale,
            )
            state = "ON" if self._is_truthy_value(new_value) else "OFF"
            await self._answer_callback(
                query,
                self._t("settings.callback.saved_state", locale=locale, state=state),
            )
            return

        if action == "choice":
            if len(parts) != 5:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_choice_request", locale=locale),
                    show_alert=True,
                )
                return
            try:
                section_index = int(parts[2])
                setting_index = int(parts[3])
                option_index = int(parts[4])
            except ValueError:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_choice_index", locale=locale),
                    show_alert=True,
                )
                return
            chosen = await self._set_choice_setting_value(
                user_id=user_id,
                section_index=section_index,
                setting_index=setting_index,
                option_index=option_index,
                locale=locale,
            )
            if chosen is None:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.option_unavailable", locale=locale),
                    show_alert=True,
                )
                return
            await self._edit_setting_page_message(
                query=query,
                user_id=user_id,
                section_index=section_index,
                setting_index=setting_index,
                locale=locale,
            )
            await self._answer_callback(
                query,
                self._t(
                    "settings.callback.saved_value",
                    locale=locale,
                    value=self._option_display_name(chosen),
                ),
            )
            return

        if action == "text":
            if len(parts) != 4:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_text_request", locale=locale),
                    show_alert=True,
                )
                return
            try:
                section_index = int(parts[2])
                setting_index = int(parts[3])
            except ValueError:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_setting_index", locale=locale),
                    show_alert=True,
                )
                return
            started = await self._start_text_setting_input(
                update=update,
                section_index=section_index,
                setting_index=setting_index,
                locale=locale,
            )
            if not started:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.write_forbidden", locale=locale),
                    show_alert=True,
                )
            return

        if action == "text_clear":
            if len(parts) != 4:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_text_clear_request", locale=locale),
                    show_alert=True,
                )
                return
            try:
                section_index = int(parts[2])
                setting_index = int(parts[3])
            except ValueError:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.invalid_setting_index", locale=locale),
                    show_alert=True,
                )
                return
            cleared = await self._clear_text_setting_value(
                user_id=user_id,
                section_index=section_index,
                setting_index=setting_index,
                locale=locale,
            )
            if not cleared:
                await self._answer_callback(
                    query,
                    self._t("settings.callback.write_forbidden", locale=locale),
                    show_alert=True,
                )
                return
            await self._edit_setting_page_message(
                query=query,
                user_id=user_id,
                section_index=section_index,
                setting_index=setting_index,
                locale=locale,
            )
            await self._answer_callback(query, self._t("settings.callback.cleared", locale=locale))
            return

        await self._answer_callback(
            query,
            self._t("settings.callback.unknown_action", locale=locale),
            show_alert=True,
        )

    async def handle_role_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "role_add"):
            return
        if not update.effective_message:
            return
        if await self._reject_if_permission_admin_unavailable(update):
            return
        admin = self._permission_admin
        if admin is None:
            return
        if len(context.args) != 1:
            await update.effective_message.reply_text("Использование: /role_add <role_name>")
            return

        role_name = context.args[0].strip().lower()
        if not role_name:
            await update.effective_message.reply_text("Использование: /role_add <role_name>")
            return
        try:
            await admin.create_role(role_name)
        except Exception as exc:
            await update.effective_message.reply_text(f"Ошибка role_add: {exc}")
            return
        await update.effective_message.reply_text(f"Role created: {role_name}")

    async def handle_role_assign(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "role_assign"):
            return
        if not update.effective_message:
            return
        if await self._reject_if_permission_admin_unavailable(update):
            return
        admin = self._permission_admin
        if admin is None:
            return
        if len(context.args) != 2:
            await update.effective_message.reply_text(
                "Использование: /role_assign <user_id> <role_name>"
            )
            return

        try:
            target_user_id = int(context.args[0].strip())
        except ValueError:
            await update.effective_message.reply_text("user_id должен быть целым числом.")
            return
        role_name = context.args[1].strip().lower()
        if not role_name:
            await update.effective_message.reply_text(
                "Использование: /role_assign <user_id> <role_name>"
            )
            return
        try:
            await admin.assign_role(
                user_id=target_user_id,
                role_name=role_name,
            )
        except Exception as exc:
            await update.effective_message.reply_text(f"Ошибка role_assign: {exc}")
            return
        await update.effective_message.reply_text(
            f"Role assigned: user={target_user_id}, role={role_name}"
        )

    async def handle_grant(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "grant"):
            return
        if not update.effective_message:
            return
        if await self._reject_if_permission_admin_unavailable(update):
            return
        admin = self._permission_admin
        if admin is None:
            return
        if len(context.args) < 4:
            await update.effective_message.reply_text(
                "Использование: /grant user <user_id> <type> <name> | /grant role <role_name> <type> <name>"
            )
            return

        target_kind = context.args[0].strip().lower()
        permission_type = self._normalize_permission_type(context.args[2])
        permission_name = " ".join(context.args[3:]).strip().lower()
        if permission_type is None:
            await update.effective_message.reply_text(
                "type должен быть одним из: general, command, assistant."
            )
            return
        if not permission_name:
            await update.effective_message.reply_text("name не должен быть пустым.")
            return

        try:
            if target_kind == "user":
                target_user_id = int(context.args[1].strip())
                await admin.set_user_permission(
                    user_id=target_user_id,
                    permission_type=permission_type,
                    name=permission_name,
                    is_active=True,
                )
                await update.effective_message.reply_text(
                    f"Granted user permission: user={target_user_id}, {permission_type}/{permission_name}"
                )
                return

            if target_kind == "role":
                role_name = context.args[1].strip().lower()
                if not role_name:
                    await update.effective_message.reply_text("role_name не должен быть пустым.")
                    return
                await admin.grant_role_permission(
                    role_name=role_name,
                    permission_type=permission_type,
                    name=permission_name,
                )
                await update.effective_message.reply_text(
                    f"Granted role permission: role={role_name}, {permission_type}/{permission_name}"
                )
                return
        except ValueError:
            await update.effective_message.reply_text("user_id должен быть целым числом.")
            return
        except Exception as exc:
            await update.effective_message.reply_text(f"Ошибка grant: {exc}")
            return

        await update.effective_message.reply_text(
            "Первый аргумент должен быть user или role."
        )

    async def handle_revoke(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "revoke"):
            return
        if not update.effective_message:
            return
        if await self._reject_if_permission_admin_unavailable(update):
            return
        admin = self._permission_admin
        if admin is None:
            return
        if len(context.args) < 4:
            await update.effective_message.reply_text(
                "Использование: /revoke user <user_id> <type> <name> | /revoke role <role_name> <type> <name>"
            )
            return

        target_kind = context.args[0].strip().lower()
        permission_type = self._normalize_permission_type(context.args[2])
        permission_name = " ".join(context.args[3:]).strip().lower()
        if permission_type is None:
            await update.effective_message.reply_text(
                "type должен быть одним из: general, command, assistant."
            )
            return
        if not permission_name:
            await update.effective_message.reply_text("name не должен быть пустым.")
            return

        try:
            if target_kind == "user":
                target_user_id = int(context.args[1].strip())
                await admin.set_user_permission(
                    user_id=target_user_id,
                    permission_type=permission_type,
                    name=permission_name,
                    is_active=False,
                )
                await update.effective_message.reply_text(
                    f"Revoked user permission: user={target_user_id}, {permission_type}/{permission_name}"
                )
                return

            if target_kind == "role":
                role_name = context.args[1].strip().lower()
                if not role_name:
                    await update.effective_message.reply_text("role_name не должен быть пустым.")
                    return
                await admin.revoke_role_permission(
                    role_name=role_name,
                    permission_type=permission_type,
                    name=permission_name,
                )
                await update.effective_message.reply_text(
                    f"Revoked role permission: role={role_name}, {permission_type}/{permission_name}"
                )
                return
        except ValueError:
            await update.effective_message.reply_text("user_id должен быть целым числом.")
            return
        except Exception as exc:
            await update.effective_message.reply_text(f"Ошибка revoke: {exc}")
            return

        await update.effective_message.reply_text(
            "Первый аргумент должен быть user или role."
        )

    async def handle_user_roles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "user_roles"):
            return
        if not update.effective_message:
            return
        if await self._reject_if_permission_admin_unavailable(update):
            return
        admin = self._permission_admin
        if admin is None:
            return
        if len(context.args) != 1:
            await update.effective_message.reply_text("Использование: /user_roles <user_id>")
            return
        try:
            target_user_id = int(context.args[0].strip())
        except ValueError:
            await update.effective_message.reply_text("user_id должен быть целым числом.")
            return

        try:
            roles = await admin.get_user_roles(target_user_id)
        except Exception as exc:
            await update.effective_message.reply_text(f"Ошибка user_roles: {exc}")
            return

        if not roles:
            await update.effective_message.reply_text(
                f"user={target_user_id}: роли не назначены."
            )
            return
        lines = [f"user={target_user_id} roles:"]
        for role in roles:
            lines.append(f"- {role}")
        await update.effective_message.reply_text("\n".join(lines))

    async def handle_user_permissions(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "user_permissions"):
            return
        if not update.effective_message:
            return
        if await self._reject_if_permission_admin_unavailable(update):
            return
        admin = self._permission_admin
        if admin is None:
            return
        if len(context.args) != 1:
            await update.effective_message.reply_text(
                "Использование: /user_permissions <user_id>"
            )
            return
        try:
            target_user_id = int(context.args[0].strip())
        except ValueError:
            await update.effective_message.reply_text("user_id должен быть целым числом.")
            return

        try:
            report = await admin.get_user_permission_report(target_user_id)
        except Exception as exc:
            await update.effective_message.reply_text(f"Ошибка user_permissions: {exc}")
            return

        user_overrides = list(report.get("user_overrides", []))
        role_permissions = list(report.get("role_permissions", []))
        effective = list(report.get("effective", []))

        lines = [f"user={target_user_id} permissions:"]
        lines.append("user_overrides:")
        if user_overrides:
            for item in user_overrides:
                lines.append(
                    f"- {item.get('type')}/{item.get('name')} = {item.get('is_active')}"
                )
        else:
            lines.append("- (none)")

        lines.append("role_permissions:")
        if role_permissions:
            for item in role_permissions:
                lines.append(
                    f"- role={item.get('role')}: {item.get('type')}/{item.get('name')}"
                )
        else:
            lines.append("- (none)")

        lines.append("effective:")
        if effective:
            for item in effective:
                lines.append(
                    f"- {item.get('type')}/{item.get('name')} = {item.get('is_active')} "
                    f"(source={item.get('source')}, roles={','.join(item.get('roles', []))})"
                )
        else:
            lines.append("- (none)")

        await update.effective_message.reply_text("\n".join(lines))

    async def _reply_with_llm(
        self,
        user_id: int,
        user_text: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not update.effective_message:
            return

        typing_task: asyncio.Task | None = None
        bot = getattr(context, "bot", None)
        chat = getattr(update, "effective_chat", None)
        chat_id = chat.id if chat else None
        if bot is not None and chat_id is not None:
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                typing_task = asyncio.create_task(
                    self._typing_heartbeat(bot=bot, chat_id=chat_id)
                )
            except Exception:
                typing_task = None

        try:
            reply = await self._assistant_service.process_text(user_id=user_id, text=user_text)
        except Exception as exc:
            await update.effective_message.reply_text(f"Ошибка LLM: {exc}")
            return
        finally:
            if typing_task:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass

        await self._send_llm_reply(update=update, text=reply.text)

    async def _typing_heartbeat(self, bot, chat_id: int) -> None:
        while True:
            await asyncio.sleep(4)
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    async def _send_llm_reply(self, update: Update, text: str) -> None:
        if not update.effective_message:
            return
        try:
            await update.effective_message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except BadRequest:
            # Fallback to plain text if model produced invalid Telegram HTML.
            await update.effective_message.reply_text(text)

    async def handle_player(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "player"):
            return
        if not update.effective_message:
            return
        await update.effective_message.reply_text(
            "Управление плеером:", reply_markup=self._player_keyboard()
        )

    async def handle_player_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        query = update.callback_query
        if not query:
            return
        if await self._reject_callback_if_not_allowed(update):
            return
        if await self._reject_if_no_callback_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_callback_permission(update, "command", "player"):
            return

        try:
            if query.data == PLAYER_OUTPUT_TOGGLE:
                if not self._output_controller:
                    await self._answer_callback(
                        query,
                        "Output controller is not configured.",
                        show_alert=True,
                    )
                    return
                enabled = self._output_controller.toggle_output()
                state = "ON" if enabled else "OFF"
                await self._answer_callback(query, f"Speakers output: {state}")
                return

            if not self._media_controller:
                await self._answer_callback(query, "Медиа-контроль не настроен.", show_alert=True)
                return

            if query.data == PLAYER_PLAY_PAUSE:
                self._media_controller.play_pause()
                await self._answer_callback(query, "Play/Pause")
                return
            if query.data == PLAYER_PREVIOUS:
                self._media_controller.previous_track()
                await self._answer_callback(query, "Previous track")
                return
            if query.data == PLAYER_NEXT:
                self._media_controller.next_track()
                await self._answer_callback(query, "Next track")
                return
        except Exception as exc:
            if query.data == PLAYER_OUTPUT_TOGGLE:
                await self._answer_callback(
                    query,
                    f"Output error: {exc}",
                    show_alert=True,
                )
                return
            await self._answer_callback(query, "Ошибка отправки клавиши.", show_alert=True)
            return

        await self._answer_callback(query, "Неизвестная кнопка.")

    async def handle_mpc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._reject_if_not_allowed(update):
            return
        if await self._reject_if_no_message_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_message_permission(update, "command", "mpc"):
            return
        if not update.effective_message:
            return
        await update.effective_message.reply_text(
            "MPC-HC: управление дорожками", reply_markup=self._mpc_keyboard()
        )

    async def handle_mpc_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        query = update.callback_query
        if not query:
            return
        if await self._reject_callback_if_not_allowed(update):
            return
        if await self._reject_if_no_callback_permission(update, "general", "usage"):
            return
        if await self._reject_if_no_callback_permission(update, "command", "mpc"):
            return
        if not self._mpc_controller:
            await self._answer_callback(query, "MPC-контроллер не настроен.", show_alert=True)
            return

        try:
            ok = False
            message = "Неизвестная команда."
            if query.data == MPC_AUDIO_PREVIOUS:
                ok = self._mpc_controller.audio_previous()
                message = "Аудио: предыдущая дорожка"
            elif query.data == MPC_AUDIO_NEXT:
                ok = self._mpc_controller.audio_next()
                message = "Аудио: следующая дорожка"
            elif query.data == MPC_SUBTITLE_PREVIOUS:
                ok = self._mpc_controller.subtitle_previous()
                message = "Субтитры: предыдущая дорожка"
            elif query.data == MPC_SUBTITLE_NEXT:
                ok = self._mpc_controller.subtitle_next()
                message = "Субтитры: следующая дорожка"
            elif query.data == MPC_AUDIO_RU:
                ok = self._mpc_controller.audio_set_language("ru")
                message = "Аудио: переключено на RU"
            elif query.data == MPC_AUDIO_EN:
                ok = self._mpc_controller.audio_set_language("en")
                message = "Аудио: переключено на EN"
            elif query.data == MPC_SUBTITLE_RU:
                ok = self._mpc_controller.subtitle_set_language("ru")
                message = "Субтитры: переключено на RU"
            elif query.data == MPC_SUBTITLE_EN:
                ok = self._mpc_controller.subtitle_set_language("en")
                message = "Субтитры: переключено на EN"

            if ok:
                await self._answer_callback(query, message)
            else:
                await self._answer_callback(
                    query,
                    "MPC-HC не найден, файл не открыт или нужная дорожка отсутствует.",
                    show_alert=True,
                )
        except Exception:
            await self._answer_callback(query, "Ошибка управления MPC-HC.", show_alert=True)
