from __future__ import annotations

import io
from dataclasses import asdict

from telegram import InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

from app.bot import keyboards
from app.bot.commands import runtime
from app.bot.messages import CANCELLED
from app.bot.permissions import ensure_owner
from app.db import session_scope
from app.repositories.accounts import AccountRepository
from app.repositories.settings import SettingsRepository
from app.services.backup import BackupError
from app.services.totp import TotpSecret, TotpValidationError, parse_setup_value, verify_setup_code
from app.utils.validators import clean_name, clean_pin

(
    UNLOCK_PIN,
    ADD_SERVICE,
    ADD_LABEL,
    ADD_SECRET,
    ADD_VERIFY,
    SEARCH_QUERY,
    RENAME_SERVICE,
    RENAME_LABEL,
    RENAME_CONFIRM,
    EXPORT_PASSWORD,
    IMPORT_FILE,
    IMPORT_PASSWORD,
) = range(12)


async def safe_delete_current_message(update: Update) -> None:
    message = update.effective_message
    if message is not None:
        try:
            await message.delete()
        except Exception:
            pass


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(CANCELLED, reply_markup=keyboards.main_menu())
    else:
        await update.effective_message.reply_text(CANCELLED, reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    rt = runtime(context)
    if rt.rate_limiter.is_locked():
        text = f"Too many failed attempts. Try again in {rt.rate_limiter.seconds_remaining()} seconds."
        await _reply_or_edit(update, text, reply_markup=keyboards.main_menu())
        return ConversationHandler.END

    with session_scope(rt.session_factory) as session:
        state = SettingsRepository(session).get_or_create(
            lock_timeout_seconds=rt.settings.vault_session_seconds,
            code_message_ttl_seconds=rt.settings.code_message_ttl_seconds,
        )
        pin_configured = state.pin_hash is not None

    text = (
        "Create a local vault PIN/passphrase. Use at least 6 characters."
        if not pin_configured
        else "Enter your vault PIN/passphrase to unlock."
    )
    context.user_data["pin_setup"] = not pin_configured
    await _reply_or_edit(update, text, reply_markup=keyboards.cancel_keyboard())
    return UNLOCK_PIN


async def receive_unlock_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    rt = runtime(context)
    try:
        pin = clean_pin(update.effective_message.text or "")
    except ValueError as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(str(exc), reply_markup=keyboards.cancel_keyboard())
        return UNLOCK_PIN

    with session_scope(rt.session_factory) as session:
        settings_repo = SettingsRepository(session)
        state = settings_repo.get_or_create(
            lock_timeout_seconds=rt.settings.vault_session_seconds,
            code_message_ttl_seconds=rt.settings.code_message_ttl_seconds,
        )
        if context.user_data.get("pin_setup"):
            settings_repo.set_pin_hash(state, rt.auth.hash_pin(pin))
            rt.auth.unlock(state.lock_timeout_seconds)
            rt.rate_limiter.register_success()
            text = "✅ Vault PIN configured and vault unlocked."
        elif state.pin_hash and rt.auth.verify_pin(state.pin_hash, pin):
            rt.auth.unlock(state.lock_timeout_seconds)
            rt.rate_limiter.register_success()
            text = "✅ Vault unlocked."
        else:
            rt.rate_limiter.register_failure()
            await safe_delete_current_message(update)
            await update.effective_chat.send_message(
                "Invalid PIN/passphrase. Please try again.", reply_markup=keyboards.cancel_keyboard()
            )
            return UNLOCK_PIN

    await safe_delete_current_message(update)
    context.user_data.clear()
    await update.effective_chat.send_message(text, reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    await _reply_or_edit(
        update,
        "➕ Add Account\n\nEnter the service name, for example Gmail, GitHub, or Facebook.",
        reply_markup=keyboards.cancel_keyboard(),
    )
    return ADD_SERVICE


async def receive_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    try:
        context.user_data["service_name"] = clean_name(update.effective_message.text or "")
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return ADD_SERVICE
    await update.effective_message.reply_text(
        "Enter an account label, for example Personal Gmail or Work GitHub. Do not send a password.",
        reply_markup=keyboards.cancel_keyboard(),
    )
    return ADD_LABEL


async def receive_add_label(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    try:
        context.user_data["account_label"] = clean_name(update.effective_message.text or "", max_length=160)
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return ADD_LABEL
    await update.effective_message.reply_text(
        "⚠️ Send only the TOTP setup key or otpauth:// URI. Never send account passwords.",
        reply_markup=keyboards.cancel_keyboard(),
    )
    return ADD_SECRET


async def receive_add_secret(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    try:
        parsed = parse_setup_value(update.effective_message.text or "")
    except TotpValidationError as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(
            f"That setup key could not be validated: {exc}. Please try again or cancel.",
            reply_markup=keyboards.cancel_keyboard(),
        )
        return ADD_SECRET

    context.user_data["parsed_secret"] = asdict(parsed)
    await safe_delete_current_message(update)
    await update.effective_chat.send_message(
        "Enter the current 6-digit code shown by the service setup page to verify the setup key.",
        reply_markup=keyboards.cancel_keyboard(),
    )
    return ADD_VERIFY


async def receive_add_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    rt = runtime(context)
    parsed = TotpSecret(**context.user_data["parsed_secret"])
    setup_code = update.effective_message.text or ""
    if not verify_setup_code(parsed, setup_code):
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(
            "The verification code did not match. Please check the service setup page and try again.",
            reply_markup=keyboards.cancel_keyboard(),
        )
        return ADD_VERIFY

    service_name = context.user_data["service_name"]
    account_label = context.user_data["account_label"]
    issuer = parsed.issuer
    with session_scope(rt.session_factory) as session:
        repo = AccountRepository(session)
        if repo.find_duplicate(service_name, account_label, issuer):
            text = "An account with the same service, label, and issuer already exists."
        else:
            repo.create(
                service_name=service_name,
                account_label=account_label,
                issuer=issuer,
                encrypted_secret=rt.encryption.encrypt_text(parsed.secret),
                algorithm=parsed.algorithm,
                digits=parsed.digits,
                period=parsed.period,
            )
            text = "✅ Account added successfully."

    await safe_delete_current_message(update)
    context.user_data.clear()
    await update.effective_chat.send_message(text, reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    await _reply_or_edit(update, "Enter a service name or account label to search.", reply_markup=keyboards.cancel_keyboard())
    return SEARCH_QUERY


async def receive_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    query = (update.effective_message.text or "").strip()
    if not query:
        await update.effective_message.reply_text("Search cannot be empty.", reply_markup=keyboards.cancel_keyboard())
        return SEARCH_QUERY
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        results = list(AccountRepository(session).search(query))
    if results:
        await update.effective_message.reply_text("Search results:", reply_markup=keyboards.account_list(results))
    else:
        await update.effective_message.reply_text("No matching accounts found.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    account_id = _callback_account_id(update)
    if account_id is None:
        await _reply_or_edit(update, "Choose an account to rename.", reply_markup=keyboards.main_menu())
        return ConversationHandler.END
    context.user_data["rename_account_id"] = account_id
    await _reply_or_edit(update, "Enter the new service name.", reply_markup=keyboards.cancel_keyboard())
    return RENAME_SERVICE


async def receive_rename_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    try:
        context.user_data["rename_service_name"] = clean_name(update.effective_message.text or "")
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return RENAME_SERVICE
    await update.effective_message.reply_text("Enter the new account label.", reply_markup=keyboards.cancel_keyboard())
    return RENAME_LABEL


async def receive_rename_label(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    try:
        label = clean_name(update.effective_message.text or "", max_length=160)
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return RENAME_LABEL
    context.user_data["rename_account_label"] = label
    service_name = context.user_data["rename_service_name"]
    await update.effective_message.reply_text(
        f"Confirm rename to:\nService: {service_name}\nAccount: {label}",
        reply_markup=keyboards.rename_confirm(),
    )
    return RENAME_CONFIRM


async def confirm_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    rt = runtime(context)
    account_id = int(context.user_data["rename_account_id"])
    service_name = context.user_data["rename_service_name"]
    label = context.user_data["rename_account_label"]
    with session_scope(rt.session_factory) as session:
        repo = AccountRepository(session)
        account = repo.get(account_id)
        if account is None:
            text = "Account not found."
        else:
            repo.rename(account, service_name, label)
            text = "✅ Account renamed."
    context.user_data.clear()
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text, reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    await _reply_or_edit(
        update,
        "Enter an export password. The backup file will be encrypted with this password.",
        reply_markup=keyboards.cancel_keyboard(),
    )
    return EXPORT_PASSWORD


async def receive_export_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    rt = runtime(context)
    try:
        password = clean_pin(update.effective_message.text or "")
    except ValueError as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(str(exc), reply_markup=keyboards.cancel_keyboard())
        return EXPORT_PASSWORD
    with session_scope(rt.session_factory) as session:
        accounts = list(AccountRepository(session).list_all())
        backup_bytes = rt.backup.export_accounts(accounts, password)
    await safe_delete_current_message(update)
    await update.effective_chat.send_document(
        document=InputFile(io.BytesIO(backup_bytes), filename="totp-vault-backup.json.enc"),
        caption="Encrypted backup created. Store it safely; it cannot be restored without the export password.",
    )
    await update.effective_chat.send_message("✅ Export complete.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    await _reply_or_edit(update, "Upload the encrypted backup file.", reply_markup=keyboards.cancel_keyboard())
    return IMPORT_FILE


async def receive_import_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    document = update.effective_message.document
    if document is None:
        await update.effective_message.reply_text("Please upload the encrypted backup file.", reply_markup=keyboards.cancel_keyboard())
        return IMPORT_FILE
    file = await document.get_file()
    data = await file.download_as_bytearray()
    context.user_data["backup_bytes"] = bytes(data)
    await update.effective_message.reply_text("Enter the backup password.", reply_markup=keyboards.cancel_keyboard())
    return IMPORT_PASSWORD


async def receive_import_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_owner(update, context):
        return ConversationHandler.END
    rt = runtime(context)
    try:
        password = clean_pin(update.effective_message.text or "")
        payload = rt.backup.decrypt_backup(context.user_data["backup_bytes"], password)
    except (ValueError, BackupError) as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(f"Import failed: {exc}", reply_markup=keyboards.main_menu())
        context.user_data.clear()
        return ConversationHandler.END

    imported = 0
    skipped = 0
    with session_scope(rt.session_factory) as session:
        repo = AccountRepository(session)
        for record in payload["accounts"]:
            if repo.find_duplicate(record["service_name"], record["account_label"], record.get("issuer")):
                skipped += 1
                continue
            repo.create(
                service_name=record["service_name"],
                account_label=record["account_label"],
                issuer=record.get("issuer"),
                encrypted_secret=record["encrypted_secret"],
                algorithm=record.get("algorithm", "SHA1"),
                digits=int(record.get("digits", 6)),
                period=int(record.get("period", 30)),
            )
            imported += 1

    await safe_delete_current_message(update)
    context.user_data.clear()
    await update.effective_chat.send_message(
        f"✅ Import complete. Imported: {imported}. Skipped duplicates: {skipped}.",
        reply_markup=keyboards.main_menu(),
    )
    return ConversationHandler.END


async def _reply_or_edit(update: Update, text: str, reply_markup=None) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=reply_markup)


def _callback_account_id(update: Update) -> int | None:
    if update.callback_query is None or not update.callback_query.data:
        return None
    try:
        return int(update.callback_query.data.split(":", 1)[1])
    except (IndexError, ValueError):
        return None
