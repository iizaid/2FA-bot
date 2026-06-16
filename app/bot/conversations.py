from __future__ import annotations

import base64
import io

from telegram import InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

from app.bot import keyboards
from app.bot.messages import CANCELLED
from app.bot.permissions import require_active_user, require_onboarded_user, require_unlocked_vault, runtime
from app.db import session_scope
from app.repositories.accounts import AccountRepository
from app.repositories.exports import ExportRepository
from app.repositories.security_events import SecurityEventRepository
from app.repositories.sessions import VaultSessionRepository
from app.repositories.users import UserRepository
from app.repositories.vaults import VaultRepository
from app.services.backup import BackupError
from app.services.totp import TotpSecret, TotpValidationError, parse_setup_value, verify_setup_code
from app.utils.validators import clean_name, clean_pin

(
    ONBOARD_PASSPHRASE,
    ONBOARD_CONFIRM,
    UNLOCK_PASSPHRASE,
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
) = range(14)


async def safe_delete_current_message(update: Update) -> None:
    message = update.effective_message
    if message is not None:
        try:
            await message.delete()
        except Exception:
            pass


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(CANCELLED, reply_markup=keyboards.main_menu())
    else:
        await update.effective_message.reply_text(CANCELLED, reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def accept_terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_active_user(update, context)
    if user is None:
        return ConversationHandler.END
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Create your vault passphrase. If you lose it, your encrypted TOTP secrets cannot be recovered.",
        reply_markup=keyboards.cancel_keyboard(),
    )
    return ONBOARD_PASSPHRASE


