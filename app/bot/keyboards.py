from __future__ import annotations

from collections.abc import Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import VaultAccount


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔐 Unlock Vault", callback_data="unlock")],
            [
                InlineKeyboardButton("📋 My Accounts", callback_data="accounts"),
                InlineKeyboardButton("➕ Add Account", callback_data="add"),
            ],
            [
                InlineKeyboardButton("🔎 Search", callback_data="search"),
                InlineKeyboardButton("📤 Export Backup", callback_data="export"),
            ],
            [
                InlineKeyboardButton("📥 Import Backup", callback_data="import"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
            [
                InlineKeyboardButton("🧾 Privacy", callback_data="privacy"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
    )


def onboarding_terms() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Accept Terms & Privacy", callback_data="accept_terms")]])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel")]])


def account_list(accounts: Sequence[VaultAccount], *, prefix: str = "account") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{account.service_name} - {account.account_label}", callback_data=f"{prefix}:{account.id}")]
        for account in accounts
    ]
    rows.append([InlineKeyboardButton("⬅️ Main Menu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def account_actions(account_id: str) -> InlineKeyboardMarkup:
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


def delete_confirm(account_id: str) -> InlineKeyboardMarkup:
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
