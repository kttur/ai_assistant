import pytest

from ai_assistant.providers.llm.arbiter import (
    ArbiterDecisionParseError,
    build_arbiter_prompt,
    build_regeneration_prompt,
    parse_arbiter_decision,
)


def test_parse_arbiter_decision_accepts_json() -> None:
    decision = parse_arbiter_decision(
        '{"action":"edit","final_answer":"updated","feedback":"fixed factual claim"}'
    )

    assert decision.action == "edit"
    assert decision.final_answer == "updated"
    assert decision.feedback == "fixed factual claim"


def test_parse_arbiter_decision_extracts_wrapped_json() -> None:
    decision = parse_arbiter_decision(
        "```json\n"
        '{"action":"regenerate","regenerate_prompt":"add citations"}\n'
        "```"
    )

    assert decision.action == "regenerate"
    assert decision.regenerate_prompt == "add citations"


def test_parse_arbiter_decision_raises_for_invalid_action() -> None:
    with pytest.raises(ArbiterDecisionParseError):
        parse_arbiter_decision('{"action":"noop"}')


def test_build_arbiter_prompt_contains_user_and_draft() -> None:
    prompt = build_arbiter_prompt(user_text="question", specialist_answer="draft")
    assert "question" in prompt
    assert "draft" in prompt


def test_build_regeneration_prompt_contains_feedback_and_instruction() -> None:
    prompt = build_regeneration_prompt(
        original_user_text="question",
        arbiter_feedback="too vague",
        regeneration_instruction="be specific",
    )
    assert "question" in prompt
    assert "too vague" in prompt
    assert "be specific" in prompt

