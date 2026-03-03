from __future__ import annotations

from dataclasses import dataclass
from os import getenv

from dotenv import load_dotenv


def _parse_optional_int(value: str) -> int | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    return int(cleaned)


def _parse_csv(value: str) -> tuple[str, ...]:
    items: list[str] = []
    for item in value.split(","):
        normalized = item.strip()
        if normalized:
            items.append(normalized)
    return tuple(items)


def _get_first_env(*names: str, default: str) -> str:
    for name in names:
        value = getenv(name)
        if value is not None:
            return value
    return default


@dataclass(slots=True, frozen=True)
class Settings:
    assistant_channel: str
    llm_provider: str
    llm_available_providers: tuple[str, ...]
    auto_router_local_provider: str
    auto_router_local_model: str
    auto_router_cloud_provider: str
    auto_router_cloud_model: str
    auto_router_timeout_seconds: float
    llm_health_base_cooldown_seconds: int
    llm_health_max_cooldown_seconds: int
    openai_available_models: tuple[str, ...]
    anthropic_available_models: tuple[str, ...]
    ollama_available_models: tuple[str, ...]
    user_settings_backend: str
    permissions_backend: str
    admin_telegram_id: int | None
    default_locale: str
    audio_output_backend: str
    terminal_shell: str
    terminal_timeout_seconds: int
    voicemeeter_strip_index: int
    voicemeeter_bus: str
    voicemeeter_output_param: str
    voicemeeter_remote_dll_path: str
    telegram_bot_token: str
    postgres_dsn: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    anthropic_api_key: str
    anthropic_base_url: str
    anthropic_model: str
    ollama_base_url: str
    ollama_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(override=False)
        openai_model = _get_first_env(
            "AI_ASSISTANT_OPENAI_MODEL",
            "OPENAI_MODEL",
            default="gpt-4.1-mini",
        )
        openai_available_models = _parse_csv(
            _get_first_env(
                "AI_ASSISTANT_OPENAI_AVAILABLE_MODELS",
                "OPENAI_AVAILABLE_MODELS",
                "AI_ASSISTANT_OPENAI_MODEL",
                "OPENAI_MODEL",
                default="gpt-4.1-mini",
            )
        )
        anthropic_model = _get_first_env(
            "AI_ASSISTANT_ANTHROPIC_MODEL",
            "ANTHROPIC_MODEL",
            default="claude-3-5-sonnet-latest",
        )
        anthropic_available_models = _parse_csv(
            _get_first_env(
                "AI_ASSISTANT_ANTHROPIC_AVAILABLE_MODELS",
                "ANTHROPIC_AVAILABLE_MODELS",
                "AI_ASSISTANT_ANTHROPIC_MODEL",
                "ANTHROPIC_MODEL",
                default="claude-3-5-sonnet-latest",
            )
        )
        ollama_model = getenv("OLLAMA_MODEL", "llama3.1")
        return cls(
            assistant_channel=getenv("ASSISTANT_CHANNEL", "telegram"),
            llm_provider=getenv("LLM_PROVIDER", "mock"),
            llm_available_providers=_parse_csv(
                getenv("LLM_AVAILABLE_PROVIDERS", "mock,openai,anthropic,ollama")
            ),
            auto_router_local_provider=_get_first_env(
                "AI_ASSISTANT_AUTO_ROUTER_LOCAL_PROVIDER",
                "AUTO_ROUTER_LOCAL_PROVIDER",
                default="ollama",
            ),
            auto_router_local_model=_get_first_env(
                "AI_ASSISTANT_AUTO_ROUTER_LOCAL_MODEL",
                "AUTO_ROUTER_LOCAL_MODEL",
                default=ollama_model,
            ),
            auto_router_cloud_provider=_get_first_env(
                "AI_ASSISTANT_AUTO_ROUTER_CLOUD_PROVIDER",
                "AUTO_ROUTER_CLOUD_PROVIDER",
                default="openai",
            ),
            auto_router_cloud_model=_get_first_env(
                "AI_ASSISTANT_AUTO_ROUTER_CLOUD_MODEL",
                "AUTO_ROUTER_CLOUD_MODEL",
                default=openai_model,
            ),
            auto_router_timeout_seconds=float(
                _get_first_env(
                    "AI_ASSISTANT_AUTO_ROUTER_TIMEOUT_SECONDS",
                    "AUTO_ROUTER_TIMEOUT_SECONDS",
                    default="20",
                )
            ),
            llm_health_base_cooldown_seconds=int(
                _get_first_env(
                    "AI_ASSISTANT_LLM_HEALTH_BASE_COOLDOWN_SECONDS",
                    "LLM_HEALTH_BASE_COOLDOWN_SECONDS",
                    default="120",
                )
            ),
            llm_health_max_cooldown_seconds=int(
                _get_first_env(
                    "AI_ASSISTANT_LLM_HEALTH_MAX_COOLDOWN_SECONDS",
                    "LLM_HEALTH_MAX_COOLDOWN_SECONDS",
                    default="1800",
                )
            ),
            openai_available_models=openai_available_models,
            anthropic_available_models=anthropic_available_models,
            ollama_available_models=_parse_csv(getenv("OLLAMA_AVAILABLE_MODELS", ollama_model)),
            user_settings_backend=getenv("USER_SETTINGS_BACKEND", "memory"),
            permissions_backend=getenv("PERMISSIONS_BACKEND", "auto"),
            admin_telegram_id=_parse_optional_int(getenv("ADMIN_TELEGRAM_ID", "")),
            default_locale=getenv("DEFAULT_LOCALE", "ru"),
            audio_output_backend=getenv("AUDIO_OUTPUT_BACKEND", "none"),
            terminal_shell=getenv("TERMINAL_SHELL", "powershell"),
            terminal_timeout_seconds=int(getenv("TERMINAL_TIMEOUT_SECONDS", "60")),
            voicemeeter_strip_index=int(getenv("VOICEMEETER_STRIP_INDEX", "5")),
            voicemeeter_bus=getenv("VOICEMEETER_BUS", "A1"),
            voicemeeter_output_param=getenv("VOICEMEETER_OUTPUT_PARAM", ""),
            voicemeeter_remote_dll_path=getenv("VOICEMEETER_REMOTE_DLL_PATH", ""),
            telegram_bot_token=getenv("TELEGRAM_BOT_TOKEN", ""),
            postgres_dsn=getenv("POSTGRES_DSN", ""),
            openai_api_key=_get_first_env(
                "AI_ASSISTANT_OPENAI_API_KEY",
                "OPENAI_API_KEY",
                "OPENAI_API_KEY_1",
                default="",
            ),
            openai_base_url=_get_first_env(
                "AI_ASSISTANT_OPENAI_BASE_URL",
                "OPENAI_BASE_URL",
                "OPENAI_BASE_URL_1",
                default="",
            ),
            openai_model=openai_model,
            anthropic_api_key=_get_first_env(
                "AI_ASSISTANT_ANTHROPIC_API_KEY",
                "ANTHROPIC_API_KEY",
                default="",
            ),
            anthropic_base_url=_get_first_env(
                "AI_ASSISTANT_ANTHROPIC_BASE_URL",
                "ANTHROPIC_BASE_URL",
                default="",
            ),
            anthropic_model=anthropic_model,
            ollama_base_url=getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=ollama_model,
        )
