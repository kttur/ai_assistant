from __future__ import annotations

import json

from ai_assistant.providers.llm.auto_router_types import RouterCatalogEntry

_MAX_ROUTER_USER_TEXT_CHARS = 700
_USER_LINE_PREFIXES = ("Пользователь:", "User:")
_ROUTER_PROMPT_SPLIT_MARKERS = (
    "Available commands JSON:",
    "Результаты выполнения команд (JSON):",
)


ROUTER_POLICY_TEXT = """You are a routing model.
Choose the best specialist model queue for the incoming user request.

You MUST evaluate:
- task complexity and reasoning depth,
- whether explicit reasoning mode is needed or concise non-reasoning output is preferred,
- expected context size,
- domain specificity (for example coding, data analysis),
- risk and error criticality (medicine, law, finance, safety-critical topics),
- modality/ability requirements (images, documents, audio, tools/commands),
- cost/performance balance.

Routing rules:
- Prefer cheap local models for simple low-risk tasks.
- Prefer stronger cloud models for high-risk or hard tasks.
- For medicine/healthcare requests, prioritize medically specialized models from the catalog
  (for example names/notes with med, medical, clinical), with a safe fallback chain.
- Use `priority` and `strength` fields from catalog metadata.
  For hard/high-risk requests prefer higher `strength`; for equal strength prefer lower `priority`.
- Return multiple candidates ordered by priority for fallback handling.
- Include confidence (0..1), risk_level, complexity, topic, required_capabilities.
- Output ONLY one JSON object, no markdown and no extra text.
"""

ROUTER_QUICK_POLICY_TEXT = """Route this simple command to the best model.
Rules: prefer cheap_local → balanced_local → cheap_cloud.
Use priority (lower is better) and strength (higher is better for complex tasks).
Output JSON only, no markdown."""


def build_router_prompt(
    *,
    user_text: str,
    candidate_catalog: tuple[RouterCatalogEntry, ...],
    quick_mode: bool = False,
) -> str:
    compact_user_text = _compact_router_user_text(user_text)

    if quick_mode:
        # Minimal catalog for quick commands
        catalog_payload = [
            {
                "provider": item.provider,
                "model": item.model,
                "cost_tier": item.cost_tier,
                "priority": item.priority,
                "strength": item.strength,
            }
            for item in candidate_catalog
        ]
        lines = [
            ROUTER_QUICK_POLICY_TEXT,
            "",
            "Models:",
            json.dumps(catalog_payload, ensure_ascii=False),
            "",
            "Request:",
            compact_user_text,
            "",
            "Output (JSON):",
            '{"confidence":0.8,"risk_level":"low","complexity":"low","topic":"command",'
            '"required_capabilities":[],'
            '"candidates":[{"provider":"ollama","model":"qwen3:8b","tier":"cheap_local","reason":"fast"}],'
            '"arbiter":{"enabled":false}}',
        ]
    else:
        # Full catalog for complex requests
        catalog_payload = [
            {
                "provider": item.provider,
                "model": item.model,
                "platform": item.platform,
                "cost_tier": item.cost_tier,
                "notes": item.notes,
                "tags": list(item.tags),
                "domains": list(item.domains),
                "roles": list(item.roles),
                "priority": item.priority,
                "strength": item.strength,
                "supports_reasoning": item.supports_reasoning,
                "supports_non_reasoning": item.supports_non_reasoning,
                "abilities": list(item.abilities),
            }
            for item in candidate_catalog
        ]
        lines = [
            ROUTER_POLICY_TEXT,
            "",
            "Candidate catalog JSON:",
            json.dumps(catalog_payload, ensure_ascii=False),
            "",
            "User request:",
            compact_user_text,
            "",
            "Output schema (JSON only):",
            '{"confidence":0.0,"risk_level":"low|medium|high","complexity":"low|medium|high","topic":"coding",'
            '"required_capabilities":["reasoning"],'
            '"candidates":[{"provider":"ollama","model":"qwen3:4b","tier":"cheap_local","reason":"..."}],'
            '"arbiter":{"enabled":false,"provider":"openai","model":"gpt-4.1-mini"}}',
        ]
    return "\n".join(lines)


def _compact_router_user_text(user_text: str) -> str:
    normalized = user_text.strip()
    if not normalized:
        return ""

    extracted_line = _extract_last_user_line(normalized)
    if extracted_line:
        normalized = extracted_line
    else:
        for marker in _ROUTER_PROMPT_SPLIT_MARKERS:
            if marker in normalized:
                normalized = normalized.split(marker, 1)[0].strip()
                break

    compact = " ".join(normalized.split())
    if len(compact) <= _MAX_ROUTER_USER_TEXT_CHARS:
        return compact
    return f"{compact[:_MAX_ROUTER_USER_TEXT_CHARS].rstrip()}..."


def _extract_last_user_line(text: str) -> str | None:
    for raw_line in reversed(text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        for prefix in _USER_LINE_PREFIXES:
            if line.startswith(prefix):
                candidate = line.removeprefix(prefix).strip()
                if candidate:
                    return candidate
    return None
