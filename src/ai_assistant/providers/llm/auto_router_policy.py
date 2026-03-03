from __future__ import annotations

import json

from ai_assistant.providers.llm.auto_router_types import RouterCatalogEntry


ROUTER_POLICY_TEXT = """You are a routing model.
Choose the best specialist model queue for the incoming user request.

You MUST evaluate:
- task complexity and reasoning depth,
- expected context size,
- domain specificity (for example coding, data analysis),
- risk and error criticality (medicine, law, finance, safety-critical topics),
- cost/performance balance.

Routing rules:
- Prefer cheap local models for simple low-risk tasks.
- Prefer stronger cloud models for high-risk or hard tasks.
- Return multiple candidates ordered by priority for fallback handling.
- Include confidence (0..1), risk_level, complexity, topic, required_capabilities.
- Output ONLY one JSON object, no markdown and no extra text.
"""


def build_router_prompt(
    *,
    user_text: str,
    candidate_catalog: tuple[RouterCatalogEntry, ...],
) -> str:
    catalog_payload = [
        {
            "provider": item.provider,
            "model": item.model,
            "platform": item.platform,
            "cost_tier": item.cost_tier,
            "notes": item.notes,
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
        user_text,
        "",
        "Output schema (JSON only):",
        '{"confidence":0.0,"risk_level":"low|medium|high","complexity":"low|medium|high","topic":"coding",'
        '"required_capabilities":["reasoning"],'
        '"candidates":[{"provider":"ollama","model":"qwen3:8b","tier":"cheap_local","reason":"..."}],'
        '"arbiter":{"enabled":false,"provider":"openai","model":"gpt-4.1-mini"}}',
    ]
    return "\n".join(lines)
