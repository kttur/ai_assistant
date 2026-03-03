from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import TranslationService
from ai_assistant.providers.i18n.file_translation_service import FileTranslationService


def build_translation_service(settings: Settings) -> TranslationService:
    return FileTranslationService(default_locale=settings.default_locale, fallback_locale="en")
