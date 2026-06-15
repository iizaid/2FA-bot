from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import Application, ContextTypes

from app.bot import keyboards
from app.bot.messages import HELP, LOCKED, WELCOME
from app.bot.permissions import ensure_owner
from app.bot.runtime import BotRuntime
from app.db import session_scope
from app.repositories.accounts import AccountRepository
from app.repositories.settings import SettingsRepository

logger = logging.getLogger(__name__)


COMMANDS = [
    BotCommand("start", "Show welcome screen and main menu"),
    BotCommand("menu", "Show main menu"),
    BotCommand("unlock", "Unlock the vault"),
    BotCommand("lock", "Lock the vault"),
    BotCommand("add", "Add a new TOTP account"),
    BotCommand("accounts", "Show all saved accounts"),
    BotCommand("code", "Choose account and show current TOTP code"),
    BotCommand("search", "Search accounts"),
    BotCommand("rename", "Rename an account"),
    BotCommand("delete", "Delete an account"),
    BotCommand("export", "Export encrypted backup"),
    BotCommand("import", "Import encrypted backup"),
    BotCommand("settings", "Show settings"),
    BotCommand("status", "Show vault status"),
    BotCommand("help", "Show help"),
]


def runtime(context: ContextTypes.DEFAULT_TYPE) -> BotRuntime:
    return context.bot_data["runtime"]


async def set_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(COMMANDS)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    await update.effective_message.reply_text(WELCOME, reply_markup=keyboards.main_menu())


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Main menu", reply_markup=keyboards.main_menu())
        return
    await update.effective_message.reply_text("Main menu", reply_markup=keyboards.main_menu())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(HELP, reply_markup=keyboards.main_menu())
        return
    await update.effective_message.reply_text(HELP, reply_markup=keyboards.main_menu())


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    runtime(context).auth.lock()
    message = "🔒 Vault locked."
    if update.callback_query is not None:
        await update.callback_query.answer("Vault locked")
        await update.callback_query.edit_message_text(message, reply_markup=keyboards.main_menu())
        return
    await update.effective_message.reply_text(message, reply_markup=keyboards.main_menu())


async def accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        repo = AccountRepository(session)
        saved = list(repo.list_all())

    text = "No accounts saved yet. Use Add Account to store your first TOTP setup key."
    markup = keyboards.main_menu()
    if saved:
        text = "📋 Your saved accounts:"
        markup = keyboards.account_list(saved)

    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup)
        return
    await update.effective_message.reply_text(text, reply_markup=markup)


async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    if not runtime(context).auth.is_unlocked():
        await update.effective_message.reply_text(LOCKED, reply_markup=keyboards.main_menu())
        return
    await accounts(update, context)


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        saved = list(AccountRepository(session).list_all())
    if not saved:
        await update.effective_message.reply_text("No accounts saved yet.", reply_markup=keyboards.main_menu())
        return
    await update.effective_message.reply_text("Choose an account to rename:", reply_markup=keyboards.account_list(saved, prefix="rename"))


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        saved = list(AccountRepository(session).list_all())
    if not saved:
        await update.effective_message.reply_text("No accounts saved yet.", reply_markup=keyboards.main_menu())
        return
    await update.effective_message.reply_text("Choose an account to delete:", reply_markup=keyboards.account_list(saved, prefix="delete"))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        settings_repo = SettingsRepository(session)
        state = settings_repo.get_or_create(
            lock_timeout_seconds=rt.settings.vault_session_seconds,
            code_message_ttl_seconds=rt.settings.code_message_ttl_seconds,
        )
        count = AccountRepository(session).count()
        has_pin = state.pin_hash is not None
        lock_timeout = state.lock_timeout_seconds

    status_text = "unlocked" if rt.auth.is_unlocked() else "locked"
    remaining = rt.auth.seconds_remaining()
    text = (
        "🔐 Vault status\n\n"
        f"State: {status_text}\n"
        f"Session remaining: {remaining} seconds\n"
        f"PIN configured: {'yes' if has_pin else 'no'}\n"
        f"Accounts: {count}\n"
        f"Lock timeout: {lock_timeout} seconds"
    )
    await update.effective_message.reply_text(text, reply_markup=keyboards.main_menu())


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        settings_repo = SettingsRepository(session)
        state = settings_repo.get_or_create(
            lock_timeout_seconds=rt.settings.vault_session_seconds,
            code_message_ttl_seconds=rt.settings.code_message_ttl_seconds,
        )
        count = AccountRepository(session).count()

    db_path = rt.settings.database_url.replace("sqlite:///", "", 1)
    text = (
        "⚙️ Settings\n\n"
        "Owner-only mode: enabled\n"
        f"Vault lock timeout: {state.lock_timeout_seconds} seconds\n"
        f"Number of accounts: {count}\n"
        f"Database path: {db_path}\n"
        "Auto-delete code messages: enabled\n"
        f"Code message TTL: {state.code_message_ttl_seconds} seconds\n"
        "Backup/export: encrypted"
    )
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboards.settings_keyboard())
        return
    await update.effective_message.reply_text(text, reply_markup=keyboards.settings_keyboard())


async def random_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    await update.effective_message.reply_text(
        "I did not understand that action. Use the menu buttons below.",
        reply_markup=keyboards.main_menu(),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_type = type(context.error).__name__ if context.error else "UnknownError"
    logger.error("Unhandled bot error type=%s", error_type)
    if isinstance(update, Update) and update.effective_message is not None:
        try:
            await update.effective_message.reply_text(
                "Something went wrong while handling that request. Please try again from the main menu.",
                reply_markup=keyboards.main_menu(),
            )
        except Exception:
            logger.error("Failed to send safe error response")
