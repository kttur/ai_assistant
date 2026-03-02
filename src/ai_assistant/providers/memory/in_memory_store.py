from __future__ import annotations

from collections import defaultdict

from ai_assistant.core.models import ConversationMessage, UserMessage


class InMemoryStore:
    def __init__(self) -> None:
        self._conversations: dict[int, list[ConversationMessage]] = defaultdict(list)

    async def save_user_message(self, message: UserMessage) -> None:
        self._conversations[message.user_id].append(
            ConversationMessage(
                user_id=message.user_id,
                role="user",
                text=message.text,
                timestamp=message.timestamp,
            )
        )

    async def save_assistant_message(self, user_id: int, text: str) -> None:
        self._conversations[user_id].append(
            ConversationMessage(user_id=user_id, role="assistant", text=text)
        )

    async def get_conversation(
        self, user_id: int, limit: int | None = None
    ) -> list[ConversationMessage]:
        messages = self._conversations.get(user_id, [])
        if limit is None:
            return list(messages)
        return list(messages[-limit:])

    async def clear_conversation(self, user_id: int) -> None:
        self._conversations.pop(user_id, None)
