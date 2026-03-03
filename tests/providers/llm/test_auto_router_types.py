import pytest

from ai_assistant.providers.llm.auto_router_types import (
    RouteDecisionParseError,
    parse_route_decision,
)


def test_parse_route_decision_accepts_plain_json() -> None:
    decision = parse_route_decision(
        '{"confidence":0.73,"risk_level":"high","complexity":"medium",'
        '"required_capabilities":["reasoning","coding"],'
        '"candidates":[{"provider":"ollama","model":"qwen3:8b"}]}'
    )

    assert decision.confidence == 0.73
    assert decision.risk_level == "high"
    assert decision.complexity == "medium"
    assert decision.required_capabilities == ("reasoning", "coding")
    assert decision.candidates[0].provider == "ollama"
    assert decision.candidates[0].model == "qwen3:8b"


def test_parse_route_decision_extracts_json_from_wrapped_text() -> None:
    decision = parse_route_decision(
        "Here is result:\n```json\n"
        '{"confidence":"0.2","candidates":[{"provider":"openai","model":"gpt-4.1-mini"}]}\n'
        "```"
    )

    assert decision.confidence == 0.2
    assert len(decision.candidates) == 1
    assert decision.candidates[0].provider == "openai"


def test_parse_route_decision_raises_for_missing_candidates() -> None:
    with pytest.raises(RouteDecisionParseError):
        parse_route_decision('{"confidence":0.9,"candidates":[]}')

