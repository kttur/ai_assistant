from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from dataclasses import dataclass

from ai_assistant.core.interfaces import (
    AssistantCommandExecutor,
    LLMProvider,
    MemoryStore,
    PermissionChecker,
    UserSettingsStore,
)
from ai_assistant.core.models import AssistantDocument, AssistantReply, ConversationMessage, UserMessage
from ai_assistant.logging_utils import text_preview

_TOOL_CALL_PATTERNS = (
    re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL | re.IGNORECASE),
    # Compatibility with models that still emit legacy wrappers like <fix>{...}<fix>.
    re.compile(r"<fix>\s*(\{.*?\})\s*(?=(?:</fix>|<fix>))", re.DOTALL | re.IGNORECASE),
    # Some models emit bare command JSON wrapped in Telegram HTML code tags.
    re.compile(r"<code>\s*(\{.*?\})\s*</code>", re.DOTALL | re.IGNORECASE),
)
_MAX_TELEGRAM_DOCUMENTS_PER_TURN = 3
_MAX_TELEGRAM_DOCUMENT_BYTES = 20 * 1024 * 1024
logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class _ToolCall:
    command: str
    args: dict[str, object]


class AssistantService:
    def __init__(
        self,
        llm_provider: LLMProvider,
        memory_store: MemoryStore,
        history_limit_messages: int = 20,
        command_executor: AssistantCommandExecutor | None = None,
        max_tool_calls_per_turn: int = 3,
        permission_checker: PermissionChecker | None = None,
        admin_telegram_id: int | None = None,
        user_settings_store: UserSettingsStore | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._memory_store = memory_store
        self._history_limit_messages = history_limit_messages
        self._command_executor = command_executor
        self._max_tool_calls_per_turn = max_tool_calls_per_turn
        self._permission_checker = permission_checker
        self._admin_telegram_id = admin_telegram_id
        self._user_settings_store = user_settings_store

    async def process_text(self, user_id: int, text: str) -> AssistantReply:
        logger.info("Processing assistant request: user_id=%s", user_id)
        logger.debug("Assistant request text preview: user_id=%s text_preview=%r", user_id, text_preview(text))
        message = UserMessage(user_id=user_id, text=text)
        await self._memory_store.save_user_message(message)

        history = await self._memory_store.get_conversation(
            user_id=user_id, limit=self._history_limit_messages
        )
        preferred_language = await self._get_preferred_reply_language(user_id=user_id)
        command_catalog = await self._get_allowed_command_catalog(user_id=user_id)
        logger.debug(
            "Prompt context prepared: user_id=%s history_messages=%d preferred_language=%s available_commands=%d",
            user_id,
            len(history),
            preferred_language,
            len(command_catalog),
        )
        llm_prompt = self._build_prompt(
            history,
            command_catalog=command_catalog,
            preferred_language=preferred_language,
        )

        first_reply = await self._llm_provider.generate_reply(
            UserMessage(user_id=user_id, text=llm_prompt, timestamp=message.timestamp)
        )
        tool_calls = self._extract_tool_calls(first_reply)
        logger.debug(
            "First LLM response received: user_id=%s reply_chars=%d tool_calls=%d",
            user_id,
            len(first_reply),
            len(tool_calls),
        )

        if tool_calls and self._command_executor:
            tool_results: list[dict[str, object]] = []
            documents: list[AssistantDocument] = []
            for call in tool_calls[: self._max_tool_calls_per_turn]:
                logger.debug(
                    "Executing tool call candidate: user_id=%s command=%s args=%s",
                    user_id,
                    call.command,
                    call.args,
                )
                if not await self._is_assistant_action_allowed(
                    user_id=user_id,
                    action_name=call.command,
                ):
                    logger.warning(
                        "Tool call denied by permissions: user_id=%s command=%s",
                        user_id,
                        call.command,
                    )
                    execution = {
                        "ok": False,
                        "message": f"Permission denied for assistant action: {call.command}",
                    }
                    tool_results.append(
                        {
                            "command": call.command,
                            "args": call.args,
                            "result": execution,
                        }
                    )
                    continue
                try:
                    execution = await self._command_executor.execute_command(
                        command=call.command,
                        args=call.args,
                        user_id=user_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Tool call failed: user_id=%s command=%s error=%s",
                        user_id,
                        call.command,
                        exc,
                    )
                    execution = {"ok": False, "message": f"Command execution error: {exc}"}
                else:
                    logger.debug(
                        "Tool call succeeded: user_id=%s command=%s result=%s",
                        user_id,
                        call.command,
                        execution,
                    )
                extracted_documents, execution_for_prompt = self._extract_telegram_documents(
                    execution,
                    command=call.command,
                )
                if extracted_documents:
                    documents.extend(extracted_documents)
                tool_results.append(
                    {
                        "command": call.command,
                        "args": call.args,
                        "result": execution_for_prompt,
                    }
                )

            followup_prompt = self._build_tool_followup_prompt(
                history=history,
                tool_results=tool_results,
                preferred_language=preferred_language,
            )
            logger.debug(
                "Requesting final response after tool execution: user_id=%s tool_results=%d",
                user_id,
                len(tool_results),
            )
            reply_text = await self._llm_provider.generate_reply(
                UserMessage(user_id=user_id, text=followup_prompt, timestamp=message.timestamp)
            )
        else:
            reply_text = first_reply
            documents = []

        await self._memory_store.save_assistant_message(user_id=user_id, text=reply_text)
        logger.info(
            "Assistant response generated: user_id=%s reply_chars=%d",
            user_id,
            len(reply_text),
        )
        return AssistantReply(
            user_id=user_id,
            text=reply_text,
            documents=tuple(documents),
        )

    async def clear_context(self, user_id: int) -> None:
        await self._memory_store.clear_conversation(user_id=user_id)
        logger.info("Conversation context cleared: user_id=%s", user_id)

    def _build_prompt(
        self,
        history: list[ConversationMessage],
        command_catalog: list[dict[str, object]] | None = None,
        preferred_language: str | None = None,
    ) -> str:
        command_catalog = command_catalog or []
        if not history:
            return ""
        if (
            len(history) == 1
            and history[0].role == "user"
            and not command_catalog
            and preferred_language is None
        ):
            return history[0].text

        lines = [
            "Ты AI-помощник. Учитывай историю и отвечай на последнее сообщение.",
            "",
            "История:",
        ]
        for item in history:
            if item.role == "user":
                lines.append(f"Пользователь: {item.text}")
            else:
                lines.append(f"Ассистент: {item.text}")

        if command_catalog:
            compact_command_catalog = self._build_compact_command_catalog(command_catalog)
            lines.extend(
                [
                    "",
                    "You can call system commands.",
                    "Format: <tool_call>{\"command\":\"media.play_pause\",\"args\":{}}</tool_call>",
                    "If command needed: output only tool_call blocks, no other text.",
                    "Otherwise: reply normally.",
                    "Commands:",
                    json.dumps(compact_command_catalog, ensure_ascii=False),
                ]
            )

        if preferred_language:
            lines.extend(
                [
                    "",
                    self._build_language_instruction(preferred_language),
                ]
            )

        lines.append("")
        lines.append("Ассистент:")
        return "\n".join(lines)

    async def _get_allowed_command_catalog(self, user_id: int) -> list[dict[str, object]]:
        if not self._command_executor:
            return []

        all_commands = await self._command_executor.get_command_catalog(user_id=user_id)
        if not self._permission_checker:
            return all_commands

        allowed: list[dict[str, object]] = []
        for item in all_commands:
            command_name = item.get("command")
            if not isinstance(command_name, str):
                continue
            if await self._is_assistant_action_allowed(user_id=user_id, action_name=command_name):
                allowed.append(item)
        logger.debug(
            "Command catalog filtered by permissions: user_id=%s total=%d allowed=%d",
            user_id,
            len(all_commands),
            len(allowed),
        )
        return allowed

    async def _is_assistant_action_allowed(self, user_id: int, action_name: str) -> bool:
        if self._admin_telegram_id is not None and user_id == self._admin_telegram_id:
            return True
        if not self._permission_checker:
            return True
        allowed = await self._permission_checker.has_permission(
            user_id=user_id,
            permission_type="assistant",
            name=action_name,
        )
        logger.debug(
            "Assistant action permission check: user_id=%s action=%s allowed=%s",
            user_id,
            action_name,
            allowed,
        )
        return allowed

    def _build_tool_followup_prompt(
        self,
        history: list[ConversationMessage],
        tool_results: list[dict[str, object]],
        preferred_language: str | None = None,
    ) -> str:
        lines = [
            "Команды выполнены. Сформируй финальный ответ на основе результатов.",
            "Не выводи <tool_call> снова.",
            "",
            "История:",
        ]
        for item in history:
            if item.role == "user":
                lines.append(f"Пользователь: {item.text}")
            else:
                lines.append(f"Ассистент: {item.text}")
        lines.extend(
            [
                "",
                "Результаты команд:",
                json.dumps(tool_results, ensure_ascii=False),
                "",
                "Ассистент:",
            ]
        )
        if preferred_language:
            lines.insert(3, self._build_language_instruction(preferred_language))
            lines.insert(4, "")
        return "\n".join(lines)

    def _extract_telegram_documents(
        self,
        execution: dict[str, object],
        *,
        command: str,
    ) -> tuple[list[AssistantDocument], dict[str, object]]:
        sanitized = dict(execution)
        raw_documents = sanitized.pop("telegram_documents", None)
        if not isinstance(raw_documents, list):
            return [], sanitized

        documents: list[AssistantDocument] = []
        skipped = 0
        for index, item in enumerate(raw_documents):
            if len(documents) >= _MAX_TELEGRAM_DOCUMENTS_PER_TURN:
                skipped += 1
                continue
            if not isinstance(item, dict):
                skipped += 1
                continue

            filename = str(item.get("filename", "")).strip()
            content_base64 = str(item.get("content_base64", "")).strip()
            caption = str(item.get("caption", "")).strip()
            if not filename or not content_base64:
                skipped += 1
                continue

            try:
                content = base64.b64decode(content_base64, validate=True)
            except (binascii.Error, ValueError):
                logger.warning(
                    "Ignoring invalid telegram document payload: user_command=%s index=%s",
                    command,
                    index,
                )
                skipped += 1
                continue
            if len(content) > _MAX_TELEGRAM_DOCUMENT_BYTES:
                logger.warning(
                    "Ignoring oversized telegram document payload: user_command=%s index=%s bytes=%d",
                    command,
                    index,
                    len(content),
                )
                skipped += 1
                continue

            documents.append(
                AssistantDocument(
                    filename=filename,
                    content=content,
                    caption=caption,
                )
            )

        if documents:
            sanitized["telegram_documents_count"] = len(documents)
        if skipped:
            sanitized["telegram_documents_skipped"] = skipped
        return documents, sanitized

    async def _get_preferred_reply_language(self, user_id: int) -> str | None:
        if not self._user_settings_store:
            return None
        try:
            raw_value = await self._user_settings_store.get_setting(user_id=user_id, key="language")
        except Exception as exc:
            logger.debug(
                "Failed to read preferred language setting: user_id=%s error=%s",
                user_id,
                exc,
            )
            return None
        normalized = self._normalize_language(raw_value)
        logger.debug(
            "Preferred language resolved: user_id=%s raw=%s normalized=%s",
            user_id,
            raw_value,
            normalized,
        )
        return normalized

    @staticmethod
    def _normalize_language(raw_value: str | None) -> str | None:
        if not raw_value:
            return None
        normalized = raw_value.strip().lower().replace("_", "-")
        if not normalized:
            return None

        short = normalized.split("-", 1)[0]
        aliases = {
            "ru": "ru",
            "russian": "ru",
            "en": "en",
            "english": "en",
        }
        return aliases.get(short, short)

    @staticmethod
    def _build_language_instruction(language: str) -> str:
        if language == "ru":
            return "Reply in Russian unless user asks otherwise."
        if language == "en":
            return "Reply in English unless user asks otherwise."
        return f"Reply in {language} unless user asks otherwise."

    def _extract_tool_calls(self, llm_text: str) -> list[_ToolCall]:
        calls: list[_ToolCall] = []
        for pattern in _TOOL_CALL_PATTERNS:
            for chunk in pattern.findall(llm_text):
                parsed = self._parse_tool_call_chunk(chunk)
                if parsed is None:
                    continue
                calls.append(parsed)
        if calls:
            logger.debug(
                "Extracted tool calls: commands=%s",
                ", ".join(call.command for call in calls),
            )
            return calls

        for chunk in self._extract_plain_json_chunks(llm_text):
            parsed = self._parse_tool_call_chunk(chunk)
            if parsed is None:
                continue
            calls.append(parsed)
        if calls:
            logger.debug(
                "Extracted tool calls: commands=%s",
                ", ".join(call.command for call in calls),
            )
        return calls

    @staticmethod
    def _parse_tool_call_chunk(chunk: str) -> _ToolCall | None:
        try:
            payload = json.loads(chunk)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        command = payload.get("command")
        args = payload.get("args", {})
        if not isinstance(command, str) or not isinstance(args, dict):
            return None
        return _ToolCall(command=command, args=args)

    @staticmethod
    def _extract_plain_json_chunks(llm_text: str) -> tuple[str, ...]:
        normalized = llm_text.strip()
        if not normalized:
            return ()

        if normalized.startswith("```"):
            lines = normalized.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                normalized = "\n".join(lines[1:-1]).strip()

        decoder = json.JSONDecoder()
        chunks: list[str] = []
        index = 0
        while index < len(normalized):
            while index < len(normalized) and normalized[index].isspace():
                index += 1
            if index >= len(normalized):
                break
            try:
                payload, end_index = decoder.raw_decode(normalized, idx=index)
            except json.JSONDecodeError:
                return ()
            if not isinstance(payload, dict):
                return ()
            chunks.append(normalized[index:end_index])
            index = end_index
        return tuple(chunks)

    @staticmethod
    def _build_compact_command_catalog(
        command_catalog: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        compact: list[dict[str, object]] = []
        for item in command_catalog:
            command = item.get("command")
            if not isinstance(command, str) or not command.strip():
                continue
            normalized_command = command.strip()
            description = item.get("description")
            args = item.get("args")
            compact.append(
                {
                    "command": normalized_command,
                    "description": description.strip() if isinstance(description, str) else "",
                    "args": args if isinstance(args, dict) else {},
                }
            )
        return compact
