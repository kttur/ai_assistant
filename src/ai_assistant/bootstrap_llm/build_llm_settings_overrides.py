from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.models import SettingChoiceOption, SettingDefinition
from ai_assistant.bootstrap_llm.build_models_for_provider import build_models_for_provider
from ai_assistant.bootstrap_llm.provider_display_name import provider_display_name


def build_llm_settings_overrides(
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
        SettingDefinition(
            key="llm_auto_low_confidence_policy",
            value_type="choice",
            section="Assistant",
            title="Auto routing confidence fallback",
            description="What to do when router confidence is low.",
        ),
    ]

    options: list[SettingChoiceOption] = [
        SettingChoiceOption(
            setting_id="llm_provider",
            name="auto",
            display_name=provider_display_name("auto"),
            description="Automatic routing by policy.",
        )
    ]
    choice_translations_ru: dict[tuple[str, str], dict[str, str]] = {}
    choice_translations_ru[("llm_provider", "auto")] = {
        "display_name": "Авто",
        "description": "Автоматический выбор провайдера и модели по политике.",
    }
    options.extend(
        [
            SettingChoiceOption(
                setting_id="llm_auto_low_confidence_policy",
                name="keep_current",
                display_name="Keep current",
                description="Keep router queue as is.",
            ),
            SettingChoiceOption(
                setting_id="llm_auto_low_confidence_policy",
                name="upgrade_tier",
                display_name="Upgrade tier",
                description="Prioritize more expensive/higher-accuracy models.",
            ),
        ]
    )
    choice_translations_ru[("llm_auto_low_confidence_policy", "keep_current")] = {
        "display_name": "Оставить текущий",
        "description": "Оставить выбранную роутером очередь.",
    }
    choice_translations_ru[("llm_auto_low_confidence_policy", "upgrade_tier")] = {
        "display_name": "Выбрать подороже",
        "description": "Приоритизировать более дорогие/точные модели.",
    }

    for provider in enabled_providers:
        provider_label = provider_display_name(provider)
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

        models = build_models_for_provider(settings, provider)
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
                "description": "Предпочитаемый backend модели или автоматическая маршрутизация.",
            },
            "llm_model": {
                "section": "Ассистент",
                "title": "LLM-модель",
                "description": "Предпочитаемая модель. Внутреннее значение: provider:model.",
            },
            "llm_auto_low_confidence_policy": {
                "section": "Ассистент",
                "title": "Политика при низкой уверенности",
                "description": "Поведение при низкой уверенности роутера.",
            },
        }
    }

    choice_translations = {
        "ru": choice_translations_ru,
    }

    return tuple(definitions), tuple(options), translations, choice_translations
