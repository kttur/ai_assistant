from __future__ import annotations


def _is_command_runtime_available(self, command_name: str) -> bool:
    if command_name in {"set", "settings", "settings_raw"}:
        return self._user_settings_store is not None
    if command_name in {"grant", "revoke", "role_add", "role_assign", "user_roles", "user_permissions"}:
        return self._permission_admin is not None
    if command_name in {"terminal", "exit"}:
        return self._terminal_executor is not None
    if command_name == "mpc":
        return self._mpc_controller is not None
    if command_name == "player":
        return self._media_controller is not None or self._output_controller is not None
    if command_name == "pc_link":
        return self._remote_ws_hub is not None
    if command_name in {"pc_list", "pc_default", "pc_share", "pc_unshare", "pc_unlink", "pc_run"}:
        return self._remote_device_service is not None and self._remote_ws_hub is not None
    return True
