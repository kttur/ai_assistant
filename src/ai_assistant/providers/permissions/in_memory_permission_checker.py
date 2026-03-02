from __future__ import annotations

from collections import defaultdict


class InMemoryPermissionChecker:
    def __init__(self, allow_all: bool = True) -> None:
        self._allow_all = allow_all
        self._permission_ids: dict[tuple[str, str], int] = {}
        self._next_permission_id = 1
        self._user_permissions: dict[int, dict[int, bool]] = defaultdict(dict)
        self._roles: dict[int, str] = {}
        self._next_role_id = 1
        self._role_permissions: dict[int, set[int]] = defaultdict(set)
        self._user_roles: dict[int, set[int]] = defaultdict(set)

    async def has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        if self._allow_all:
            return True

        key = (permission_type.strip().lower(), name.strip().lower())
        permission_id = self._permission_ids.get(key)
        if permission_id is None:
            return False

        user_override = self._user_permissions.get(user_id, {}).get(permission_id)
        if user_override is not None:
            return bool(user_override)

        user_role_ids = self._user_roles.get(user_id, set())
        for role_id in user_role_ids:
            if permission_id in self._role_permissions.get(role_id, set()):
                return True
        return False

    async def set_user_permission(
        self,
        user_id: int,
        permission_type: str,
        name: str,
        is_active: bool,
    ) -> None:
        self.set_user_permission_sync(user_id, permission_type, name, is_active)

    async def create_role(self, role_name: str) -> None:
        self.ensure_role(role_name)

    async def assign_role(self, user_id: int, role_name: str) -> None:
        self.assign_role_sync(user_id, role_name)

    async def grant_role_permission(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        self.grant_role_permission_sync(role_name, permission_type, name)

    async def revoke_role_permission(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        normalized_role = role_name.strip().lower()
        role_id = None
        for current_id, current_name in self._roles.items():
            if current_name == normalized_role:
                role_id = current_id
                break
        if role_id is None:
            return
        permission_id = self._permission_ids.get(
            (permission_type.strip().lower(), name.strip().lower())
        )
        if permission_id is None:
            return
        self._role_permissions.get(role_id, set()).discard(permission_id)

    async def get_user_roles(self, user_id: int) -> list[str]:
        role_ids = self._user_roles.get(user_id, set())
        result = [self._roles[role_id] for role_id in role_ids if role_id in self._roles]
        return sorted(result)

    async def get_user_permission_report(
        self,
        user_id: int,
    ) -> dict[str, list[dict[str, object]]]:
        user_overrides: list[dict[str, object]] = []
        role_permissions: list[dict[str, object]] = []

        permission_by_id = {perm_id: key for key, perm_id in self._permission_ids.items()}

        for permission_id, is_active in self._user_permissions.get(user_id, {}).items():
            key = permission_by_id.get(permission_id)
            if not key:
                continue
            perm_type, perm_name = key
            user_overrides.append(
                {
                    "type": perm_type,
                    "name": perm_name,
                    "is_active": bool(is_active),
                }
            )

        for role_id in self._user_roles.get(user_id, set()):
            role_name = self._roles.get(role_id)
            if not role_name:
                continue
            for permission_id in self._role_permissions.get(role_id, set()):
                key = permission_by_id.get(permission_id)
                if not key:
                    continue
                perm_type, perm_name = key
                role_permissions.append(
                    {
                        "role": role_name,
                        "type": perm_type,
                        "name": perm_name,
                    }
                )

        user_overrides.sort(key=lambda item: (str(item["type"]), str(item["name"])))
        role_permissions.sort(
            key=lambda item: (str(item["role"]), str(item["type"]), str(item["name"]))
        )

        override_map: dict[tuple[str, str], bool] = {
            (str(item["type"]), str(item["name"])): bool(item["is_active"])
            for item in user_overrides
        }
        role_map: dict[tuple[str, str], set[str]] = {}
        for item in role_permissions:
            key = (str(item["type"]), str(item["name"]))
            role_map.setdefault(key, set()).add(str(item["role"]))

        all_keys = sorted(set(override_map.keys()) | set(role_map.keys()))
        effective: list[dict[str, object]] = []
        for perm_type, perm_name in all_keys:
            if (perm_type, perm_name) in override_map:
                is_active = override_map[(perm_type, perm_name)]
                source = "user_override"
            else:
                is_active = True
                source = "role"
            roles = sorted(role_map.get((perm_type, perm_name), set()))
            effective.append(
                {
                    "type": perm_type,
                    "name": perm_name,
                    "is_active": is_active,
                    "source": source,
                    "roles": roles,
                }
            )

        return {
            "user_overrides": user_overrides,
            "role_permissions": role_permissions,
            "effective": effective,
        }

    # Helpers for tests/local bootstrap.
    def ensure_permission(self, permission_type: str, name: str) -> int:
        key = (permission_type.strip().lower(), name.strip().lower())
        existing = self._permission_ids.get(key)
        if existing is not None:
            return existing
        permission_id = self._next_permission_id
        self._next_permission_id += 1
        self._permission_ids[key] = permission_id
        return permission_id

    def set_user_permission_sync(
        self,
        user_id: int,
        permission_type: str,
        name: str,
        is_active: bool,
    ) -> None:
        permission_id = self.ensure_permission(permission_type, name)
        self._user_permissions[user_id][permission_id] = bool(is_active)

    def ensure_role(self, role_name: str) -> int:
        normalized = role_name.strip().lower()
        for role_id, existing_name in self._roles.items():
            if existing_name == normalized:
                return role_id
        role_id = self._next_role_id
        self._next_role_id += 1
        self._roles[role_id] = normalized
        return role_id

    def grant_role_permission_sync(self, role_name: str, permission_type: str, name: str) -> None:
        role_id = self.ensure_role(role_name)
        permission_id = self.ensure_permission(permission_type, name)
        self._role_permissions[role_id].add(permission_id)

    def assign_role_sync(self, user_id: int, role_name: str) -> None:
        role_id = self.ensure_role(role_name)
        self._user_roles[user_id].add(role_id)
