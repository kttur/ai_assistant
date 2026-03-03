from __future__ import annotations

from ai_assistant.core.models import SettingChoiceOption
from ai_assistant.modules.telegram.handler_functions.extract_model_provider import extract_model_provider
from ai_assistant.modules.telegram.handler_functions.extract_model_provider_from_permission import (
    extract_model_provider_from_permission,
)


_ALLOWED_PROVIDER_DESCRIPTIONS = {"openai", "ollama", "mock", "anthropic"}


def extract_model_provider_from_option(option: SettingChoiceOption) -> str | None:
    by_name = extract_model_provider(option.name)
    if by_name is not None:
        return by_name

    by_permission = extract_model_provider_from_permission(option.permission_name)
    if by_permission is not None:
        return by_permission

    normalized_description = option.description.strip().lower()
    if normalized_description in _ALLOWED_PROVIDER_DESCRIPTIONS:
        return normalized_description

    return None
