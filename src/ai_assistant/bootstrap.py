from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import (
    ChannelModule,
    LLMProvider,
    MPCController,
    MediaController,
    OutputController,
    PermissionAdminStore,
    TerminalCommandExecutor,
    TranslationService,
    UserSettingsStore,
)
from ai_assistant.core.models import SettingChoiceOption, SettingDefinition
from ai_assistant.core.service import AssistantService
from ai_assistant.modules.telegram.bot import TelegramBotModule
from ai_assistant.modules.telegram.handlers import TelegramHandlers
from ai_assistant.providers.i18n.file_translation_service import FileTranslationService
from ai_assistant.providers.llm.anthropic_provider import AnthropicProvider
from ai_assistant.providers.llm.mock_provider import MockLLMProvider
from ai_assistant.providers.llm.ollama_provider import OllamaProvider
from ai_assistant.providers.llm.openai_provider import OpenAIProvider
from ai_assistant.providers.llm.user_selectable_provider import UserSelectableLLMProvider
from ai_assistant.providers.memory.in_memory_store import InMemoryStore
from ai_assistant.providers.permissions.in_memory_permission_checker import (
    InMemoryPermissionChecker,
)
from ai_assistant.providers.permissions.postgres_permission_checker import (
    PostgresPermissionChecker,
)
from ai_assistant.providers.settings.in_memory_user_settings_store import InMemoryUserSettingsStore
from ai_assistant.providers.settings.postgres_user_settings_store import (
    PostgresUserSettingsStore,
)
from ai_assistant.providers.system.assistant_command_executor import SystemAssistantCommandExecutor
from ai_assistant.providers.system.media_controller import WindowsMediaController
from ai_assistant.providers.system.mpc_hc_controller import MpcHcController
from ai_assistant.providers.system.voicemeeter_output_controller import VoicemeeterOutputController
from ai_assistant.providers.terminal.shell_terminal_executor import ShellTerminalExecutor

SUPPORTED_LLM_PROVIDERS = ("mock", "openai", "anthropic", "ollama")


