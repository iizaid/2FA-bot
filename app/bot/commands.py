from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import Application, ContextTypes

from app.bot import keyboards
from app.bot.messages import HELP, PRIVACY, SECURITY, TERMS, WELCOME
from app.bot.permissions import require_active_user, require_admin, require_onboarded_user, runtime
from app.db import session_scope
from app.repositories.accounts import AccountRepository
from app.repositories.admin import AdminRepository
from app.repositories.security_events import SecurityEventRepository
from app.repositories.users import UserRepository
from app.repositories.vaults import VaultRepository

logger = logging.getLogger(__name__)


COMMANDS = [
    BotCommand("start", "Start onboarding or show menu"),
    BotCommand("menu", "Show main menu"),
    BotCommand("unlock", "Unlock the vault"),
    BotCommand("lock", "Lock your vault"),
    BotCommand("add", "Add a new TOTP account"),
    BotCommand("accounts", "Show your accounts"),
    BotCommand("code", "Choose account and show code"),
    BotCommand("search", "Search your accounts"),
    BotCommand("rename", "Rename your account"),
    BotCommand("delete", "Delete your account"),
    BotCommand("export", "Export encrypted backup"),
    BotCommand("import", "Import encrypted backup"),
    BotCommand("settings", "Show settings"),
    BotCommand("status", "Show vault status"),
    BotCommand("privacy", "Show privacy notice"),
    BotCommand("terms", "Show terms"),
    BotCommand("security", "Show security notes"),
    BotCommand("delete_my_data", "Soft-delete your data"),
    BotCommand("help", "Show help"),
    BotCommand("admin", "Admin dashboard"),
]


async def set_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(COMMANDS)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_active_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        vault = VaultRepository(session).get_for_user(user.id)
    if user.accepted_terms_at is None or vault is None:
        await update.effective_message.reply_text(
            f"{WELCOME}\n\n{TERMS}\n\n{PRIVACY}",
            reply_markup=keyboards.onboarding_terms(),
        )
        return
    await update.effective_message.reply_text("Main menu", reply_markup=keyboards.main_menu())


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    await _reply_or_edit(update, "Main menu", reply_markup=keyboards.main_menu())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_or_edit(update, HELP, reply_markup=keyboards.main_menu())


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_or_edit(update, PRIVACY, reply_markup=keyboards.main_menu())


async def terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_or_edit(update, TERMS, reply_markup=keyboards.main_menu())


