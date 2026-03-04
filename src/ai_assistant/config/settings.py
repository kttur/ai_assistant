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


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    auto_router_low_confidence_threshold: float
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
    assistant_active_skills: tuple[str, ...]
    assistant_skill_factories: tuple[str, ...]
    remote_enabled: bool
    remote_backend: str
    remote_server_id: str
    remote_ws_host: str
    remote_ws_port: int
    remote_ws_path: str
    remote_ws_public_url: str
    remote_tls_cert_path: str
    remote_tls_key_path: str
    remote_link_code_ttl_seconds: int
    remote_request_timeout_seconds: float
    remote_ping_interval_seconds: float
    remote_ping_timeout_seconds: float
    remote_client_server_url: str
    remote_client_name: str
    remote_client_platform: str
    remote_client_token_file: str
    remote_client_active_skills: tuple[str, ...]
    remote_client_skill_factories: tuple[str, ...]
    remote_client_reconnect_min_seconds: float
    remote_client_reconnect_max_seconds: float
    remote_client_ping_interval_seconds: float
    remote_client_ping_timeout_seconds: float
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
    anthropic_max_tokens: int
    ollama_base_url: str
    ollama_model: str
    ollama_auth_header_name: str
    ollama_auth_header_value: str
    ollama_extra_headers_json: str

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
        ollama_model = getenv("OLLAMA_MODEL", "mistral-small3.2:24b")

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
            auto_router_low_confidence_threshold=float(
                _get_first_env(
                    "AI_ASSISTANT_AUTO_ROUTER_LOW_CONFIDENCE_THRESHOLD",
                    "AUTO_ROUTER_LOW_CONFIDENCE_THRESHOLD",
                    default="0.55",
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
            assistant_active_skills=_parse_csv(getenv("AI_ASSISTANT_ACTIVE_SKILLS", "")),
            assistant_skill_factories=_parse_csv(getenv("AI_ASSISTANT_SKILL_FACTORIES", "")),
            remote_enabled=_parse_bool(getenv("AI_ASSISTANT_REMOTE_ENABLED", "false")),
            remote_backend=getenv("AI_ASSISTANT_REMOTE_BACKEND", "postgres"),
            remote_server_id=getenv("AI_ASSISTANT_REMOTE_SERVER_ID", "default"),
            remote_ws_host=getenv("AI_ASSISTANT_REMOTE_WS_HOST", "0.0.0.0"),
            remote_ws_port=int(getenv("AI_ASSISTANT_REMOTE_WS_PORT", "8765")),
            remote_ws_path=getenv("AI_ASSISTANT_REMOTE_WS_PATH", "/ws/remote"),
            remote_ws_public_url=getenv("AI_ASSISTANT_REMOTE_WS_PUBLIC_URL", ""),
            remote_tls_cert_path=getenv("AI_ASSISTANT_REMOTE_TLS_CERT_PATH", ""),
            remote_tls_key_path=getenv("AI_ASSISTANT_REMOTE_TLS_KEY_PATH", ""),
            remote_link_code_ttl_seconds=int(
                getenv("AI_ASSISTANT_REMOTE_LINK_CODE_TTL_SECONDS", "300")
            ),
            remote_request_timeout_seconds=float(
                getenv("AI_ASSISTANT_REMOTE_REQUEST_TIMEOUT_SECONDS", "20")
            ),
            remote_ping_interval_seconds=float(
                getenv("AI_ASSISTANT_REMOTE_PING_INTERVAL_SECONDS", "20")
            ),
            remote_ping_timeout_seconds=float(
                getenv("AI_ASSISTANT_REMOTE_PING_TIMEOUT_SECONDS", "20")
            ),
            remote_client_server_url=getenv("AI_ASSISTANT_REMOTE_CLIENT_SERVER_URL", ""),
            remote_client_name=getenv("AI_ASSISTANT_REMOTE_CLIENT_NAME", ""),
            remote_client_platform=getenv("AI_ASSISTANT_REMOTE_CLIENT_PLATFORM", "windows"),
            remote_client_token_file=getenv(
                "AI_ASSISTANT_REMOTE_CLIENT_TOKEN_FILE",
                ".ai_assistant_remote_client_token.json",
            ),
            remote_client_active_skills=_parse_csv(
                getenv("AI_ASSISTANT_REMOTE_CLIENT_ACTIVE_SKILLS", "")
            ),
            remote_client_skill_factories=_parse_csv(
                getenv("AI_ASSISTANT_REMOTE_CLIENT_SKILL_FACTORIES", "")
            ),
            remote_client_reconnect_min_seconds=float(
                getenv("AI_ASSISTANT_REMOTE_CLIENT_RECONNECT_MIN_SECONDS", "1")
            ),
            remote_client_reconnect_max_seconds=float(
                getenv("AI_ASSISTANT_REMOTE_CLIENT_RECONNECT_MAX_SECONDS", "30")
            ),
            remote_client_ping_interval_seconds=float(
                getenv("AI_ASSISTANT_REMOTE_CLIENT_PING_INTERVAL_SECONDS", "20")
            ),
            remote_client_ping_timeout_seconds=float(
                getenv("AI_ASSISTANT_REMOTE_CLIENT_PING_TIMEOUT_SECONDS", "20")
            ),
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
            anthropic_max_tokens=int(
                _get_first_env(
                    "AI_ASSISTANT_ANTHROPIC_MAX_TOKENS",
                    "ANTHROPIC_MAX_TOKENS",
                    default="4096",
                )
            ),
            ollama_base_url=getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=ollama_model,
            ollama_auth_header_name=_get_first_env(
                "AI_ASSISTANT_OLLAMA_AUTH_HEADER_NAME",
                "OLLAMA_AUTH_HEADER_NAME",
                default="",
            ),
            ollama_auth_header_value=_get_first_env(
                "AI_ASSISTANT_OLLAMA_AUTH_HEADER_VALUE",
                "OLLAMA_AUTH_HEADER_VALUE",
                default="",
            ),
            ollama_extra_headers_json=_get_first_env(
                "AI_ASSISTANT_OLLAMA_EXTRA_HEADERS_JSON",
                "OLLAMA_EXTRA_HEADERS_JSON",
                default="",
            ),
        )
