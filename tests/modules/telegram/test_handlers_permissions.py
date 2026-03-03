from tests.modules.telegram._shared import *

def test_handle_ping_requires_usage_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "command", "ping")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_ping(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: general/usage."]


def test_handle_ping_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_ping(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/ping."]


def test_handle_settings_raw_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(
        assistant_service=assistant,
        user_settings_store=settings_store,
        permission_checker=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_raw(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/settings_raw."]


def test_handle_settings_callback_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(
        assistant_service=assistant,
        user_settings_store=settings_store,
        permission_checker=permissions,
    )
    update = FakeUpdate(user_id=101)
    update.callback_query = FakeCallbackQuery(data="settings:home", message=update.effective_message)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    assert update.callback_query.answers == [("Недостаточно прав: command/settings.", True)]


def test_handle_cancel_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_cancel(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/cancel."]


def test_handle_id_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_id(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/id."]


def test_admin_telegram_id_bypasses_permissions_in_handlers() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed=set())
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        admin_telegram_id=101,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_ping(update, context))

    assert update.effective_message.replies == ["pong"]


def test_text_message_requires_assistant_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101, text="hello")
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_text_message(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: general/assistant."]
    assert assistant.process_calls == []


def test_handle_role_add_creates_role() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "role_add")}
    )
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["admin"])

    asyncio.run(handlers.handle_role_add(update, context))

    assert permissions.roles_created == ["admin"]
    assert update.effective_message.replies == ["Role created: admin"]


def test_handle_grant_user_sets_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "grant")}
    )
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["user", "200", "command", "ping"])

    asyncio.run(handlers.handle_grant(update, context))

    assert permissions.user_permission_updates == [(200, "command", "ping", True)]
    assert "Granted user permission" in update.effective_message.replies[0]


def test_handle_revoke_role_removes_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "revoke")}
    )
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["role", "admins", "assistant", "media.play_pause"])

    asyncio.run(handlers.handle_revoke(update, context))

    assert permissions.role_revokes == [("admins", "assistant", "media.play_pause")]
    assert "Revoked role permission" in update.effective_message.replies[0]


def test_handle_user_roles_returns_roles() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "user_roles")}
    )
    permissions.user_roles_response[200] = ["admin", "operator"]
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["200"])

    asyncio.run(handlers.handle_user_roles(update, context))

    text = update.effective_message.replies[0]
    assert "user=200 roles:" in text
    assert "- admin" in text
    assert "- operator" in text


def test_handle_user_permissions_returns_report() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "user_permissions")}
    )
    permissions.user_permissions_response[200] = {
        "user_overrides": [{"type": "command", "name": "ping", "is_active": False}],
        "role_permissions": [{"role": "admin", "type": "general", "name": "usage"}],
        "effective": [
            {
                "type": "general",
                "name": "usage",
                "is_active": True,
                "source": "role",
                "roles": ["admin"],
            },
            {
                "type": "command",
                "name": "ping",
                "is_active": False,
                "source": "user_override",
                "roles": [],
            },
        ],
    }
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["200"])

    asyncio.run(handlers.handle_user_permissions(update, context))

    text = update.effective_message.replies[0]
    assert "user=200 permissions:" in text
    assert "user_overrides:" in text
    assert "command/ping = False" in text
    assert "role_permissions:" in text
    assert "role=admin: general/usage" in text
    assert "effective:" in text
