from __future__ import annotations

import json
from dataclasses import dataclass


ARBITER_SYSTEM_PROMPT = """You are a response arbiter.
Validate the draft answer from a specialist model against the user request.

Your goals:
- detect critical mistakes and unsafe claims,
- improve clarity and factual reliability,
- keep edits minimal when the answer is already good.

Return JSON only with schema:
{
  "action": "approve|edit|regenerate",
  "final_answer": "text",
  "feedback": "short rationale",
  "regenerate_prompt": "extra instructions for specialist model"
}
"""


@dataclass(slots=True, frozen=True)
class ArbiterDecision:
    action: str
    final_answer: str = ""
    feedback: str = ""
    regenerate_prompt: str = ""


class ArbiterDecisionParseError(RuntimeError):
    pass


def build_arbiter_prompt(*, user_text: str, specialist_answer: str) -> str:
    lines = [
        ARBITER_SYSTEM_PROMPT,
        "",
        "User request:",
        user_text,
        "",
        "Specialist answer draft:",
        specialist_answer,
    ]
    return "\n".join(lines)


def build_regeneration_prompt(
    *,
    original_user_text: str,
    arbiter_feedback: str,
    regeneration_instruction: str,
) -> str:
    lines = [
        original_user_text,
        "",
        "Arbiter feedback:",
        arbiter_feedback or "(none)",
        "",
        "Regenerate answer with these additional constraints:",
        regeneration_instruction,
    ]
    return "\n".join(lines)


def parse_arbiter_decision(raw_text: str) -> ArbiterDecision:
    payload = _extract_json_payload(raw_text)
    if not isinstance(payload, dict):
        raise ArbiterDecisionParseError("Arbiter reply payload is not a JSON object.")

    action = str(payload.get("action", "")).strip().lower()
    if action not in {"approve", "edit", "regenerate"}:
        raise ArbiterDecisionParseError("Arbiter action is missing or invalid.")

    return ArbiterDecision(
        action=action,
        final_answer=str(payload.get("final_answer", "")).strip(),
        feedback=str(payload.get("feedback", "")).strip(),
        regenerate_prompt=str(payload.get("regenerate_prompt", "")).strip(),
    )


def _extract_json_payload(raw_text: str) -> object:
    text = raw_text.strip()
    if not text:
        raise ArbiterDecisionParseError("Arbiter reply is empty.")

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            text = "\n".join(lines[1:-1]).strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return parsed

    raise ArbiterDecisionParseError("Arbiter reply does not contain JSON object.")