async def security(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_or_edit(update, SECURITY, reply_markup=keyboards.main_menu())


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    rt.auth.lock(user.id)
    with session_scope(rt.session_factory) as session:
        vault = VaultRepository(session).get_for_user(user.id)
        if vault is not None:
            VaultRepository(session).mark_locked(vault)
    await _reply_or_edit(update, "🔒 Your vault is locked.", reply_markup=keyboards.main_menu())


async def accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        saved = list(AccountRepository(session).list_for_user(user.id))
    if not saved:
        await _reply_or_edit(update, "No accounts saved yet.", reply_markup=keyboards.main_menu())
        return
    await _reply_or_edit(update, "📋 Your saved accounts:", reply_markup=keyboards.account_list(saved))


async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await accounts(update, context)


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        saved = list(AccountRepository(session).list_for_user(user.id))
    await update.effective_message.reply_text(
        "Choose one of your accounts to rename:" if saved else "No accounts saved yet.",
        reply_markup=keyboards.account_list(saved, prefix="rename") if saved else keyboards.main_menu(),
    )


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        saved = list(AccountRepository(session).list_for_user(user.id))
    await update.effective_message.reply_text(
        "Choose one of your accounts to delete:" if saved else "No accounts saved yet.",
        reply_markup=keyboards.account_list(saved, prefix="delete") if saved else keyboards.main_menu(),
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_active_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        count = AccountRepository(session).count_for_user(user.id)
        has_vault = VaultRepository(session).get_for_user(user.id) is not None
    text = (
        "🔐 Vault status\n\n"
        f"Account status: {user.status}\n"
        f"Terms accepted: {'yes' if user.accepted_terms_at else 'no'}\n"
        f"Vault created: {'yes' if has_vault else 'no'}\n"
        f"Vault unlocked: {'yes' if rt.auth.is_unlocked(user.id) else 'no'}\n"
        f"Session remaining: {rt.auth.seconds_remaining(user.id)} seconds\n"
        f"Accounts: {count}"
    )
    await update.effective_message.reply_text(text, reply_markup=keyboards.main_menu())


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    text = (
        "⚙️ Settings\n\n"
        f"Vault lock timeout: {rt.settings.vault_session_seconds} seconds\n"
        f"Code message TTL: {rt.settings.code_message_ttl_seconds} seconds\n"
        "Auto-delete code messages: enabled\n"
        "Vault encryption: per-user passphrase-derived key"
    )
    await _reply_or_edit(update, text, reply_markup=keyboards.main_menu())


async def delete_my_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_active_user(update, context)
    if user is None:
        return
    rt = runtime(context)
    rt.auth.lock(user.id)
    with session_scope(rt.session_factory) as session:
        UserRepository(session).set_status(user.id, "deleted")
        SecurityEventRepository(session).record(
            event_type="user_soft_deleted",
            severity="warning",
            user_id=user.id,
            telegram_id=user.telegram_id,
        )
    await update.effective_message.reply_text("Your account has been marked deleted. Vault access is disabled.")


async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_user = await require_admin(update, context)
    if admin_user is None:
        return
    rt = runtime(context)
    args = context.args or []
    if args:
        await _admin_action(update, context, admin_user, args)
        return
    with session_scope(rt.session_factory) as session:
        stats = AdminRepository(session).stats()
        AdminRepository(session).record_audit(admin_user_id=admin_user.id, action="admin_dashboard")
    text = (
        "Admin dashboard\n\n"
        f"Total users: {stats['total_users']}\n"
        f"Active users: {stats['active_users']}\n"
        f"Blocked users: {stats['blocked_users']}\n"
        f"Deleted users: {stats['deleted_users']}\n"
        f"Vault accounts: {stats['vault_accounts']}\n\n"
        "Safe actions:\n"
        "/admin events\n"
        "/admin db\n"
        "/admin block <telegram_id>\n"
        "/admin unblock <telegram_id>\n"
        "/admin soft_delete <telegram_id>\n"
        "/admin broadcast <message>\n\n"
        "Secrets and OTP codes are not available."
    )
    await update.effective_message.reply_text(text)


async def _admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_user, args: list[str]) -> None:
    rt = runtime(context)
    action = args[0].lower()
    with session_scope(rt.session_factory) as session:
        admin_repo = AdminRepository(session)
        user_repo = UserRepository(session)
        event_repo = SecurityEventRepository(session)
        if action in {"block", "unblock", "soft_delete"} and len(args) >= 2:
            target = user_repo.set_status_by_telegram_id(
                int(args[1]),
                {"block": "blocked", "unblock": "active", "soft_delete": "deleted"}[action],
            )
            admin_repo.record_audit(
                admin_user_id=admin_user.id,
                action=f"admin_{action}",
                target_user_id=target.id if target else None,
                safe_metadata={"target_telegram_id": int(args[1]), "found": target is not None},
            )
            await update.effective_message.reply_text("Action applied." if target else "Target user not found.")
            return
        if action == "events":
            events = event_repo.recent(10)
            lines = [f"{event.created_at.isoformat()} {event.severity} {event.event_type}" for event in events]
            admin_repo.record_audit(admin_user_id=admin_user.id, action="admin_events")
            await update.effective_message.reply_text("\n".join(lines) if lines else "No security events.")
            return
        if action == "db":
            stats = admin_repo.stats()
            admin_repo.record_audit(admin_user_id=admin_user.id, action="admin_db")
            await update.effective_message.reply_text(f"Database reachable. Users: {stats['total_users']}. Accounts: {stats['vault_accounts']}.")
            return
        if action == "broadcast" and len(args) >= 2:
            message = " ".join(args[1:]).strip()
            telegram_ids = list(user_repo.list_active_telegram_ids())
            admin_repo.record_audit(
                admin_user_id=admin_user.id,
                action="admin_broadcast",
                safe_metadata={"recipient_count": len(telegram_ids)},
            )
    if action == "broadcast" and len(args) >= 2:
        sent = 0
        for telegram_id in telegram_ids:
            try:
                await context.bot.send_message(chat_id=telegram_id, text=f"Announcement:\n\n{message}")
                sent += 1
            except Exception:
                continue
        await update.effective_message.reply_text(f"Broadcast sent to {sent} active users.")
        return
    await update.effective_message.reply_text("Unknown admin action. Use /admin for help.")


async def random_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_active_user(update, context)
    if user is None:
        return
    await update.effective_message.reply_text("Use the menu buttons or /help.", reply_markup=keyboards.main_menu())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_type = type(context.error).__name__ if context.error else "UnknownError"
    logger.error("Unhandled bot error type=%s", error_type)
    if isinstance(update, Update) and update.effective_message is not None:
        await update.effective_message.reply_text("Something went wrong. Please try again from /menu.")


async def _reply_or_edit(update: Update, text: str, reply_markup=None) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=reply_markup)
