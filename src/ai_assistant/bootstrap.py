from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from ai_assistant.bootstrap_infra import (
    build_media_controller,
    build_mpc_controller,
    build_output_controller,
    build_permission_checker,
    build_remote_device_service,
    build_remote_ws_hub,
    build_terminal_executor,
    build_translation_service,
    build_user_settings_store,
)
from ai_assistant.bootstrap_llm import (
    build_available_provider_names,
    build_llm_provider,
    build_llm_provider_instances,
    build_llm_settings_overrides,
)
from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import ChannelModule
from ai_assistant.core.service import AssistantService
from ai_assistant.modules.telegram.bot import TelegramBotModule
from ai_assistant.modules.telegram.handlers import TelegramHandlers
from ai_assistant.providers.memory.in_memory_store import InMemoryStore
from ai_assistant.providers.system.assistant_command_executor import SystemAssistantCommandExecutor
from ai_assistant.providers.system.hybrid_command_executor import HybridAssistantCommandExecutor

logger = logging.getLogger(__name__)


def build_channel_module(settings: Settings) -> ChannelModule:
    logger.info("Building channel module for channel=%s", settings.assistant_channel)
    memory_store = InMemoryStore()
    translation_service = build_translation_service(settings)
    permission_checker = build_permission_checker(settings)

    available_providers = build_available_provider_names(settings)
    provider_instances = build_llm_provider_instances(settings, available_providers)
    enabled_provider_names = tuple(provider_instances.keys())
    logger.info("Enabled LLM providers: %s", ", ".join(enabled_provider_names))

    (
        extra_setting_definitions,
        extra_choice_options,
        extra_translations,
        extra_choice_translations,
    ) = build_llm_settings_overrides(settings, enabled_provider_names)

    user_settings_store = build_user_settings_store(
        settings,
        extra_definitions=extra_setting_definitions,
        extra_choice_options=extra_choice_options,
        extra_translations=extra_translations,
        extra_choice_translations=extra_choice_translations,
    )
    llm_provider = build_llm_provider(
        settings,
        user_settings_store=user_settings_store,
        provider_instances=provider_instances,
        permission_checker=permission_checker,
    )

    media_controller = build_media_controller()
    mpc_controller = build_mpc_controller()
    output_controller = build_output_controller(settings)
    terminal_executor = build_terminal_executor(settings)
    remote_device_service = build_remote_device_service(settings)
    remote_ws_hub = build_remote_ws_hub(settings, remote_device_service)

    local_command_executor = SystemAssistantCommandExecutor(
        media_controller=media_controller,
        mpc_controller=mpc_controller,
        output_controller=output_controller,
        active_skill_ids=settings.assistant_active_skills,
        skill_factories=settings.assistant_skill_factories,
    )
    command_executor = HybridAssistantCommandExecutor(
        local_executor=local_command_executor,
        remote_ws_hub=remote_ws_hub,
    )

    assistant_service = AssistantService(
        llm_provider=llm_provider,
        memory_store=memory_store,
        command_executor=command_executor,
        permission_checker=permission_checker,
        admin_telegram_id=settings.admin_telegram_id,
        user_settings_store=user_settings_store,
    )

    channel = settings.assistant_channel.lower()
    if channel == "telegram":
        logger.info("Initializing Telegram channel module")
        handlers = TelegramHandlers(
            assistant_service=assistant_service,
            user_settings_store=user_settings_store,
            media_controller=media_controller,
            mpc_controller=mpc_controller,
            output_controller=output_controller,
            terminal_executor=terminal_executor,
            permission_checker=permission_checker,
            permission_admin=permission_checker,
            admin_telegram_id=settings.admin_telegram_id,
            translation_service=translation_service,
            remote_device_service=remote_device_service,
            remote_ws_hub=remote_ws_hub,
        )
        startup_hooks: tuple[Callable[[], Awaitable[None]], ...] = ()
        shutdown_hooks: tuple[Callable[[], Awaitable[None]], ...] = ()
        if remote_ws_hub is not None:
            startup_hooks = (remote_ws_hub.start,)
            shutdown_hooks = (remote_ws_hub.stop,)
        return TelegramBotModule(
            token=settings.telegram_bot_token,
            handlers=handlers,
            startup_hooks=startup_hooks,
            shutdown_hooks=shutdown_hooks,
        )
    logger.error("Unsupported assistant channel requested: %s", settings.assistant_channel)
    raise ValueError(f"Unsupported channel: {settings.assistant_channel}")
