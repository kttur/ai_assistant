from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RouterCatalogEntry:
    provider: str
    model: str
    platform: str
    cost_tier: str
    notes: str = ""


@dataclass(slots=True, frozen=True)
class RouteCandidate:
    provider: str
    model: str
    tier: str = ""
    reason: str = ""


@dataclass(slots=True, frozen=True)
class RouteArbiter:
    enabled: bool
    provider: str | None = None
    model: str | None = None


@dataclass(slots=True, frozen=True)
class RouteDecision:
    confidence: float
    risk_level: str
    complexity: str
    required_capabilities: tuple[str, ...]
    candidates: tuple[RouteCandidate, ...]
    arbiter: RouteArbiter | None = None


class RouteDecisionParseError(RuntimeError):
    pass


def parse_route_decision(raw_text: str) -> RouteDecision:
    payload = _extract_json_payload(raw_text)
    if not isinstance(payload, dict):
        raise RouteDecisionParseError("Router reply payload is not a JSON object.")

    candidates_raw = payload.get("candidates")
    if not isinstance(candidates_raw, list):
        raise RouteDecisionParseError("Router reply does not contain candidates list.")

    candidates: list[RouteCandidate] = []
    for item in candidates_raw:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider", "")).strip().lower()
        model = str(item.get("model", "")).strip()
        if not provider or not model:
            continue
        candidates.append(
            RouteCandidate(
                provider=provider,
                model=model,
                tier=str(item.get("tier", "")).strip(),
                reason=str(item.get("reason", "")).strip(),
            )
        )
    if not candidates:
        raise RouteDecisionParseError("Router reply has no valid candidates.")

    arbiter = _parse_arbiter(payload.get("arbiter"))
    confidence = _parse_confidence(payload.get("confidence"))
    risk_level = str(payload.get("risk_level", "unknown")).strip().lower() or "unknown"
    complexity = str(payload.get("complexity", "unknown")).strip().lower() or "unknown"
    required_capabilities = _parse_required_capabilities(payload.get("required_capabilities"))

    return RouteDecision(
        confidence=confidence,
        risk_level=risk_level,
        complexity=complexity,
        required_capabilities=required_capabilities,
        candidates=tuple(candidates),
        arbiter=arbiter,
    )


def _extract_json_payload(raw_text: str) -> object:
    text = raw_text.strip()
    if not text:
        raise RouteDecisionParseError("Router reply is empty.")

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

    raise RouteDecisionParseError("Router reply does not contain JSON object.")


def _parse_confidence(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return min(1.0, max(0.0, float(value)))
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return 0.0
        return min(1.0, max(0.0, parsed))
    return 0.0


def _parse_required_capabilities(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        normalized = str(raw_item).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


def _parse_arbiter(value: object) -> RouteArbiter | None:
    if not isinstance(value, dict):
        return None
    enabled = bool(value.get("enabled", False))
    provider = str(value.get("provider", "")).strip().lower() or None
    model = str(value.get("model", "")).strip() or None
    return RouteArbiter(enabled=enabled, provider=provider, model=model)

