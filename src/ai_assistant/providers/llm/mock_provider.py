from __future__ import annotations

import logging

from ai_assistant.core.models import UserMessage

logger = logging.getLogger(__name__)


class MockLLMProvider:
    async def generate_reply(self, message: UserMessage) -> str:
        logger.debug("Mock provider request: user_id=%s prompt_chars=%d", message.user_id, len(message.text))
        return f"[mock] Вы сказали: {message.text}"
