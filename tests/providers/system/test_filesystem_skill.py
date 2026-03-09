from pathlib import Path

from ai_assistant.providers.system.skills.filesystem_skill import build_filesystem_skill


def test_filesystem_skill_lists_directory_content(tmp_path: Path) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    skill = build_filesystem_skill()
    result = skill.execute(
        "filesystem.list_directory",
        {"path": str(tmp_path)},
    )

    assert result["ok"] is True
    assert result["path"] == str(tmp_path.resolve())
    assert result["total_entries"] == 2
    assert result["returned_entries"] == 2
    assert result["truncated"] is False

    entries = result["entries"]
    assert isinstance(entries, list)
    assert [item["name"] for item in entries] == ["alpha", "notes.txt"]
    assert entries[0]["kind"] == "directory"
    assert entries[0]["size_bytes"] is None
    assert entries[1]["kind"] == "file"
    assert entries[1]["size_bytes"] == 5


def test_filesystem_skill_respects_max_items(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("1", encoding="utf-8")
    (tmp_path / "two.txt").write_text("2", encoding="utf-8")

    skill = build_filesystem_skill()
    result = skill.execute(
        "filesystem.list_directory",
        {"path": str(tmp_path), "max_items": 1},
    )

    assert result["ok"] is True
    assert result["returned_entries"] == 1
    assert result["truncated"] is True


def test_filesystem_skill_returns_file_metadata(tmp_path: Path) -> None:
    file_path = tmp_path / "movie.mkv"
    file_path.write_bytes(b"abc123")

    skill = build_filesystem_skill()
    result = skill.execute(
        "filesystem.file_info",
        {"path": str(file_path)},
    )

    assert result["ok"] is True
    file_payload = result["file"]
    assert file_payload["name"] == "movie.mkv"
    assert file_payload["suffix"] == ".mkv"
    assert file_payload["size_bytes"] == 6
    assert file_payload["path"] == str(file_path.resolve())


def test_filesystem_skill_rejects_directory_for_file_info(tmp_path: Path) -> None:
    skill = build_filesystem_skill()
    result = skill.execute(
        "filesystem.file_info",
        {"path": str(tmp_path)},
    )

    assert result["ok"] is False
    assert "not a file" in str(result["message"])


def test_filesystem_skill_reads_file_content_with_limit(tmp_path: Path) -> None:
    file_path = tmp_path / "story.txt"
    file_path.write_text("abcdef", encoding="utf-8")

    skill = build_filesystem_skill()
    result = skill.execute(
        "filesystem.read_file",
        {"path": str(file_path), "max_chars": 3},
    )

    assert result["ok"] is True
    assert result["content"] == "abc"
    assert result["truncated"] is True
    assert result["returned_chars"] == 3


def test_filesystem_skill_writes_and_appends_file_content(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    skill = build_filesystem_skill()

    first = skill.execute(
        "filesystem.write_file",
        {"path": str(file_path), "content": "hello"},
    )
    second = skill.execute(
        "filesystem.write_file",
        {"path": str(file_path), "content": " world", "append": True},
    )

    assert first["ok"] is True
    assert first["mode"] == "overwrite"
    assert second["ok"] is True
    assert second["mode"] == "append"
    assert file_path.read_text(encoding="utf-8") == "hello world"


def test_filesystem_skill_requires_permissioned_write_payload(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    skill = build_filesystem_skill()

    no_content = skill.execute(
        "filesystem.write_file",
        {"path": str(file_path)},
    )
    missing_parent = skill.execute(
        "filesystem.write_file",
        {"path": str(tmp_path / "missing" / "notes.txt"), "content": "x"},
    )

    assert no_content["ok"] is False
    assert "content must be a string" in str(no_content["message"])
    assert missing_parent["ok"] is False
    assert "Parent directory does not exist" in str(missing_parent["message"])


def test_filesystem_skill_can_prepare_existing_file_for_telegram(tmp_path: Path) -> None:
    file_path = tmp_path / "hello.txt"
    file_path.write_text("hello", encoding="utf-8")
    skill = build_filesystem_skill()

    result = skill.execute(
        "filesystem.send_file",
        {"path": str(file_path), "telegram_caption": "doc"},
    )

    assert result["ok"] is True
    assert result["telegram_documents_count"] == 1
    documents = result["telegram_documents"]
    assert isinstance(documents, list)
    assert documents[0]["filename"] == "hello.txt"
    assert documents[0]["caption"] == "doc"
    assert documents[0]["content_base64"]


def test_filesystem_skill_can_write_and_prepare_file_for_telegram(tmp_path: Path) -> None:
    file_path = tmp_path / "generated.txt"
    skill = build_filesystem_skill()

    result = skill.execute(
        "filesystem.write_file",
        {
            "path": str(file_path),
            "content": "hello",
            "send_to_telegram": True,
            "telegram_filename": "result.txt",
        },
    )

    assert result["ok"] is True
    assert result["telegram_documents_count"] == 1
    documents = result["telegram_documents"]
    assert isinstance(documents, list)
    assert documents[0]["filename"] == "result.txt"
    assert file_path.read_text(encoding="utf-8") == "hello"
