from __future__ import annotations

import json


class RemoteProtocolError(ValueError):
    pass


def encode_message(
    *,
    message_type: str,
    payload: dict[str, object],
    request_id: str | None = None,
) -> str:
    envelope: dict[str, object] = {
        "type": message_type,
        "payload": payload,
    }
    if request_id:
        envelope["request_id"] = request_id
    return json.dumps(envelope, ensure_ascii=False)


def decode_message(raw_message: str) -> tuple[str, dict[str, object], str | None]:
    try:
        parsed = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise RemoteProtocolError("Message is not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise RemoteProtocolError("Message envelope must be an object.")

    message_type = parsed.get("type")
    payload = parsed.get("payload")
    request_id = parsed.get("request_id")

    if not isinstance(message_type, str) or not message_type.strip():
        raise RemoteProtocolError("Message type is required.")

    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise RemoteProtocolError("Message payload must be an object.")

    normalized_request_id: str | None
    if request_id is None:
        normalized_request_id = None
    elif isinstance(request_id, str) and request_id.strip():
        normalized_request_id = request_id
    else:
        raise RemoteProtocolError("request_id must be a non-empty string when provided.")

    return message_type.strip(), payload, normalized_request_id
