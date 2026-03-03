from __future__ import annotations

import asyncio
import json
import logging
from urllib import error, request

from ai_assistant.core.models import UserMessage

DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant replying in Telegram chat.

Formatting requirements:
- Use Telegram HTML formatting only.
- Allowed tags: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <del>, <code>, <pre>, <a href="...">.
- Do not use Markdown.
- Keep formatting valid and properly closed.
- Use concise structure: short paragraphs and compact lists.
- Do not include unsupported tags or raw HTML comments/scripts.
- Exception: if prompt explicitly requests tool calls, output exact <tool_call>{...}</tool_call>.
"""
DEFAULT_USER_AGENT = "python-requests/2.32.3"
logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        auth_header_name: str = "",
        auth_header_value: str = "",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._system_prompt = system_prompt
        self._generate_urls = (
            f"{self._base_url}/api/generate",
            f"{self._base_url}/api/generate/",
        )
        self._request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        for raw_name, raw_value in (extra_headers or {}).items():
            header_name = raw_name.strip().rstrip(":")
            header_value = raw_value.strip()
            if header_name and header_value:
                self._request_headers[header_name] = header_value
        header_name = auth_header_name.strip().rstrip(":")
        header_value = auth_header_value.strip()
        if header_name and header_value:
            self._request_headers[header_name] = header_value
        logger.info(
            "Ollama provider initialized: base_url=%s model=%s",
            self._base_url,
            self._model,
        )

    async def generate_reply(self, message: UserMessage) -> str:
        return await self.generate_reply_for_model(message=message, model=None)

    async def generate_reply_for_model(
        self,
        message: UserMessage,
        model: str | None = None,
    ) -> str:
        target_model = (model or self._model).strip()
        if not target_model:
            raise RuntimeError("Ollama model is not configured.")
        logger.debug(
            "Ollama request: user_id=%s model=%s prompt_chars=%d",
            message.user_id,
            target_model,
            len(message.text),
        )
        payload = {
            "model": target_model,
            "prompt": message.text,
            "system": self._system_prompt,
            "stream": False,
        }
        return await asyncio.to_thread(self._generate_sync, payload)

    def _generate_sync(self, payload: dict[str, object]) -> str:
        data = json.dumps(payload).encode("utf-8")
        body = ""
        for index, target_url in enumerate(self._generate_urls):
            req = request.Request(
                target_url,
                data=data,
                headers=self._request_headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self._timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                logger.debug("Ollama request succeeded via %s", target_url)
                break
            except error.HTTPError as exc:
                is_last_attempt = index == len(self._generate_urls) - 1
                should_retry_alt_path = exc.code in {403, 404} and not is_last_attempt
                if should_retry_alt_path:
                    logger.debug(
                        "Ollama HTTP %s on %s, retrying alternate URL",
                        exc.code,
                        target_url,
                    )
                    continue
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                detail = f" Ollama response: {error_body[:300]}" if error_body else ""
                logger.warning("Ollama HTTP error %s via %s", exc.code, target_url)
                raise RuntimeError(f"Ollama HTTP error {exc.code}.{detail}") from exc
            except error.URLError as exc:
                logger.warning("Ollama is unreachable via %s: %s", target_url, exc.reason)
                raise RuntimeError(f"Ollama is unreachable: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Invalid JSON from Ollama.") from exc

        api_error = parsed.get("error")
        if api_error:
            raise RuntimeError(f"Ollama API error: {api_error}")

        text = str(parsed.get("response", "")).strip()
        if not text:
            raise RuntimeError("Empty response from Ollama.")
        logger.debug("Ollama response received: reply_chars=%d", len(text))
        return text
