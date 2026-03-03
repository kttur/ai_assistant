from __future__ import annotations

ALLOWED_PERMISSION_TYPES = {"general", "command", "assistant"}


def normalize_role_name(role_name: str) -> str:
    normalized = role_name.strip().lower()
    if not normalized:
        raise ValueError("Role name must not be empty.")
    return normalized


def normalize_permission_parts(permission_type: str, name: str) -> tuple[str, str]:
    normalized_type = permission_type.strip().lower()
    normalized_name = name.strip().lower()
    if normalized_type not in ALLOWED_PERMISSION_TYPES:
        raise ValueError("permission_type must be one of: general, command, assistant.")
    if not normalized_name:
        raise ValueError("permission name must not be empty.")
    return normalized_type, normalized_name


def build_permission_report(
    override_rows: list[tuple[object, ...]],
    role_rows: list[tuple[object, ...]],
) -> dict[str, list[dict[str, object]]]:
    user_overrides: list[dict[str, object]] = [
        {
            "type": str(row[0]),
            "name": str(row[1]),
            "is_active": bool(row[2]),
        }
        for row in override_rows
    ]
    role_permissions: list[dict[str, object]] = [
        {
            "role": str(row[0]),
            "type": str(row[1]),
            "name": str(row[2]),
        }
        for row in role_rows
    ]

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
