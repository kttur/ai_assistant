from ai_assistant.providers.llm.auto_router_policy import build_router_prompt
from ai_assistant.providers.llm.auto_router_types import RouterCatalogEntry


def test_build_router_prompt_uses_latest_user_message_from_assistant_context_prompt() -> None:
    router_prompt = build_router_prompt(
        user_text=(
            "Ты полезный AI-помощник. Учитывай историю диалога и отвечай на последнее сообщение пользователя.\n"
            "\n"
            "История диалога:\n"
            "Пользователь: включи музыку\n"
            "Ассистент: Уже включил.\n"
            "Пользователь: Переключи субтитры на два назад\n"
            "\n"
            "Available commands JSON:\n"
            '[{"command":"mpc.subtitle_previous","args":{}}]\n'
            "\n"
            "Ассистент:"
        ),
        candidate_catalog=(
            RouterCatalogEntry(
                provider="ollama",
                model="qwen3:4b",
                platform="local",
                cost_tier="cheap_local",
            ),
        ),
    )

    assert "User request:\nПереключи субтитры на два назад" in router_prompt
    assert '"command":"mpc.subtitle_previous"' not in router_prompt
