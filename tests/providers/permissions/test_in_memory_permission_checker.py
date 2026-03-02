import asyncio

from ai_assistant.providers.permissions.in_memory_permission_checker import InMemoryPermissionChecker


def test_in_memory_checker_defaults_to_deny_when_not_allow_all() -> None:
    checker = InMemoryPermissionChecker(allow_all=False)

    allowed = asyncio.run(checker.has_permission(100, "general", "usage"))

    assert allowed is False


def test_in_memory_checker_uses_user_override_before_roles() -> None:
    checker = InMemoryPermissionChecker(allow_all=False)
    asyncio.run(checker.grant_role_permission("admin", "general", "usage"))
    asyncio.run(checker.assign_role(100, "admin"))
    asyncio.run(checker.set_user_permission(100, "general", "usage", is_active=False))

    allowed = asyncio.run(checker.has_permission(100, "general", "usage"))

    assert allowed is False


def test_in_memory_checker_falls_back_to_role_permissions() -> None:
    checker = InMemoryPermissionChecker(allow_all=False)
    asyncio.run(checker.grant_role_permission("operator", "command", "ping"))
    asyncio.run(checker.assign_role(100, "operator"))

    allowed = asyncio.run(checker.has_permission(100, "command", "ping"))

    assert allowed is True


def test_in_memory_checker_returns_roles_and_permission_report() -> None:
    checker = InMemoryPermissionChecker(allow_all=False)
    asyncio.run(checker.grant_role_permission("admin", "general", "usage"))
    asyncio.run(checker.assign_role(100, "admin"))
    asyncio.run(checker.set_user_permission(100, "command", "ping", is_active=False))

    roles = asyncio.run(checker.get_user_roles(100))
    report = asyncio.run(checker.get_user_permission_report(100))

    assert roles == ["admin"]
    assert report["user_overrides"] == [
        {"type": "command", "name": "ping", "is_active": False}
    ]
    assert report["role_permissions"] == [
        {"role": "admin", "type": "general", "name": "usage"}
    ]
    assert {
        (item["type"], item["name"]): item["is_active"]
        for item in report["effective"]
    } == {
        ("command", "ping"): False,
        ("general", "usage"): True,
    }
