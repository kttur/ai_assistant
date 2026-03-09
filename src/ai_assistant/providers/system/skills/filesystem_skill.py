from __future__ import annotations

import base64
import codecs
from datetime import datetime, timezone
from pathlib import Path

from ai_assistant.skills.models import ExecutableSkill, SkillCommandSpec, SkillSpec

_DEFAULT_MAX_ITEMS = 200
_MAX_LIST_ITEMS = 500
_DEFAULT_MAX_READ_CHARS = 4000
_MAX_READ_CHARS = 200000
_DEFAULT_ENCODING = "utf-8"
_MAX_TELEGRAM_DOCUMENT_BYTES = 20 * 1024 * 1024


def build_filesystem_skill() -> ExecutableSkill:
    spec = SkillSpec(
        skill_id="filesystem",
        title="Filesystem inspection",
        llm_description=(
            "Inspect local filesystem content: list files/folders, read file metadata/content, and write text files."
        ),
        commands=(
            SkillCommandSpec(
                command="filesystem.list_directory",
                description="List files and folders in a directory.",
                args={
                    "path": "directory path; relative paths are resolved from current working directory",
                    "max_items": "optional integer 1..500, default 200",
                },
            ),
            SkillCommandSpec(
                command="filesystem.file_info",
                description="Get metadata for a single file.",
                args={
                    "path": "file path; relative paths are resolved from current working directory",
                },
            ),
            SkillCommandSpec(
                command="filesystem.read_file",
                description="Read text content from a file.",
                args={
                    "path": "file path; relative paths are resolved from current working directory",
                    "encoding": "optional text encoding, default utf-8",
                    "max_chars": "optional integer 1..200000, default 4000",
                },
            ),
            SkillCommandSpec(
                command="filesystem.write_file",
                description="Write text content to a file (overwrite or append).",
                args={
                    "path": "file path; relative paths are resolved from current working directory",
                    "content": "text content to write",
                    "encoding": "optional text encoding, default utf-8",
                    "append": "optional boolean, true appends to file, false overwrites",
                    "create_parents": "optional boolean, create missing parent directories",
                    "send_to_telegram": "optional boolean, include written file for Telegram delivery",
                    "telegram_filename": "optional file name for Telegram attachment",
                    "telegram_caption": "optional caption for Telegram attachment",
                },
            ),
            SkillCommandSpec(
                command="filesystem.send_file",
                description="Load existing file and include it for Telegram delivery.",
                args={
                    "path": "file path; relative paths are resolved from current working directory",
                    "telegram_filename": "optional file name for Telegram attachment",
                    "telegram_caption": "optional caption for Telegram attachment",
                },
            ),
        ),
    )

    def execute(command: str, args: dict[str, object]) -> dict[str, object]:
        if command == "filesystem.list_directory":
            return _list_directory(args)
        if command == "filesystem.file_info":
            return _file_info(args)
        if command == "filesystem.read_file":
            return _read_file(args)
        if command == "filesystem.write_file":
            return _write_file(args)
        if command == "filesystem.send_file":
            return _send_file(args)
        return {"ok": False, "message": f"Unknown command: {command}"}

    return ExecutableSkill(spec=spec, execute=execute)


def _list_directory(args: dict[str, object]) -> dict[str, object]:
    directory_path, path_error = _parse_path_arg(args=args, key="path", default=".")
    if path_error:
        return {"ok": False, "message": path_error}

    max_items, max_items_error = _parse_max_items(args.get("max_items"))
    if max_items_error:
        return {"ok": False, "message": max_items_error}

    assert directory_path is not None
    assert max_items is not None

    if not directory_path.exists():
        return {"ok": False, "message": f"Directory does not exist: {_stringify_path(directory_path)}"}
    if not directory_path.is_dir():
        return {"ok": False, "message": f"Path is not a directory: {_stringify_path(directory_path)}"}

    try:
        children = sorted(directory_path.iterdir(), key=_entry_sort_key)
    except OSError as exc:
        return {"ok": False, "message": f"Unable to list directory: {exc}"}

    entries: list[dict[str, object]] = []
    errors: list[str] = []
    for child in children[:max_items]:
        try:
            child_stat = child.stat()
            is_directory = child.is_dir()
            is_file = child.is_file()
        except OSError as exc:
            errors.append(f"{child.name}: {exc}")
            continue

        kind = "directory" if is_directory else "file" if is_file else "other"
        entries.append(
            {
                "name": child.name,
                "path": _stringify_path(child),
                "kind": kind,
                "size_bytes": child_stat.st_size if is_file else None,
                "created_at": _to_utc_iso(child_stat.st_ctime),
                "modified_at": _to_utc_iso(child_stat.st_mtime),
            }
        )

    listed_path = _stringify_path(directory_path)
    return {
        "ok": True,
        "message": f"Directory listed: {listed_path}",
        "path": listed_path,
        "total_entries": len(children),
        "returned_entries": len(entries),
        "truncated": len(children) > max_items,
        "entries": entries,
        "errors": errors,
    }


