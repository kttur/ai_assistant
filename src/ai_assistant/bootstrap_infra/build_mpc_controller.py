from __future__ import annotations

from ai_assistant.core.interfaces import MPCController
from ai_assistant.providers.system.mpc_hc_controller import MpcHcController


def build_mpc_controller() -> MPCController | None:
    try:
        return MpcHcController()
    except RuntimeError:
        return None
