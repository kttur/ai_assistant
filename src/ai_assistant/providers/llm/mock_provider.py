from __future__ import annotations

from ai_assistant.core.models import UserMessage


class MockLLMProvider:
    async def generate_reply(self, message: UserMessage) -> str:
        return f"[mock] Вы сказали: {message.text}"

