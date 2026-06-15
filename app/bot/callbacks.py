from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot import keyboards
from app.bot.commands import accounts, help_command, menu, runtime, settings
from app.bot.messages import LOCKED
from app.bot.permissions import ensure_owner
from app.db import session_scope
from app.repositories.accounts import AccountRepository
from app.repositories.settings import SettingsRepository
from app.services.encryption import EncryptionError
from app.services.totp import current_code


async def account_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    account_id = int(update.callback_query.data.split(":", 1)[1])
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        account = AccountRepository(session).get(account_id)
        if account is None:
            await update.callback_query.answer("Account not found", show_alert=True)
            return
        text = (
            f"Service: {account.service_name}\n"
            f"Account: {account.account_label}\n"
            f"Issuer: {account.issuer or '-'}"
        )
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text, reply_markup=keyboards.account_actions(account_id))


async def show_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    rt = runtime(context)
    if not rt.auth.is_unlocked():
        await update.callback_query.answer("Vault locked", show_alert=True)
        await update.callback_query.message.reply_text(LOCKED, reply_markup=keyboards.main_menu())
        return

    account_id = int(update.callback_query.data.split(":", 1)[1])
    with session_scope(rt.session_factory) as session:
        repo = AccountRepository(session)
        account = repo.get(account_id)
        if account is None:
            await update.callback_query.answer("Account not found", show_alert=True)
            return
        try:
            secret = rt.encryption.decrypt_text(account.encrypted_secret)
            generated = current_code(
                secret,
                algorithm=account.algorithm,
                digits=account.digits,
                period=account.period,
            )
        except EncryptionError:
            await update.callback_query.answer("Unable to decrypt account", show_alert=True)
            return
        repo.mark_used(account)
        service_name = account.service_name
        account_label = account.account_label

        settings_repo = SettingsRepository(session)
        state = settings_repo.get_or_create(
            lock_timeout_seconds=rt.settings.vault_session_seconds,
            code_message_ttl_seconds=rt.settings.code_message_ttl_seconds,
        )
        ttl = state.code_message_ttl_seconds

    await update.callback_query.answer("Code generated")
    message = await update.callback_query.message.reply_text(
        f"Service: {service_name}\n"
        f"Account: {account_label}\n"
        f"Code: {generated.code}\n"
        f"Expires in: {generated.expires_in} seconds"
    )
    if context.job_queue is not None:
        context.job_queue.run_once(delete_message_job, ttl, data={"chat_id": message.chat_id, "message_id": message.message_id})


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except Exception:
        pass


async def delete_requested(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    account_id = int(update.callback_query.data.split(":", 1)[1])
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        account = AccountRepository(session).get(account_id)
        if account is None:
            await update.callback_query.answer("Account not found", show_alert=True)
            return
        text = f"Delete {account.service_name} - {account.account_label}? This cannot be undone."
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text, reply_markup=keyboards.delete_confirm(account_id))


async def delete_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    account_id = int(update.callback_query.data.split(":", 1)[1])
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        repo = AccountRepository(session)
        account = repo.get(account_id)
        if account is None:
            text = "Account not found."
        else:
            repo.delete(account)
            text = "✅ Account deleted."
    await update.callback_query.answer("Deleted")
    await update.callback_query.edit_message_text(text, reply_markup=keyboards.main_menu())


async def set_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    seconds = int(update.callback_query.data.split(":", 1)[1])
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        repo = SettingsRepository(session)
        state = repo.get_or_create(
            lock_timeout_seconds=rt.settings.vault_session_seconds,
            code_message_ttl_seconds=rt.settings.code_message_ttl_seconds,
        )
        repo.update_lock_timeout(state, seconds)
    await update.callback_query.answer("Timeout updated")
    await settings(update, context)


async def set_ttl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_owner(update, context):
        return
    seconds = int(update.callback_query.data.split(":", 1)[1])
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        repo = SettingsRepository(session)
        state = repo.get_or_create(
            lock_timeout_seconds=rt.settings.vault_session_seconds,
            code_message_ttl_seconds=rt.settings.code_message_ttl_seconds,
        )
        repo.update_code_ttl(state, seconds)
    await update.callback_query.answer("TTL updated")
    await settings(update, context)


async def route_simple_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data
    if data == "menu":
        await menu(update, context)
    elif data == "accounts":
        await accounts(update, context)
    elif data == "settings":
        await settings(update, context)
    elif data == "help":
        await help_command(update, context)

