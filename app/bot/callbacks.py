from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot import keyboards
from app.bot.commands import accounts, help_command, menu, privacy, security, settings, terms
from app.bot.permissions import require_onboarded_user, require_unlocked_vault, runtime
from app.db import session_scope
from app.repositories.accounts import AccountRepository
from app.services.encryption import EncryptionError
from app.services.totp import current_code


async def account_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    account_id = update.callback_query.data.split(":", 1)[1]
    with session_scope(runtime(context).session_factory) as session:
        account = AccountRepository(session).get_for_user(user.id, account_id)
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
    user = await require_unlocked_vault(update, context)
    if user is None:
        return
    rt = runtime(context)
    vault_key = rt.auth.require_vault_key(user.id)
    account_id = update.callback_query.data.split(":", 1)[1]
    with session_scope(rt.session_factory) as session:
        repo = AccountRepository(session)
        account = repo.get_for_user(user.id, account_id)
        if account is None:
            await update.callback_query.answer("Account not found", show_alert=True)
            return
        try:
            secret = rt.encryption.decrypt_text(account.encrypted_secret, vault_key)
            generated = current_code(secret, algorithm=account.algorithm, digits=account.digits, period=account.period)
        except EncryptionError:
            await update.callback_query.answer("Unable to decrypt account", show_alert=True)
            return
        repo.mark_used_for_user(user.id, account_id)
        service_name = account.service_name
        account_label = account.account_label
    await update.callback_query.answer("Code generated")
    message = await update.callback_query.message.reply_text(
        f"Service: {service_name}\n"
        f"Account: {account_label}\n"
        f"Code: {generated.code}\n"
        f"Expires in: {generated.expires_in} seconds"
    )
    if context.job_queue is not None:
        context.job_queue.run_once(
            delete_message_job,
            rt.settings.code_message_ttl_seconds,
            data={"chat_id": message.chat_id, "message_id": message.message_id},
        )


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except Exception:
        pass


async def delete_requested(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    account_id = update.callback_query.data.split(":", 1)[1]
    with session_scope(runtime(context).session_factory) as session:
        account = AccountRepository(session).get_for_user(user.id, account_id)
        if account is None:
            await update.callback_query.answer("Account not found", show_alert=True)
            return
        text = f"Delete {account.service_name} - {account.account_label}? This cannot be undone."
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text, reply_markup=keyboards.delete_confirm(account_id))


async def delete_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    account_id = update.callback_query.data.split(":", 1)[1]
    with session_scope(runtime(context).session_factory) as session:
        deleted = AccountRepository(session).delete_for_user(user.id, account_id)
    await update.callback_query.answer("Deleted" if deleted else "Not found")
    await update.callback_query.edit_message_text(
        "✅ Account deleted." if deleted else "Account not found.", reply_markup=keyboards.main_menu()
    )


async def route_simple_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data
    if data == "menu":
        await menu(update, context)
    elif data == "accounts":
        await accounts(update, context)
    elif data == "settings":
        await settings(update, context)
    elif data == "privacy":
        await privacy(update, context)
    elif data == "terms":
        await terms(update, context)
    elif data == "security":
        await security(update, context)
    elif data == "help":
        await help_command(update, context)
