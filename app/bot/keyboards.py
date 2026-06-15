from __future__ import annotations

from collections.abc import Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import Account


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔐 Unlock Vault", callback_data="unlock")],
            [
                InlineKeyboardButton("📋 My Accounts", callback_data="accounts"),
                InlineKeyboardButton("➕ Add Account", callback_data="add"),
            ],
            [
                InlineKeyboardButton("🔎 Search Account", callback_data="search"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
            [
                InlineKeyboardButton("🔒 Lock Vault", callback_data="lock"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel")]])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="accounts")]])


def account_list(accounts: Sequence[Account], *, prefix: str = "account") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{account.service_name} - {account.account_label}", callback_data=f"{prefix}:{account.id}")]
        for account in accounts
    ]
    rows.append([InlineKeyboardButton("⬅️ Main Menu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def account_actions(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔢 Show Code", callback_data=f"show_code:{account_id}")],
            [
                InlineKeyboardButton("✏️ Rename", callback_data=f"rename:{account_id}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete:{account_id}"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="accounts")],
        ]
    )


def delete_confirm(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Yes, delete", callback_data=f"delete_yes:{account_id}")],
            [InlineKeyboardButton("Cancel", callback_data=f"account:{account_id}")],
        ]
    )


def rename_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Yes, rename", callback_data="rename_confirm")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")],
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Timeout 3m", callback_data="set_timeout:180"),
                InlineKeyboardButton("Timeout 10m", callback_data="set_timeout:600"),
            ],
            [
                InlineKeyboardButton("TTL 45s", callback_data="set_ttl:45"),
                InlineKeyboardButton("TTL 60s", callback_data="set_ttl:60"),
            ],
            [InlineKeyboardButton("⬅️ Main Menu", callback_data="menu")],
        ]
    )
