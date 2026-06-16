WELCOME = (
    "🔐 Welcome to TOTP Vault Bot.\n\n"
    "This public bot stores encrypted TOTP setup secrets for each user separately. "
    "Never send account passwords, Telegram login codes, recovery codes, or banking/crypto credentials.\n\n"
    "Telegram messages pass through Telegram, so use a strong vault passphrase and keep your Telegram account secure."
)

TERMS = (
    "Terms of Use\n\n"
    "This is a beta convenience tool for TOTP setup secrets. You are responsible for keeping recovery codes and "
    "account recovery options safe. Do not use this for highly sensitive accounts during beta."
)

PRIVACY = (
    "Privacy\n\n"
    "Stored data: Telegram profile metadata, encrypted vault data, encrypted account records, export metadata, "
    "and safe security events. Generated OTP codes are not stored. Admins cannot view plaintext secrets, setup keys, "
    "otpauth URIs, generated OTP codes, vault passphrases, or backup passwords. You can request data deletion with "
    "/delete_my_data."
)

SECURITY = (
    "Security\n\n"
    "Use Telegram 2FA, keep your Telegram account secure, and never send passwords or recovery codes. "
    "If your vault passphrase is lost, encrypted TOTP secrets cannot be recovered."
)

HELP = (
    "Commands: /start, /menu, /unlock, /lock, /add, /accounts, /code, /search, /rename, /delete, "
    "/export, /import, /settings, /status, /privacy, /terms, /security, /delete_my_data, /admin."
)

LOCKED = "🔐 Vault locked. Please unlock your vault before viewing codes."
CANCELLED = "Cancelled. Returning to the main menu."
