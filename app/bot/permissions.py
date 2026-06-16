from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.runtime import BotRuntime
from app.db import session_scope
from app.models import User
from app.repositories.security_events import SecurityEventRepository
from app.repositories.users import UserRepository
from app.repositories.vaults import VaultRepository

logger = logging.getLogger(__name__)


def runtime(context: ContextTypes.DEFAULT_TYPE) -> BotRuntime:
    return context.bot_data["runtime"]


async def get_or_create_current_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    telegram_user = update.effective_user
    if telegram_user is None:
        return None
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        repo = UserRepository(session, admin_telegram_ids=rt.settings.admin_ids)
        user = repo.get_or_create_from_telegram(telegram_user)
        session.expunge(user)
        return user


async def require_registered_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    user = await get_or_create_current_user(update, context)
    if user is None:
        await _reply(update, "Telegram user context is missing. Please try /start again.")
        return None
    return user


async def require_active_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    user = await require_registered_user(update, context)
    if user is None:
        return None
    if user.status != "active":
        await _reply(update, "Your account is not active. Contact support if this is unexpected.")
        return None
    rt = runtime(context)
    if not rt.rate_limiter.allow_message(user.id):
        with session_scope(rt.session_factory) as session:
            SecurityEventRepository(session).record(
                event_type="message_rate_limit",
                severity="warning",
                user_id=user.id,
                telegram_id=user.telegram_id,
            )
        await _reply(update, "Too many requests. Please wait a moment and try again.")
        return None
    return user


async def require_onboarded_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    user = await require_active_user(update, context)
    if user is None:
        return None
    rt = runtime(context)
    with session_scope(rt.session_factory) as session:
        has_vault = VaultRepository(session).get_for_user(user.id) is not None
    if user.accepted_terms_at is None or not has_vault:
        await _reply(update, "Please complete onboarding first with /start.")
        return None
    return user


async def require_unlocked_vault(update: Update, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    user = await require_onboarded_user(update, context)
    if user is None:
        return None
    if runtime(context).auth.require_vault_key(user.id) is None:
        await _reply(update, "🔐 Vault locked. Please unlock your vault before viewing or changing secrets.")
        return None
    return user


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    user = await require_registered_user(update, context)
    if user is None:
        return None
    if user.role != "admin" or user.telegram_id not in runtime(context).settings.admin_ids:
        with session_scope(runtime(context).session_factory) as session:
            SecurityEventRepository(session).record(
                event_type="admin_denied",
                severity="warning",
                user_id=user.id,
                telegram_id=user.telegram_id,
            )
        await _reply(update, "Admin access denied.")
        return None
    return user


async def check_message_rate(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User) -> bool:
    if runtime(context).rate_limiter.allow_message(user.id):
        return True
    with session_scope(runtime(context).session_factory) as session:
        SecurityEventRepository(session).record(
            event_type="rate_limit",
            severity="warning",
            user_id=user.id,
            telegram_id=user.telegram_id,
        )
    await _reply(update, "Too many requests. Please wait a moment and try again.")
    return False


async def _reply(update: Update, text: str) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer(text[:200], show_alert=True)
    elif update.effective_message is not None:
        await update.effective_message.reply_text(text)