def _file_info(args: dict[str, object]) -> dict[str, object]:
    file_path, path_error = _parse_path_arg(args=args, key="path")
    if path_error:
        return {"ok": False, "message": path_error}

    assert file_path is not None

    if not file_path.exists():
        return {"ok": False, "message": f"File does not exist: {_stringify_path(file_path)}"}
    if not file_path.is_file():
        return {"ok": False, "message": f"Path is not a file: {_stringify_path(file_path)}"}

    try:
        file_stat = file_path.stat()
    except OSError as exc:
        return {"ok": False, "message": f"Unable to read file metadata: {exc}"}

    resolved_path = _stringify_path(file_path)
    return {
        "ok": True,
        "message": f"File info collected: {resolved_path}",
        "file": {
            "name": file_path.name,
            "path": resolved_path,
            "parent": _stringify_path(file_path.parent),
            "suffix": file_path.suffix,
            "size_bytes": file_stat.st_size,
            "created_at": _to_utc_iso(file_stat.st_ctime),
            "modified_at": _to_utc_iso(file_stat.st_mtime),
            "accessed_at": _to_utc_iso(file_stat.st_atime),
        },
    }


def _read_file(args: dict[str, object]) -> dict[str, object]:
    file_path, path_error = _parse_path_arg(args=args, key="path")
    if path_error:
        return {"ok": False, "message": path_error}

    encoding, encoding_error = _parse_encoding(args.get("encoding"))
    if encoding_error:
        return {"ok": False, "message": encoding_error}

    max_chars, max_chars_error = _parse_max_read_chars(args.get("max_chars"))
    if max_chars_error:
        return {"ok": False, "message": max_chars_error}

    assert file_path is not None
    assert encoding is not None
    assert max_chars is not None

    if not file_path.exists():
        return {"ok": False, "message": f"File does not exist: {_stringify_path(file_path)}"}
    if not file_path.is_file():
        return {"ok": False, "message": f"Path is not a file: {_stringify_path(file_path)}"}

    try:
        with file_path.open(mode="r", encoding=encoding) as handle:
            raw_text = handle.read(max_chars + 1)
    except LookupError:
        return {"ok": False, "message": f"Unknown encoding: {encoding}"}
    except UnicodeDecodeError as exc:
        return {"ok": False, "message": f"Unable to decode file with {encoding}: {exc}"}
    except OSError as exc:
        return {"ok": False, "message": f"Unable to read file: {exc}"}

    truncated = len(raw_text) > max_chars
    content = raw_text[:max_chars]

    try:
        file_stat = file_path.stat()
    except OSError:
        file_stat = None

    resolved_path = _stringify_path(file_path)
    return {
        "ok": True,
        "message": f"File read: {resolved_path}",
        "path": resolved_path,
        "encoding": encoding,
        "returned_chars": len(content),
        "truncated": truncated,
        "max_chars": max_chars,
        "size_bytes": file_stat.st_size if file_stat is not None else None,
        "content": content,
    }


