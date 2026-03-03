from __future__ import annotations

DEFAULT_SETTING_DEFINITIONS: tuple[tuple[str, str, str, str, str, bool], ...] = (
    (
        "language",
        "choice",
        "Assistant",
        "Language",
        "Preferred language for assistant replies.",
        True,
    ),
    (
        "tts",
        "bool",
        "Assistant",
        "Voice replies (TTS)",
        "Enable or disable text-to-speech replies.",
        True,
    ),
    (
        "signature",
        "text",
        "Assistant",
        "Reply signature",
        "Optional text signature appended to assistant messages.",
        True,
    ),
)

DEFAULT_SETTING_TRANSLATIONS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "language",
        "en",
        "Assistant",
        "Language",
        "Preferred language for assistant replies.",
    ),
    (
        "tts",
        "en",
        "Assistant",
        "Voice replies (TTS)",
        "Enable or disable text-to-speech replies.",
    ),
    (
        "signature",
        "en",
        "Assistant",
        "Reply signature",
        "Optional text signature appended to assistant messages.",
    ),
    (
        "language",
        "ru",
        "Ассистент",
        "Язык",
        "Предпочитаемый язык ответов ассистента.",
    ),
    (
        "tts",
        "ru",
        "Ассистент",
        "Голосовые ответы (TTS)",
        "Включить или отключить озвучивание ответов.",
    ),
    (
        "signature",
        "ru",
        "Ассистент",
        "Подпись ответа",
        "Необязательная подпись, добавляемая к сообщениям ассистента.",
    ),
)

DEFAULT_SETTING_CHOICE_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("language", "ru", "Russian"),
    ("language", "en", "English"),
)

DEFAULT_SETTING_CHOICE_TRANSLATIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("language", "ru", "en", "Russian", "Russian"),
    ("language", "en", "en", "English", "English"),
    ("language", "ru", "ru", "Русский", "Русский"),
    ("language", "en", "ru", "Английский", "English"),
)
