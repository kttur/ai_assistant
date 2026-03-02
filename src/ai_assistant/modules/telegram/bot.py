from __future__ import annotations

import asyncio

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from ai_assistant.modules.telegram.handlers import TelegramHandlers


class TelegramBotModule:
    def __init__(self, token: str, handlers: TelegramHandlers) -> None:
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required for telegram channel.")
        self._token = token
        self._handlers = handlers

    def _build_application(self) -> Application:
        application = ApplicationBuilder().token(self._token).build()
        application.add_handler(CommandHandler("start", self._handlers.handle_start))
        application.add_handler(CommandHandler("id", self._handlers.handle_id))
        application.add_handler(CommandHandler("ping", self._handlers.handle_ping))
        application.add_handler(CommandHandler("echo", self._handlers.handle_echo))
        application.add_handler(CommandHandler("ask", self._handlers.handle_ask))
        application.add_handler(CommandHandler("clear", self._handlers.handle_clear))
        application.add_handler(CommandHandler("set", self._handlers.handle_set_setting))
        application.add_handler(CommandHandler("settings", self._handlers.handle_settings))
        application.add_handler(CommandHandler("settings_raw", self._handlers.handle_settings_raw))
        application.add_handler(CommandHandler("grant", self._handlers.handle_grant))
        application.add_handler(CommandHandler("revoke", self._handlers.handle_revoke))
        application.add_handler(CommandHandler("role_add", self._handlers.handle_role_add))
        application.add_handler(CommandHandler("role_assign", self._handlers.handle_role_assign))
        application.add_handler(CommandHandler("user_roles", self._handlers.handle_user_roles))
        application.add_handler(
            CommandHandler("user_permissions", self._handlers.handle_user_permissions)
        )
        application.add_handler(CommandHandler("terminal", self._handlers.handle_terminal_mode))
        application.add_handler(CommandHandler("exit", self._handlers.handle_exit_terminal_mode))
        application.add_handler(CommandHandler("cancel", self._handlers.handle_cancel))
        application.add_handler(CommandHandler("player", self._handlers.handle_player))
        application.add_handler(CommandHandler("mpc", self._handlers.handle_mpc))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handlers.handle_text_message)
        )
        application.add_handler(
            CallbackQueryHandler(self._handlers.handle_player_button, pattern=r"^player:")
        )
        application.add_handler(
            CallbackQueryHandler(self._handlers.handle_mpc_button, pattern=r"^mpc:")
        )
        application.add_handler(
            CallbackQueryHandler(self._handlers.handle_settings_callback, pattern=r"^settings:")
        )
        return application

    def run(self) -> None:
        # Python 3.14 no longer creates an implicit current loop in main thread.
        # `python-telegram-bot` still expects one in `run_polling`.
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        application = self._build_application()
        application.run_polling(drop_pending_updates=True)
