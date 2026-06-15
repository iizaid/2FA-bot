# Personal Telegram TOTP Vault Bot

A private Telegram bot for storing TOTP authenticator setup secrets and generating 6-digit codes on demand. It is designed for one owner only, configured with `OWNER_TELEGRAM_ID`.

## Security Warning

This bot stores TOTP setup secrets only. Never send Telegram login codes, account passwords, Gmail passwords, Telegram 2FA passwords, recovery codes, or other real account credentials. Generated TOTP codes are not stored in the database.

## Features

- Owner-only access control.
- Encrypted TOTP secrets at rest.
- Local PIN/passphrase unlock with Argon2 hashing.
- Expiring vault sessions and `/lock`.
- Rate limiting for failed unlock attempts.
- Inline-button interface and slash commands.
- Encrypted backup export/import.
- SQLite local storage by default.

## Create a Telegram Bot Token

1. Open Telegram and chat with `@BotFather`.
2. Send `/newbot`.
3. Follow the prompts and copy the bot token.
4. Put the token in `.env` as `BOT_TOKEN`.

## Get Your Telegram User ID

Use a trusted ID bot such as `@userinfobot`, or temporarily run this bot and inspect your own update through Telegram tooling. Set the numeric ID as `OWNER_TELEGRAM_ID`.

## Generate `VAULT_MASTER_KEY`

Run:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the result in `.env` as `VAULT_MASTER_KEY`. If this key is lost, existing encrypted secrets cannot be decrypted.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and fill in `BOT_TOKEN`, `OWNER_TELEGRAM_ID`, and `VAULT_MASTER_KEY`.

## Run Locally

```powershell
python run.py
```

On startup, the bot creates the SQLite tables and sets the Telegram command list.

## Commands

- `/start` - Show welcome screen and main menu
- `/menu` - Show main menu
- `/unlock` - Unlock the vault
- `/lock` - Lock the vault
- `/add` - Add a new TOTP account
- `/accounts` - Show all saved accounts
- `/code` - Choose account and show current TOTP code
- `/search` - Search accounts
- `/rename` - Rename an account
- `/delete` - Delete an account
- `/export` - Export encrypted backup
- `/import` - Import encrypted backup
- `/settings` - Show settings
- `/status` - Show vault status
- `/help` - Show help

## Usage Flow

1. Start the bot with `/start`.
2. Choose `Unlock Vault`. On first use, create a local PIN/passphrase.
3. Choose `Add Account`.
4. Enter service name and account label.
5. Send only the TOTP setup key or `otpauth://totp/...` URI.
6. Enter the current setup code from the service page to verify the secret.
7. Use `My Accounts` and `Show Code` to generate codes.

Code messages are auto-deleted according to `CODE_MESSAGE_TTL_SECONDS` when Telegram allows deletion.

## Backup and Import

Use `/export` to create an encrypted backup file. The export password is separate from the vault PIN. Store both the backup and password safely.

Use `/import` to upload a backup and enter its password. Duplicate accounts are skipped when possible.

## Troubleshooting

- `Access denied`: verify `OWNER_TELEGRAM_ID`.
- Bot does not start: verify `BOT_TOKEN` and dependencies.
- Cannot decrypt accounts: verify the same `VAULT_MASTER_KEY` is configured.
- Codes fail on services: check your system clock and confirm the setup key was copied correctly.
- No auto-delete: Telegram may reject deleting older messages or messages outside bot permissions.

## Security Checklist

- Keep `.env` private.
- Back up `VAULT_MASTER_KEY` securely.
- Use a strong local PIN/passphrase.
- Run the bot only on a trusted machine.
- Do not paste passwords, recovery codes, or Telegram login codes into the bot.
- Review logs before sharing; logs are designed to avoid sensitive data.

