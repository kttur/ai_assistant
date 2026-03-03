from __future__ import annotations

import logging

from ai_assistant.core.models import UserMessage

DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant replying in Telegram chat.

Formatting requirements:
- Use Telegram HTML formatting only.
- Allowed tags: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <del>, <code>, <pre>, <a href=\"...\">.
- Do not use Markdown.
- Keep formatting valid and properly closed.
- Use concise structure: short paragraphs and compact lists.
- Do not include unsupported tags or raw HTML comments/scripts.
- Exception: if prompt explicitly requests tool calls, output exact <tool_call>{...}</tool_call>.
"""


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        timeout_seconds: float = 120.0,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        if not api_key.strip():
            raise ValueError(
                "AI_ASSISTANT_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY) is required for anthropic provider."
            )
        self._model = model
        self._system_prompt = system_prompt

        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is not installed. Install project with anthropic extra: pip install -e .[anthropic]"
            ) from exc

        self._client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url.strip() or None,
            timeout=timeout_seconds,
        )
        logging.getLogger(__name__).info(
            "Anthropic provider initialized: model=%s base_url=%s",
            self._model,
            base_url.strip() or "default",
        )

    async def generate_reply(self, message: UserMessage) -> str:
        return await self.generate_reply_for_model(message=message, model=None)

    async def generate_reply_for_model(
        self,
        message: UserMessage,
        model: str | None = None,
    ) -> str:
        logger = logging.getLogger(__name__)
        target_model = (model or self._model).strip()
        if not target_model:
            raise RuntimeError("Anthropic model is not configured.")

        logger.debug(
            "Anthropic request: user_id=%s model=%s prompt_chars=%d",
            message.user_id,
            target_model,
            len(message.text),
        )
        try:
            response = await self._client.messages.create(
                model=target_model,
                max_tokens=1024,
                system=self._system_prompt,
                messages=[
                    {"role": "user", "content": message.text},
                ],
            )
        except Exception as exc:
            logger.warning(
                "Anthropic request failed: user_id=%s model=%s error=%s",
                message.user_id,
                target_model,
                exc,
            )
            raise RuntimeError(f"Anthropic request failed: {exc}") from exc

        chunks: list[str] = []
        for item in getattr(response, "content", []) or []:
            text = getattr(item, "text", None)
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
                continue
            if isinstance(item, dict):
                maybe_text = item.get("text")
                if isinstance(maybe_text, str) and maybe_text.strip():
                    chunks.append(maybe_text.strip())

        if chunks:
            logger.debug(
                "Anthropic response received: user_id=%s model=%s chunks=%d",
                message.user_id,
                target_model,
                len(chunks),
            )
            return "\n".join(chunks)
        raise RuntimeError("Anthropic returned empty response.")
