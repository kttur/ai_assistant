from __future__ import annotations

import json
from pathlib import Path


class FileTranslationService:
    def __init__(
        self,
        locales_dir: Path | None = None,
        default_locale: str = "en",
        fallback_locale: str = "en",
    ) -> None:
        self._default_locale = self._normalize_locale(default_locale)
        self._fallback_locale = self._normalize_locale(fallback_locale)
        self._locales_dir = locales_dir or self._default_locales_dir()
        self._catalogs = self._load_catalogs(self._locales_dir)

    def get_default_locale(self) -> str:
        return self._default_locale

    def resolve_locale(self, locale: str | None) -> str:
        normalized = self._normalize_locale(locale)
        if normalized in self._catalogs:
            return normalized
        language = normalized.split("-", 1)[0]
        if language in self._catalogs:
            return language
        if self._default_locale in self._catalogs:
            return self._default_locale
        if self._fallback_locale in self._catalogs:
            return self._fallback_locale
        return self._default_locale

    def translate(self, message_key: str, locale: str | None = None, **params: object) -> str:
        for candidate in self._candidate_locales(locale):
            template = self._catalogs.get(candidate, {}).get(message_key)
            if template is None:
                continue
            if not params:
                return template
            try:
                return template.format(**params)
            except Exception:
                return template
        return message_key

    def _candidate_locales(self, locale: str | None) -> list[str]:
        requested = self._normalize_locale(locale)
        candidates = [requested]

        short = requested.split("-", 1)[0]
        if short != requested:
            candidates.append(short)

        candidates.append(self._default_locale)
        candidates.append(self._fallback_locale)

        # Keep order while removing duplicates.
        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            unique.append(candidate)
        return unique

    @staticmethod
    def _normalize_locale(locale: str | None) -> str:
        if locale is None:
            return ""
        normalized = locale.strip().lower().replace("_", "-")
        return normalized

    @staticmethod
    def _default_locales_dir() -> Path:
        return Path(__file__).resolve().parents[2] / "resources" / "i18n"

    @staticmethod
    def _load_catalogs(locales_dir: Path) -> dict[str, dict[str, str]]:
        catalogs: dict[str, dict[str, str]] = {}
        if not locales_dir.exists() or not locales_dir.is_dir():
            return catalogs

        for file in locales_dir.glob("*.json"):
            locale = FileTranslationService._normalize_locale(file.stem)
            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            normalized_payload: dict[str, str] = {}
            for key, value in payload.items():
                if isinstance(key, str) and isinstance(value, str):
                    normalized_payload[key] = value
            catalogs[locale] = normalized_payload
        return catalogs