async def receive_onboard_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_active_user(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    try:
        passphrase = clean_pin(update.effective_message.text or "")
    except ValueError as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(str(exc), reply_markup=keyboards.cancel_keyboard())
        return ONBOARD_PASSPHRASE
    context.user_data["onboard_passphrase_hash"] = rt.encryption.hash_passphrase(passphrase)
    await safe_delete_current_message(update)
    await update.effective_chat.send_message("Confirm your vault passphrase.", reply_markup=keyboards.cancel_keyboard())
    return ONBOARD_CONFIRM


async def receive_onboard_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_active_user(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    passphrase = update.effective_message.text or ""
    passphrase_hash = context.user_data.get("onboard_passphrase_hash")
    if not passphrase_hash or not rt.encryption.verify_passphrase(passphrase_hash, passphrase):
        await safe_delete_current_message(update)
        await update.effective_chat.send_message("Passphrases did not match. Start again with /start.")
        context.user_data.clear()
        return ConversationHandler.END
    salt, vault_hash, vault_key = rt.auth.create_vault_material(passphrase)
    with session_scope(rt.session_factory) as session:
        UserRepository(session).accept_terms(session.merge(user))
        vault = VaultRepository(session).create_for_user(
            user_id=user.id,
            kdf_salt=salt,
            passphrase_hash=vault_hash,
            encryption_scheme=rt.encryption.scheme,
        )
        expires_at = rt.auth.store_session_key(user_id=user.id, vault_key=vault_key)
        VaultSessionRepository(session).replace_for_user(user.id, expires_at)
        VaultRepository(session).mark_unlocked(vault)
        SecurityEventRepository(session).record(event_type="onboarded", user_id=user.id, telegram_id=user.telegram_id)
    await safe_delete_current_message(update)
    context.user_data.clear()
    await update.effective_chat.send_message("✅ Vault created and unlocked.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_onboarded_user(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    if rt.rate_limiter.unlock_is_locked(user.id):
        await _reply_or_edit(
            update,
            f"Too many failed attempts. Try again in {rt.rate_limiter.unlock_seconds_remaining(user.id)} seconds.",
            reply_markup=keyboards.main_menu(),
        )
        return ConversationHandler.END
    await _reply_or_edit(update, "Enter your vault passphrase.", reply_markup=keyboards.cancel_keyboard())
    return UNLOCK_PASSPHRASE


async def receive_unlock_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_onboarded_user(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    passphrase = update.effective_message.text or ""
    with session_scope(rt.session_factory) as session:
        vault = VaultRepository(session).get_for_user(user.id)
        if vault is None or not rt.auth.unlock(user=user, vault=vault, passphrase=passphrase):
            rt.rate_limiter.register_unlock_failure(user.id)
            SecurityEventRepository(session).record(
                event_type="unlock_failed", severity="warning", user_id=user.id, telegram_id=user.telegram_id
            )
            await safe_delete_current_message(update)
            await update.effective_chat.send_message("Invalid passphrase.", reply_markup=keyboards.cancel_keyboard())
            return UNLOCK_PASSPHRASE
        rt.rate_limiter.register_unlock_success(user.id)
        VaultSessionRepository(session).replace_for_user(user.id, rt.auth._sessions[user.id].expires_at)
        VaultRepository(session).mark_unlocked(vault)
        SecurityEventRepository(session).record(event_type="vault_unlocked", user_id=user.id, telegram_id=user.telegram_id)
    await safe_delete_current_message(update)
    await update.effective_chat.send_message("✅ Vault unlocked.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_unlocked_vault(update, context)
    if user is None:
        return ConversationHandler.END
    if not runtime(context).rate_limiter.allow_add_attempt(user.id):
        await _reply_or_edit(update, "Too many add attempts. Please wait a moment.", reply_markup=keyboards.main_menu())
        return ConversationHandler.END
    await _reply_or_edit(update, "Enter the service name.", reply_markup=keyboards.cancel_keyboard())
    return ADD_SERVICE


async def receive_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await require_unlocked_vault(update, context) is None:
        return ConversationHandler.END
    try:
        context.user_data["service_name"] = clean_name(update.effective_message.text or "")
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return ADD_SERVICE
    await update.effective_message.reply_text("Enter an account label. Do not send a password.", reply_markup=keyboards.cancel_keyboard())
    return ADD_LABEL


async def receive_add_label(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await require_unlocked_vault(update, context) is None:
        return ConversationHandler.END
    try:
        context.user_data["account_label"] = clean_name(update.effective_message.text or "", max_length=160)
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return ADD_LABEL
    await update.effective_message.reply_text(
        "Send only the TOTP setup key or otpauth:// URI. Never send account passwords.",
        reply_markup=keyboards.cancel_keyboard(),
    )
    return ADD_SECRET


async def receive_add_secret(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_unlocked_vault(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    vault_key = rt.auth.require_vault_key(user.id)
    try:
        parsed = parse_setup_value(update.effective_message.text or "")
    except TotpValidationError as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(f"Setup key could not be validated: {exc}", reply_markup=keyboards.cancel_keyboard())
        return ADD_SECRET
    context.user_data["pending_secret"] = base64.b64encode(rt.encryption.encrypt_text(parsed.secret, vault_key)).decode("ascii")
    context.user_data["pending_totp"] = {
        "issuer": parsed.issuer,
        "account_name": parsed.account_name,
        "algorithm": parsed.algorithm,
        "digits": parsed.digits,
        "period": parsed.period,
    }
    await safe_delete_current_message(update)
    await update.effective_chat.send_message("Enter the current setup code to verify.", reply_markup=keyboards.cancel_keyboard())
    return ADD_VERIFY


async def receive_add_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_unlocked_vault(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    vault_key = rt.auth.require_vault_key(user.id)
    pending = context.user_data["pending_totp"]
    encrypted_secret = base64.b64decode(context.user_data["pending_secret"])
    secret = rt.encryption.decrypt_text(encrypted_secret, vault_key)
    parsed = TotpSecret(secret=secret, **pending)
    if not verify_setup_code(parsed, update.effective_message.text or ""):
        await safe_delete_current_message(update)
        await update.effective_chat.send_message("Verification code did not match.", reply_markup=keyboards.cancel_keyboard())
        return ADD_VERIFY
    with session_scope(rt.session_factory) as session:
        vault = VaultRepository(session).get_for_user(user.id)
        repo = AccountRepository(session)
        if vault is None:
            text = "Vault not found."
        elif repo.find_duplicate_for_user(user.id, context.user_data["service_name"], context.user_data["account_label"], parsed.issuer):
            text = "That account already exists."
        else:
            repo.create_for_user(
                user_id=user.id,
                vault_id=vault.id,
                service_name=context.user_data["service_name"],
                account_label=context.user_data["account_label"],
                issuer=parsed.issuer,
                encrypted_secret=encrypted_secret,
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
    if await require_onboarded_user(update, context) is None:
        return ConversationHandler.END
    await _reply_or_edit(update, "Enter search text.", reply_markup=keyboards.cancel_keyboard())
    return SEARCH_QUERY


async def receive_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_onboarded_user(update, context)
    if user is None:
        return ConversationHandler.END
    with session_scope(runtime(context).session_factory) as session:
        results = list(AccountRepository(session).search_for_user(user.id, update.effective_message.text or ""))
    await update.effective_message.reply_text(
        "Search results:" if results else "No matching accounts found.",
        reply_markup=keyboards.account_list(results) if results else keyboards.main_menu(),
    )
    return ConversationHandler.END


async def begin_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await require_onboarded_user(update, context) is None:
        return ConversationHandler.END
    context.user_data["rename_account_id"] = update.callback_query.data.split(":", 1)[1]
    await _reply_or_edit(update, "Enter the new service name.", reply_markup=keyboards.cancel_keyboard())
    return RENAME_SERVICE


async def receive_rename_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data["rename_service_name"] = clean_name(update.effective_message.text or "")
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return RENAME_SERVICE
    await update.effective_message.reply_text("Enter the new account label.", reply_markup=keyboards.cancel_keyboard())
    return RENAME_LABEL


async def receive_rename_label(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data["rename_account_label"] = clean_name(update.effective_message.text or "", max_length=160)
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=keyboards.cancel_keyboard())
        return RENAME_LABEL
    await update.effective_message.reply_text(
        f"Confirm rename to:\nService: {context.user_data['rename_service_name']}\n"
        f"Account: {context.user_data['rename_account_label']}",
        reply_markup=keyboards.rename_confirm(),
    )
    return RENAME_CONFIRM


async def confirm_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_onboarded_user(update, context)
    if user is None:
        return ConversationHandler.END
    with session_scope(runtime(context).session_factory) as session:
        account = AccountRepository(session).rename_for_user(
            user.id,
            context.user_data["rename_account_id"],
            context.user_data["rename_service_name"],
            context.user_data["rename_account_label"],
        )
    context.user_data.clear()
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "✅ Account renamed." if account else "Account not found.", reply_markup=keyboards.main_menu()
    )
    return ConversationHandler.END


async def begin_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await require_onboarded_user(update, context) is None:
        return ConversationHandler.END
    await _reply_or_edit(update, "Enter an export password.", reply_markup=keyboards.cancel_keyboard())
    return EXPORT_PASSWORD


async def receive_export_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_onboarded_user(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    try:
        password = clean_pin(update.effective_message.text or "")
    except ValueError as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(str(exc), reply_markup=keyboards.cancel_keyboard())
        return EXPORT_PASSWORD
    with session_scope(rt.session_factory) as session:
        accounts = list(AccountRepository(session).list_for_user(user.id))
        backup_bytes, export_hash = rt.backup.export_user_accounts(user_id=user.id, accounts=accounts, password=password)
        ExportRepository(session).record(user_id=user.id, file_name="totp-vault-backup.json.enc", export_hash=export_hash)
    await safe_delete_current_message(update)
    await update.effective_chat.send_document(
        document=InputFile(io.BytesIO(backup_bytes), filename="totp-vault-backup.json.enc"),
        caption="Encrypted backup created. Store it safely.",
    )
    await update.effective_chat.send_message(f"✅ Export complete. Hash prefix: {export_hash[:12]}", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


async def begin_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if await require_unlocked_vault(update, context) is None:
        return ConversationHandler.END
    await _reply_or_edit(update, "Upload the encrypted backup file.", reply_markup=keyboards.cancel_keyboard())
    return IMPORT_FILE


async def receive_import_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    document = update.effective_message.document
    if document is None:
        await update.effective_message.reply_text("Please upload the encrypted backup file.", reply_markup=keyboards.cancel_keyboard())
        return IMPORT_FILE
    file = await document.get_file()
    context.user_data["backup_bytes"] = bytes(await file.download_as_bytearray())
    await update.effective_message.reply_text("Enter the backup password.", reply_markup=keyboards.cancel_keyboard())
    return IMPORT_PASSWORD


async def receive_import_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_unlocked_vault(update, context)
    if user is None:
        return ConversationHandler.END
    rt = runtime(context)
    try:
        payload = rt.backup.decrypt_backup(context.user_data["backup_bytes"], clean_pin(update.effective_message.text or ""))
    except (ValueError, BackupError) as exc:
        await safe_delete_current_message(update)
        await update.effective_chat.send_message(f"Import failed: {exc}", reply_markup=keyboards.main_menu())
        context.user_data.clear()
        return ConversationHandler.END
    imported = skipped = 0
    with session_scope(rt.session_factory) as session:
        vault = VaultRepository(session).get_for_user(user.id)
        repo = AccountRepository(session)
        for record in payload["accounts"]:
            if repo.find_duplicate_for_user(user.id, record["service_name"], record["account_label"], record.get("issuer")):
                skipped += 1
                continue
            repo.create_for_user(
                user_id=user.id,
                vault_id=vault.id,
                service_name=record["service_name"],
                account_label=record["account_label"],
                issuer=record.get("issuer"),
                encrypted_secret=base64.b64decode(record["encrypted_secret"]),
                encrypted_metadata=record.get("encrypted_metadata"),
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
