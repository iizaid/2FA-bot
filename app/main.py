from __future__ import annotations

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot import callbacks, commands, conversations
from app.bot.runtime import BotRuntime
from app.config import Settings, get_settings
from app.db import build_session_factory, init_db, session_scope
from app.logging_config import configure_logging
from app.repositories.settings import SettingsRepository
from app.services.auth import VaultAuthService
from app.services.backup import BackupService
from app.services.encryption import EncryptionService
from app.services.rate_limit import UnlockRateLimiter


def build_runtime(settings: Settings) -> BotRuntime:
    session_factory = build_session_factory(settings)
    return BotRuntime(
        settings=settings,
        session_factory=session_factory,
        encryption=EncryptionService(settings.vault_master_key),
        auth=VaultAuthService(settings.vault_session_seconds),
        rate_limiter=UnlockRateLimiter(),
        backup=BackupService(),
    )


async def post_init(application: Application) -> None:
    await commands.set_bot_commands(application)


def build_application(settings: Settings | None = None) -> Application:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    init_db(settings)
    rt = build_runtime(settings)
    with session_scope(rt.session_factory) as session:
        SettingsRepository(session).get_or_create(
            lock_timeout_seconds=settings.vault_session_seconds,
            code_message_ttl_seconds=settings.code_message_ttl_seconds,
        )

    application = ApplicationBuilder().token(settings.bot_token).post_init(post_init).build()
    application.bot_data["runtime"] = rt
    application.bot_data["settings"] = settings

    application.add_handler(_unlock_conversation())
    application.add_handler(_add_conversation())
    application.add_handler(_search_conversation())
    application.add_handler(_rename_conversation())
    application.add_handler(_export_conversation())
    application.add_handler(_import_conversation())

    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("menu", commands.menu))
    application.add_handler(CommandHandler("lock", commands.lock))
    application.add_handler(CommandHandler("accounts", commands.accounts))
    application.add_handler(CommandHandler("code", commands.code_command))
    application.add_handler(CommandHandler("rename", commands.rename_command))
    application.add_handler(CommandHandler("delete", commands.delete_command))
    application.add_handler(CommandHandler("settings", commands.settings))
    application.add_handler(CommandHandler("status", commands.status))
    application.add_handler(CommandHandler("help", commands.help_command))

    application.add_handler(CallbackQueryHandler(commands.lock, pattern=r"^lock$"))
    application.add_handler(CallbackQueryHandler(callbacks.account_selected, pattern=r"^account:\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.show_code, pattern=r"^show_code:\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.delete_requested, pattern=r"^delete:\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.delete_confirmed, pattern=r"^delete_yes:\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.set_timeout, pattern=r"^set_timeout:\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.set_ttl, pattern=r"^set_ttl:\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.route_simple_callback, pattern=r"^(menu|accounts|settings|help)$"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, commands.random_text))
    application.add_error_handler(commands.error_handler)
    return application


def _unlock_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("unlock", conversations.begin_unlock),
            CallbackQueryHandler(conversations.begin_unlock, pattern=r"^unlock$"),
        ],
        states={
            conversations.UNLOCK_PIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_unlock_pin),
                CallbackQueryHandler(conversations.cancel, pattern=r"^cancel$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(conversations.cancel, pattern=r"^cancel$")],
    )


def _add_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", conversations.begin_add),
            CallbackQueryHandler(conversations.begin_add, pattern=r"^add$"),
        ],
        states={
            conversations.ADD_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_add_service)],
            conversations.ADD_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_add_label)],
            conversations.ADD_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_add_secret)],
            conversations.ADD_VERIFY: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_add_verify)],
        },
        fallbacks=[CallbackQueryHandler(conversations.cancel, pattern=r"^cancel$")],
    )


def _search_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("search", conversations.begin_search),
            CallbackQueryHandler(conversations.begin_search, pattern=r"^search$"),
        ],
        states={
            conversations.SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_search_query)],
        },
        fallbacks=[CallbackQueryHandler(conversations.cancel, pattern=r"^cancel$")],
    )


def _rename_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(conversations.begin_rename, pattern=r"^rename:\d+$")],
        states={
            conversations.RENAME_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_rename_service)],
            conversations.RENAME_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_rename_label)],
            conversations.RENAME_CONFIRM: [CallbackQueryHandler(conversations.confirm_rename, pattern=r"^rename_confirm$")],
        },
        fallbacks=[CallbackQueryHandler(conversations.cancel, pattern=r"^cancel$")],
    )


def _export_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("export", conversations.begin_export), CallbackQueryHandler(conversations.begin_export, pattern=r"^export$")],
        states={
            conversations.EXPORT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_export_password)],
        },
        fallbacks=[CallbackQueryHandler(conversations.cancel, pattern=r"^cancel$")],
    )


def _import_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("import", conversations.begin_import), CallbackQueryHandler(conversations.begin_import, pattern=r"^import$")],
        states={
            conversations.IMPORT_FILE: [MessageHandler(filters.Document.ALL, conversations.receive_import_file)],
            conversations.IMPORT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, conversations.receive_import_password)],
        },
        fallbacks=[CallbackQueryHandler(conversations.cancel, pattern=r"^cancel$")],
    )


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