def _dedupe_keep_order(values: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _is_llm_provider_configured(provider: str, settings: Settings) -> bool:
    if provider == "mock":
        return True
    if provider == "openai":
        return bool(settings.openai_api_key.strip())
    if provider == "anthropic":
        return bool(settings.anthropic_api_key.strip())
    if provider == "ollama":
        return True
    return False


def _build_available_provider_names(settings: Settings) -> tuple[str, ...]:
    requested = [item.strip().lower() for item in settings.llm_available_providers]
    default_provider = settings.llm_provider.strip().lower()
    if default_provider not in SUPPORTED_LLM_PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
    if not _is_llm_provider_configured(default_provider, settings):
        raise ValueError(f"Default LLM provider is not configured: {settings.llm_provider}")
    requested.append(default_provider)

    filtered: list[str] = []
    for provider in requested:
        if provider not in SUPPORTED_LLM_PROVIDERS:
            continue
        if not _is_llm_provider_configured(provider, settings):
            continue
        filtered.append(provider)

    if not filtered:
        return ("mock",)
    return _dedupe_keep_order(filtered)


def _build_models_for_provider(settings: Settings, provider: str) -> tuple[str, ...]:
    if provider == "openai":
        models = [settings.openai_model.strip()]
        models.extend(item.strip() for item in settings.openai_available_models)
        return _dedupe_keep_order(models)
    if provider == "anthropic":
        models = [settings.anthropic_model.strip()]
        models.extend(item.strip() for item in settings.anthropic_available_models)
        return _dedupe_keep_order(models)
    if provider == "ollama":
        models = [settings.ollama_model.strip()]
        models.extend(item.strip() for item in settings.ollama_available_models)
        return _dedupe_keep_order(models)
    return ()


def _provider_display_name(provider: str) -> str:
    if provider == "openai":
        return "OpenAI"
    if provider == "anthropic":
        return "Anthropic"
    if provider == "ollama":
        return "Ollama"
    if provider == "mock":
        return "Mock"
    return provider


def _build_llm_settings_overrides(
    settings: Settings,
    enabled_providers: tuple[str, ...],
) -> tuple[
    tuple[SettingDefinition, ...],
    tuple[SettingChoiceOption, ...],
    dict[str, dict[str, dict[str, str]]],
    dict[str, dict[tuple[str, str], dict[str, str]]],
]:
    definitions: list[SettingDefinition] = [
        SettingDefinition(
            key="llm_provider",
            value_type="choice",
            section="Assistant",
            title="LLM provider",
            description="Preferred LLM backend for your requests.",
        ),
    ]

    options: list[SettingChoiceOption] = []
    choice_translations_ru: dict[tuple[str, str], dict[str, str]] = {}

    for provider in enabled_providers:
        provider_label = _provider_display_name(provider)
        options.append(
            SettingChoiceOption(
                setting_id="llm_provider",
                name=provider,
                display_name=provider_label,
                description=provider_label,
                permission_type="assistant",
                permission_name=f"llm.provider.{provider}",
            )
        )
        choice_translations_ru[("llm_provider", provider)] = {
            "display_name": provider_label,
            "description": provider_label,
        }

        models = _build_models_for_provider(settings, provider)
        for model in models:
            option_name = f"{provider}:{model}"
            options.append(
                SettingChoiceOption(
                    setting_id="llm_model",
                    name=option_name,
                    display_name=model,
                    description=provider_label,
                    permission_type="assistant",
                    permission_name=f"llm.model.{provider}:{model}".lower(),
                )
            )
            choice_translations_ru[("llm_model", option_name)] = {
                "display_name": model,
                "description": provider_label,
            }

    if any(item.setting_id == "llm_model" for item in options):
        definitions.append(
            SettingDefinition(
                key="llm_model",
                value_type="choice",
                section="Assistant",
                title="LLM model",
                description="Preferred model. Use provider:model format internally.",
            )
        )

    translations = {
        "ru": {
            "llm_provider": {
                "section": "Ассистент",
                "title": "LLM-провайдер",
                "description": "Предпочитаемый backend модели для ваших запросов.",
            },
            "llm_model": {
                "section": "Ассистент",
                "title": "LLM-модель",
                "description": "Предпочитаемая модель. Внутреннее значение: provider:model.",
            },
        }
    }

    choice_translations = {
        "ru": choice_translations_ru,
    }

    return tuple(definitions), tuple(options), translations, choice_translations


def _build_single_llm_provider(provider: str, settings: Settings) -> LLMProvider:
    if provider == "mock":
        return MockLLMProvider()
    if provider == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
    if provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            base_url=settings.anthropic_base_url,
        )
    if provider == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _build_llm_provider_instances(
    settings: Settings,
    provider_names: tuple[str, ...],
) -> dict[str, LLMProvider]:
    instances: dict[str, LLMProvider] = {}
    default_provider = settings.llm_provider.strip().lower()

    for provider in provider_names:
        try:
            instances[provider] = _build_single_llm_provider(provider, settings)
        except Exception:
            if provider == default_provider:
                raise
            continue

    if not instances:
        raise RuntimeError("No available LLM providers are configured.")
    return instances


def _build_llm_provider(
    settings: Settings,
    user_settings_store: UserSettingsStore,
    provider_instances: dict[str, LLMProvider],
    permission_checker: PermissionAdminStore | None,
) -> LLMProvider:
    default_provider = settings.llm_provider.strip().lower()
    if default_provider not in provider_instances:
        default_provider = next(iter(provider_instances.keys()))

    available_models = {
        provider: _build_models_for_provider(settings, provider)
        for provider in provider_instances.keys()
    }
    default_models = {
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "ollama": settings.ollama_model,
    }

    return UserSelectableLLMProvider(
        providers=provider_instances,
        default_provider=default_provider,
        default_models=default_models,
        available_models=available_models,
        user_settings_store=user_settings_store,
        permission_checker=permission_checker,
        admin_telegram_id=settings.admin_telegram_id,
    )


def _build_media_controller() -> MediaController | None:
    try:
        return WindowsMediaController()
    except RuntimeError:
        return None


def _build_mpc_controller() -> MPCController | None:
    try:
        return MpcHcController()
    except RuntimeError:
        return None


