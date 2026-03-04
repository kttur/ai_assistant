import asyncio

import pytest

from ai_assistant.providers.remote.in_memory_remote_device_store import InMemoryRemoteDeviceStore
from ai_assistant.providers.remote.remote_device_service import (
    AccessDeniedError,
    LinkCodeNotFoundError,
    OwnershipError,
    RemoteDeviceService,
)


def test_issue_link_code_and_link_device_assigns_default() -> None:
    store = InMemoryRemoteDeviceStore()
    service = RemoteDeviceService(store=store, link_code_ttl_seconds=300)

    link = asyncio.run(
        service.issue_link_code(
            session_id="s1",
            client_id="client-1",
            display_name="Home PC",
            platform="windows",
            server_id="default",
        )
    )
    result = asyncio.run(service.link_device(user_id=10, code=link.code))

    assert result.client.client_id == "client-1"
    assert result.client.owner_user_id == 10
    assert result.default_assigned is True
    assert result.auth_token

    clients = asyncio.run(service.list_user_clients(user_id=10))
    assert len(clients) == 1
    assert clients[0].is_default is True


def test_link_device_rejects_other_owner() -> None:
    store = InMemoryRemoteDeviceStore()
    service = RemoteDeviceService(store=store, link_code_ttl_seconds=300)

    first = asyncio.run(
        service.issue_link_code(
            session_id="s1",
            client_id="client-1",
            display_name="Home PC",
            platform="windows",
            server_id="default",
        )
    )
    asyncio.run(service.link_device(user_id=10, code=first.code))

    second = asyncio.run(
        service.issue_link_code(
            session_id="s2",
            client_id="client-1",
            display_name="Home PC",
            platform="windows",
            server_id="default",
        )
    )

    with pytest.raises(OwnershipError):
        asyncio.run(service.link_device(user_id=11, code=second.code))


def test_share_and_revoke_access() -> None:
    store = InMemoryRemoteDeviceStore()
    service = RemoteDeviceService(store=store, link_code_ttl_seconds=300)

    link = asyncio.run(
        service.issue_link_code(
            session_id="s1",
            client_id="client-1",
            display_name="Home PC",
            platform="windows",
            server_id="default",
        )
    )
    asyncio.run(service.link_device(user_id=10, code=link.code))

    asyncio.run(service.share_client(owner_user_id=10, client_id="client-1", target_user_id=20))
    shared_clients = asyncio.run(service.list_user_clients(user_id=20))
    assert len(shared_clients) == 1
    assert shared_clients[0].is_owner is False

    asyncio.run(
        service.revoke_client_access(owner_user_id=10, client_id="client-1", target_user_id=20)
    )
    shared_clients_after_revoke = asyncio.run(service.list_user_clients(user_id=20))
    assert shared_clients_after_revoke == []


def test_set_default_requires_access() -> None:
    store = InMemoryRemoteDeviceStore()
    service = RemoteDeviceService(store=store, link_code_ttl_seconds=300)

    link = asyncio.run(
        service.issue_link_code(
            session_id="s1",
            client_id="client-1",
            display_name="Home PC",
            platform="windows",
            server_id="default",
        )
    )
    asyncio.run(service.link_device(user_id=10, code=link.code))

    with pytest.raises(AccessDeniedError):
        asyncio.run(service.set_default_client(user_id=11, client_id="client-1"))


def test_unlink_by_token_removes_client() -> None:
    store = InMemoryRemoteDeviceStore()
    service = RemoteDeviceService(store=store, link_code_ttl_seconds=300)

    link = asyncio.run(
        service.issue_link_code(
            session_id="s1",
            client_id="client-1",
            display_name="Home PC",
            platform="windows",
            server_id="default",
        )
    )
    result = asyncio.run(service.link_device(user_id=10, code=link.code))

    asyncio.run(
        service.unlink_client_by_token(
            client_id="client-1",
            server_id="default",
            auth_token=result.auth_token,
        )
    )

    with pytest.raises(LinkCodeNotFoundError):
        asyncio.run(service.unlink_client(owner_user_id=10, client_id="client-1"))
