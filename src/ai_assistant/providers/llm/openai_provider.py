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


class OpenAIProvider:
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
                "AI_ASSISTANT_OPENAI_API_KEY (or OPENAI_API_KEY) is required for openai provider."
            )
        self._model = model
        self._system_prompt = system_prompt

        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "openai package is not installed. Install project with openai extra: pip install -e .[openai]"
            ) from exc

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.strip() or None,
            timeout=timeout_seconds,
        )
        logging.getLogger(__name__).info(
            "OpenAI provider initialized: model=%s base_url=%s",
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
            raise RuntimeError("OpenAI model is not configured.")

        logger.debug(
            "OpenAI request: user_id=%s model=%s prompt_chars=%d",
            message.user_id,
            target_model,
            len(message.text),
        )
        try:
            completion = await self._client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": message.text},
                ],
            )
        except Exception as exc:
            logger.warning(
                "OpenAI request failed: user_id=%s model=%s error=%s",
                message.user_id,
                target_model,
                exc,
            )
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        choices = getattr(completion, "choices", None)
        if not choices:
            raise RuntimeError("OpenAI returned no choices.")

        first = choices[0]
        content = getattr(getattr(first, "message", None), "content", None)
        if isinstance(content, str) and content.strip():
            logger.debug(
                "OpenAI response received: user_id=%s model=%s reply_chars=%d",
                message.user_id,
                target_model,
                len(content.strip()),
            )
            return content.strip()

        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                text = getattr(item, "text", None)
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
                elif isinstance(item, dict):
                    maybe_text = item.get("text")
                    if isinstance(maybe_text, str) and maybe_text.strip():
                        chunks.append(maybe_text.strip())
            if chunks:
                logger.debug(
                    "OpenAI response received (chunked): user_id=%s model=%s chunks=%d",
                    message.user_id,
                    target_model,
                    len(chunks),
                )
                return "\n".join(chunks)

        raise RuntimeError("OpenAI returned empty response.")