def _build_output_controller(settings: Settings) -> OutputController | None:
    backend = settings.audio_output_backend.lower().strip()
    if backend in {"", "none"}:
        return None
    if backend == "voicemeeter":
        return VoicemeeterOutputController(
            strip_index=settings.voicemeeter_strip_index,
            bus=settings.voicemeeter_bus,
            output_param=settings.voicemeeter_output_param,
            remote_dll_path=settings.voicemeeter_remote_dll_path,
        )
    raise ValueError(f"Unsupported audio output backend: {settings.audio_output_backend}")


def _build_user_settings_store(
    settings: Settings,
    extra_definitions: tuple[SettingDefinition, ...],
    extra_choice_options: tuple[SettingChoiceOption, ...],
    extra_translations: dict[str, dict[str, dict[str, str]]],
    extra_choice_translations: dict[str, dict[tuple[str, str], dict[str, str]]],
) -> UserSettingsStore:
    backend = settings.user_settings_backend.lower()
    if backend == "memory":
        return InMemoryUserSettingsStore(
            extra_definitions=extra_definitions,
            extra_choice_options=extra_choice_options,
            extra_translations=extra_translations,
            extra_choice_translations=extra_choice_translations,
        )
    if backend == "postgres":
        return PostgresUserSettingsStore(
            dsn=settings.postgres_dsn,
            fallback_locale=settings.default_locale,
            extra_definitions=extra_definitions,
            extra_choice_options=extra_choice_options,
            extra_translations=extra_translations,
            extra_choice_translations=extra_choice_translations,
        )
    raise ValueError(f"Unsupported user settings backend: {settings.user_settings_backend}")


def _build_translation_service(settings: Settings) -> TranslationService:
    return FileTranslationService(default_locale=settings.default_locale, fallback_locale="en")


def _build_permission_checker(settings: Settings) -> PermissionAdminStore | None:
    backend = settings.permissions_backend.strip().lower()
    if backend == "auto":
        if settings.user_settings_backend.strip().lower() == "postgres":
            backend = "postgres"
        else:
            backend = "disabled"
    if backend in {"", "none", "disabled"}:
        return None
    if backend == "memory":
        return InMemoryPermissionChecker(allow_all=False)
    if backend == "postgres":
        return PostgresPermissionChecker(dsn=settings.postgres_dsn)
    raise ValueError(f"Unsupported permissions backend: {settings.permissions_backend}")


def _build_terminal_executor(settings: Settings) -> TerminalCommandExecutor | None:
    try:
        return ShellTerminalExecutor(
            preferred_shell=settings.terminal_shell,
            timeout_seconds=settings.terminal_timeout_seconds,
        )
    except RuntimeError:
        return None


def build_channel_module(settings: Settings) -> ChannelModule:
    memory_store = InMemoryStore()
    translation_service = _build_translation_service(settings)
    permission_checker = _build_permission_checker(settings)

    available_providers = _build_available_provider_names(settings)
    provider_instances = _build_llm_provider_instances(settings, available_providers)
    enabled_provider_names = tuple(provider_instances.keys())

    (
        extra_setting_definitions,
        extra_choice_options,
        extra_translations,
        extra_choice_translations,
    ) = _build_llm_settings_overrides(settings, enabled_provider_names)

    user_settings_store = _build_user_settings_store(
        settings,
        extra_definitions=extra_setting_definitions,
        extra_choice_options=extra_choice_options,
        extra_translations=extra_translations,
        extra_choice_translations=extra_choice_translations,
    )
    llm_provider = _build_llm_provider(
        settings,
        user_settings_store=user_settings_store,
        provider_instances=provider_instances,
        permission_checker=permission_checker,
    )

    media_controller = _build_media_controller()
    mpc_controller = _build_mpc_controller()
    output_controller = _build_output_controller(settings)
    terminal_executor = _build_terminal_executor(settings)
    command_executor = SystemAssistantCommandExecutor(
        media_controller=media_controller,
        mpc_controller=mpc_controller,
        output_controller=output_controller,
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
        )
        return TelegramBotModule(
            token=settings.telegram_bot_token,
            handlers=handlers,
        )
    raise ValueError(f"Unsupported channel: {settings.assistant_channel}")
