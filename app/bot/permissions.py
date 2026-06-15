from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.messages import ACCESS_DENIED

logger = logging.getLogger(__name__)


async def ensure_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings = context.bot_data["settings"]
    user = update.effective_user
    if user is not None and user.id == settings.owner_telegram_id:
        return True

    user_id = user.id if user else "unknown"
    logger.warning("Unauthorized Telegram user denied: user_id=%s", user_id)
    if update.callback_query is not None:
        await update.callback_query.answer("Access denied", show_alert=True)
        return False
    if update.effective_message is not None:
        await update.effective_message.reply_text(ACCESS_DENIED)
    return False

