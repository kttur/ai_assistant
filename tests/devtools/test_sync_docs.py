from ai_assistant.devtools.sync_docs import run


def test_generated_docs_are_in_sync() -> None:
    assert run(check=True) == 0

