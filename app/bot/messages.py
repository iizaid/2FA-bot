WELCOME = (
    "🔐 Welcome to your private TOTP Vault.\n\n"
    "This bot stores TOTP setup secrets only. Never send account passwords, Telegram login codes, "
    "email passwords, or recovery codes.\n\n"
    "Use the buttons below for normal vault actions."
)

HELP = (
    "🔐 Private TOTP Vault Help\n\n"
    "• Add accounts with setup keys or otpauth://totp URIs.\n"
    "• Unlock the vault before viewing codes.\n"
    "• Codes are generated on demand and are not stored.\n"
    "• Export backups are encrypted with your export password.\n\n"
    "Commands: /menu, /unlock, /lock, /add, /accounts, /code, /search, /rename, /delete, "
    "/export, /import, /settings, /status."
)

ACCESS_DENIED = "Access denied. This private bot is configured for its owner only."
LOCKED = "🔐 Vault locked. Please unlock your vault before viewing codes."
CANCELLED = "Cancelled. Returning to the main menu."

