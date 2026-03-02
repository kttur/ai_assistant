from ai_assistant.providers.system.voicemeeter_output_controller import VoicemeeterOutputController


def test_build_param_candidates_default_and_override() -> None:
    default_candidates = VoicemeeterOutputController._build_param_candidates(
        strip_index=5,
        bus="A1",
        output_param="",
    )
    assert default_candidates == ["Strip[5].A1", "Strip(5).A1"]

    override_candidates = VoicemeeterOutputController._build_param_candidates(
        strip_index=5,
        bus="A1",
        output_param="Strip(5).A2",
    )
    assert override_candidates == ["Strip(5).A2"]


def test_build_param_candidates_override_with_brackets_adds_parentheses() -> None:
    override_candidates = VoicemeeterOutputController._build_param_candidates(
        strip_index=5,
        bus="A1",
        output_param="Strip[5].A1",
    )
    assert override_candidates == ["Strip[5].A1"]