def _write_file(args: dict[str, object]) -> dict[str, object]:
    file_path, path_error = _parse_path_arg(args=args, key="path")
    if path_error:
        return {"ok": False, "message": path_error}

    content = args.get("content")
    if not isinstance(content, str):
        return {"ok": False, "message": "content must be a string."}

    encoding, encoding_error = _parse_encoding(args.get("encoding"))
    if encoding_error:
        return {"ok": False, "message": encoding_error}

    append, append_error = _parse_bool_arg(args.get("append"), key="append", default=False)
    if append_error:
        return {"ok": False, "message": append_error}

    create_parents, create_parents_error = _parse_bool_arg(
        args.get("create_parents"),
        key="create_parents",
        default=False,
    )
    if create_parents_error:
        return {"ok": False, "message": create_parents_error}

    assert file_path is not None
    assert encoding is not None
    assert append is not None
    assert create_parents is not None

    send_to_telegram, send_to_telegram_error = _parse_bool_arg(
        args.get("send_to_telegram"),
        key="send_to_telegram",
        default=False,
    )
    if send_to_telegram_error:
        return {"ok": False, "message": send_to_telegram_error}

    telegram_filename, filename_error = _parse_optional_string_arg(
        args.get("telegram_filename"),
        key="telegram_filename",
    )
    if filename_error:
        return {"ok": False, "message": filename_error}
    telegram_caption, caption_error = _parse_optional_string_arg(
        args.get("telegram_caption"),
        key="telegram_caption",
    )
    if caption_error:
        return {"ok": False, "message": caption_error}

    assert send_to_telegram is not None

    parent = file_path.parent
    if create_parents:
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"ok": False, "message": f"Unable to create parent directories: {exc}"}
    elif not parent.exists():
        return {
            "ok": False,
            "message": (
                f"Parent directory does not exist: {_stringify_path(parent)}. "
                "Set create_parents=true to create it."
            ),
        }

    if file_path.exists() and file_path.is_dir():
        return {"ok": False, "message": f"Path is a directory: {_stringify_path(file_path)}"}

    mode = "a" if append else "w"
    try:
        with file_path.open(mode=mode, encoding=encoding) as handle:
            chars_written = handle.write(content)
    except LookupError:
        return {"ok": False, "message": f"Unknown encoding: {encoding}"}
    except OSError as exc:
        return {"ok": False, "message": f"Unable to write file: {exc}"}

    try:
        file_stat = file_path.stat()
        size_bytes: int | None = file_stat.st_size
    except OSError:
        size_bytes = None

    resolved_path = _stringify_path(file_path)
    result: dict[str, object] = {
        "ok": True,
        "message": f"File written: {resolved_path}",
        "path": resolved_path,
        "encoding": encoding,
        "mode": "append" if append else "overwrite",
        "chars_written": chars_written,
        "size_bytes": size_bytes,
    }
    if send_to_telegram:
        document_payload, document_error = _build_telegram_document_for_path(
            file_path=file_path,
            telegram_filename=telegram_filename,
            telegram_caption=telegram_caption,
        )
        if document_error is not None:
            result["message"] = f"{result['message']} (telegram export skipped: {document_error})"
            result["telegram_export_error"] = document_error
        elif document_payload is not None:
            result["telegram_documents"] = [document_payload]
            result["telegram_documents_count"] = 1
    return result


def _send_file(args: dict[str, object]) -> dict[str, object]:
    file_path, path_error = _parse_path_arg(args=args, key="path")
    if path_error:
        return {"ok": False, "message": path_error}

    telegram_filename, filename_error = _parse_optional_string_arg(
        args.get("telegram_filename"),
        key="telegram_filename",
    )
    if filename_error:
        return {"ok": False, "message": filename_error}
    telegram_caption, caption_error = _parse_optional_string_arg(
        args.get("telegram_caption"),
        key="telegram_caption",
    )
    if caption_error:
        return {"ok": False, "message": caption_error}

    assert file_path is not None

    if not file_path.exists():
        return {"ok": False, "message": f"File does not exist: {_stringify_path(file_path)}"}
    if not file_path.is_file():
        return {"ok": False, "message": f"Path is not a file: {_stringify_path(file_path)}"}

    document_payload, document_error = _build_telegram_document_for_path(
        file_path=file_path,
        telegram_filename=telegram_filename,
        telegram_caption=telegram_caption,
    )
    if document_error is not None or document_payload is None:
        return {
            "ok": False,
            "message": f"Unable to prepare file for Telegram: {document_error or 'unknown error'}",
        }

    resolved_path = _stringify_path(file_path)
    return {
        "ok": True,
        "message": f"File prepared for Telegram delivery: {resolved_path}",
        "path": resolved_path,
        "size_bytes": document_payload.get("size_bytes"),
        "telegram_documents_count": 1,
        "telegram_documents": [document_payload],
    }


