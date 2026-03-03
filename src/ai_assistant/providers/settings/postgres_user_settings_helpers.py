from __future__ import annotations

from collections.abc import Callable

from ai_assistant.core.models import SettingChoiceOption, SettingDefinition


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return "en"
    normalized = locale.strip().lower().replace("_", "-")
    return normalized.split("-", 1)[0] or "en"


def normalize_choice_name(name: str) -> str:
    return name.strip().lower()


def build_setting_definitions(
    rows: list[tuple[object, ...]],
    extra_definitions: dict[str, SettingDefinition],
    locale: str,
    resolve_extra_translation: Callable[..., dict[str, str]],
) -> list[SettingDefinition]:
    definitions: list[SettingDefinition] = []
    for row in rows:
        definitions.append(
            SettingDefinition(
                key=str(row[0]),
                value_type=str(row[1]),  # type: ignore[arg-type]
                section=str(row[2]),
                title=str(row[3]),
                description=str(row[4] or ""),
                is_shown_in_ui=bool(row[5]),
                read_permission_type=str(row[6]) if row[6] else None,
                read_permission_name=str(row[7]) if row[7] else None,
                write_permission_type=str(row[8]) if row[8] else None,
                write_permission_name=str(row[9]) if row[9] else None,
            )
        )

    existing_keys = {item.key for item in definitions}
    for key, item in extra_definitions.items():
        if key in existing_keys:
            continue
        translation = resolve_extra_translation(locale=locale, setting_key=key)
        definitions.append(
            SettingDefinition(
                key=item.key,
                value_type=item.value_type,
                section=translation.get("section", item.section),
                title=translation.get("title", item.title),
                description=translation.get("description", item.description),
                is_shown_in_ui=item.is_shown_in_ui,
                read_permission_type=item.read_permission_type,
                read_permission_name=item.read_permission_name,
                write_permission_type=item.write_permission_type,
                write_permission_name=item.write_permission_name,
            )
        )
    definitions.sort(key=lambda item: (item.section.lower(), item.title.lower(), item.key))
    return definitions


def build_setting_choice_options(
    rows: list[tuple[object, ...]],
    extra_choice_options: list[SettingChoiceOption],
    locale: str,
    resolve_extra_choice_translation: Callable[..., dict[str, str]],
) -> list[SettingChoiceOption]:
    options: list[SettingChoiceOption] = []
    for row in rows:
        options.append(
            SettingChoiceOption(
                setting_id=str(row[0]),
                name=str(row[1]),
                display_name=str(row[2]) if row[2] else None,
                description=str(row[3] or ""),
                permission_type=str(row[4]) if row[4] else None,
                permission_name=str(row[5]) if row[5] else None,
            )
        )

    normalized_index: dict[tuple[str, str], int] = {}
    for index, item in enumerate(options):
        key = (item.setting_id.strip().lower(), normalize_choice_name(item.name))
        normalized_index.setdefault(key, index)

    for item in extra_choice_options:
        normalized_key = (item.setting_id.strip().lower(), normalize_choice_name(item.name))
        existing_index = normalized_index.get(normalized_key)

        if existing_index is not None:
            existing_item = options[existing_index]
            translation = resolve_extra_choice_translation(
                locale=locale,
                setting_id=item.setting_id,
                option_name=item.name,
            )
            merged = SettingChoiceOption(
                setting_id=existing_item.setting_id,
                name=existing_item.name,
                display_name=(
                    existing_item.display_name
                    or translation.get("display_name")
                    or item.display_name
                ),
                description=(
                    existing_item.description
                    or translation.get("description")
                    or item.description
                ),
                permission_type=existing_item.permission_type or item.permission_type,
                permission_name=existing_item.permission_name or item.permission_name,
            )
            if merged != existing_item:
                options[existing_index] = merged
            continue

        translation = resolve_extra_choice_translation(
            locale=locale,
            setting_id=item.setting_id,
            option_name=item.name,
        )
        options.append(
            SettingChoiceOption(
                setting_id=item.setting_id.strip().lower(),
                name=item.name,
                display_name=translation.get("display_name", item.display_name),
                description=translation.get("description", item.description),
                permission_type=item.permission_type,
                permission_name=item.permission_name,
            )
        )
        normalized_index[normalized_key] = len(options) - 1

    options.sort(key=lambda item: item.name.lower())
    return options
