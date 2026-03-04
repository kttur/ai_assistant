from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ClientState:
    client_id: str
    auth_token: str
    server_id: str


class FileClientStateStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path).expanduser()

    def load(self) -> ClientState | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        client_id = str(payload.get("client_id", "")).strip().lower()
        auth_token = str(payload.get("auth_token", "")).strip()
        server_id = str(payload.get("server_id", "")).strip().lower()
        if not client_id:
            return None
        return ClientState(client_id=client_id, auth_token=auth_token, server_id=server_id)

    def save(self, state: ClientState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "client_id": state.client_id,
            "auth_token": state.auth_token,
            "server_id": state.server_id,
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