def _parse_path_arg(
    *,
    args: dict[str, object],
    key: str,
    default: str | None = None,
) -> tuple[Path | None, str | None]:
    raw_value = args.get(key, default)
    if not isinstance(raw_value, str):
        return None, f"{key} must be a string path."

    normalized_value = raw_value.strip()
    if not normalized_value:
        if default is None:
            return None, f"{key} must not be empty."
        normalized_value = default

    return Path(normalized_value).expanduser(), None


def _parse_max_items(raw_value: object) -> tuple[int | None, str | None]:
    if raw_value is None:
        return _DEFAULT_MAX_ITEMS, None

    if isinstance(raw_value, bool):
        return None, "max_items must be an integer between 1 and 500."

    if isinstance(raw_value, int):
        value = raw_value
    elif isinstance(raw_value, str):
        normalized = raw_value.strip()
        if not normalized:
            return _DEFAULT_MAX_ITEMS, None
        try:
            value = int(normalized)
        except ValueError:
            return None, "max_items must be an integer between 1 and 500."
    else:
        return None, "max_items must be an integer between 1 and 500."

    if value < 1 or value > _MAX_LIST_ITEMS:
        return None, "max_items must be an integer between 1 and 500."

    return value, None


def _parse_max_read_chars(raw_value: object) -> tuple[int | None, str | None]:
    if raw_value is None:
        return _DEFAULT_MAX_READ_CHARS, None

    if isinstance(raw_value, bool):
        return None, "max_chars must be an integer between 1 and 200000."

    if isinstance(raw_value, int):
        value = raw_value
    elif isinstance(raw_value, str):
        normalized = raw_value.strip()
        if not normalized:
            return _DEFAULT_MAX_READ_CHARS, None
        try:
            value = int(normalized)
        except ValueError:
            return None, "max_chars must be an integer between 1 and 200000."
    else:
        return None, "max_chars must be an integer between 1 and 200000."

    if value < 1 or value > _MAX_READ_CHARS:
        return None, "max_chars must be an integer between 1 and 200000."

    return value, None


def _parse_encoding(raw_value: object) -> tuple[str | None, str | None]:
    if raw_value is None:
        return _DEFAULT_ENCODING, None
    if not isinstance(raw_value, str):
        return None, "encoding must be a string."

    encoding = raw_value.strip() or _DEFAULT_ENCODING
    try:
        codecs.lookup(encoding)
    except LookupError:
        return None, f"Unknown encoding: {encoding}"
    return encoding, None


def _parse_bool_arg(
    raw_value: object,
    *,
    key: str,
    default: bool,
) -> tuple[bool | None, str | None]:
    if raw_value is None:
        return default, None
    if isinstance(raw_value, bool):
        return raw_value, None
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True, None
        if normalized in {"0", "false", "no", "off"}:
            return False, None
    return None, f"{key} must be a boolean."


def _parse_optional_string_arg(
    raw_value: object,
    *,
    key: str,
) -> tuple[str | None, str | None]:
    if raw_value is None:
        return None, None
    if not isinstance(raw_value, str):
        return None, f"{key} must be a string."
    normalized = raw_value.strip()
    return normalized or None, None


def _build_telegram_document_for_path(
    *,
    file_path: Path,
    telegram_filename: str | None,
    telegram_caption: str | None,
) -> tuple[dict[str, object] | None, str | None]:
    try:
        size_bytes = file_path.stat().st_size
    except OSError as exc:
        return None, f"unable to read file metadata: {exc}"

    if size_bytes > _MAX_TELEGRAM_DOCUMENT_BYTES:
        return (
            None,
            f"file is too large for telegram payload ({size_bytes} bytes, max {_MAX_TELEGRAM_DOCUMENT_BYTES})",
        )

    try:
        content_bytes = file_path.read_bytes()
    except OSError as exc:
        return None, f"unable to read file bytes: {exc}"

    filename = telegram_filename or file_path.name
    payload = {
        "filename": filename,
        "caption": telegram_caption or "",
        "content_base64": base64.b64encode(content_bytes).decode("ascii"),
        "size_bytes": len(content_bytes),
        "source_path": _stringify_path(file_path),
    }
    return payload, None


def _entry_sort_key(path: Path) -> tuple[int, str]:
    try:
        is_dir = path.is_dir()
    except OSError:
        is_dir = False
    return (0 if is_dir else 1, path.name.lower())


def _to_utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _stringify_path(path: Path) -> str:
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path)
