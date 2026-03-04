from __future__ import annotations

import argparse
import asyncio
import platform
import sys

from ai_assistant.bootstrap_infra import build_media_controller, build_mpc_controller, build_output_controller
from ai_assistant.config.settings import Settings
from ai_assistant.logging_utils import configure_logging
from ai_assistant.providers.system.assistant_command_executor import SystemAssistantCommandExecutor
from ai_assistant.remote_client.agent import RemoteClientAgent
from ai_assistant.remote_client.state_store import FileClientStateStore


def run() -> None:
    parser = argparse.ArgumentParser(description="AI Assistant remote Windows client")
    parser.add_argument(
        "--unlink",
        action="store_true",
        help="Remove locally saved server link token and exit.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    configure_logging()

    if sys.platform != "win32":
        raise RuntimeError("Remote client currently supports Windows only.")

    state_store = FileClientStateStore(settings.remote_client_token_file)
    if args.unlink:
        state_store.clear()
        print("Local server link has been removed.")
        return

    if not settings.remote_client_server_url.strip():
        raise ValueError("AI_ASSISTANT_REMOTE_CLIENT_SERVER_URL is required for remote client.")

    media_controller = build_media_controller()
    mpc_controller = build_mpc_controller()
    output_controller = build_output_controller(settings)
    command_executor = SystemAssistantCommandExecutor(
        media_controller=media_controller,
        mpc_controller=mpc_controller,
        output_controller=output_controller,
        active_skill_ids=settings.remote_client_active_skills,
        skill_factories=settings.remote_client_skill_factories,
    )

    client_name = settings.remote_client_name.strip() or platform.node() or "Windows PC"
    agent = RemoteClientAgent(
        server_url=settings.remote_client_server_url,
        server_id=settings.remote_server_id,
        client_name=client_name,
        platform=settings.remote_client_platform,
        command_executor=command_executor,
        state_store=state_store,
        reconnect_min_seconds=settings.remote_client_reconnect_min_seconds,
        reconnect_max_seconds=settings.remote_client_reconnect_max_seconds,
        ping_interval_seconds=settings.remote_client_ping_interval_seconds,
        ping_timeout_seconds=settings.remote_client_ping_timeout_seconds,
    )
    asyncio.run(agent.run_forever())
