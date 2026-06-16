# Public Telegram TOTP Vault Bot

A public multi-user Telegram bot for storing encrypted TOTP authenticator setup secrets and generating OTP codes on demand. Each Telegram user gets an isolated vault protected by their own passphrase.

This is not a claim of perfect security. It is a practical design with encrypted storage, strict app-level authorization, short unlock sessions, safe logging, rate limits, and Supabase RLS as defense in depth.

## Security Model

- Every Telegram user has a separate `users` row, `vaults` row, and scoped `vault_accounts`.
- TOTP setup secrets are encrypted with a key derived from the user's vault passphrase and per-vault salt.
- Vault passphrases, backup passwords, plaintext setup keys, `otpauth://` URIs, and generated OTP codes are never stored.
- Generated OTP codes are sent as temporary Telegram messages and are not persisted.
- If a user forgets their vault passphrase, encrypted TOTP secrets cannot be recovered.
- Telegram bot messages pass through Telegram. Use Telegram 2FA and keep your Telegram account secure.

## Admin Limitations

Admins are configured with `ADMIN_TELEGRAM_IDS`.

Admins can view safe operational metadata:
- total users
- active/blocked/deleted counts
- total vault account count
- safe security events
- database/connectivity status
- block, unblock, and soft-delete users by Telegram ID
- broadcast announcements to active users

Admins cannot:
- view plaintext TOTP secrets
- view setup keys or `otpauth://` URIs
- view generated OTP codes
- view vault passphrases or backup passwords
- decrypt user vaults
- generate OTP codes for another user
- export plaintext vaults

## Supabase Setup

1. Create a Supabase project.
2. Get the direct Postgres connection string.
3. Set it as `SUPABASE_DB_URL`.
4. Run migrations in `app/db_migrations/` in order:
   - `001_public_multi_user_schema.sql`
   - `002_rls_policies.sql`

RLS policies are included as defense in depth. The Python bot still enforces app-level authorization on every repository call because backend service keys can bypass RLS.

## Environment Variables

Copy `.env.example` to `.env` and fill values:

```env
BOT_TOKEN=
SUPABASE_DB_URL=
SUPABASE_URL=
SUPABASE_SECRET_KEY=
ADMIN_TELEGRAM_IDS=
APP_ENV=development
LOG_LEVEL=INFO
VAULT_SESSION_SECONDS=180
CODE_MESSAGE_TTL_SECONDS=45
MAX_UNLOCK_ATTEMPTS=5
LOCKOUT_SECONDS=300
GLOBAL_RATE_LIMIT_PER_MINUTE=30
```

`SUPABASE_SECRET_KEY` must stay server-side. Do not put it in any client application.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Run Locally

```powershell
python run.py
```

For local tests, SQLite is supported as a development/test fallback. Production should use Supabase Postgres.

## BotFather Setup

1. Open Telegram and chat with `@BotFather`.
2. Send `/newbot`.
3. Copy the token into `BOT_TOKEN`.

## Commands

- `/start` - create/update user and start onboarding
- `/menu` - main menu
- `/unlock` - unlock your vault
- `/lock` - lock your vault
- `/add` - add a TOTP account
- `/accounts` - list your accounts
- `/code` - choose an account and show code
- `/search` - search your accounts
- `/rename` - rename your account
- `/delete` - delete your account entry
- `/export` - export encrypted backup
- `/import` - import encrypted backup
- `/settings` - show settings
- `/status` - show vault status
- `/privacy` - privacy notice
- `/terms` - terms
- `/security` - security guidance
- `/delete_my_data` - soft-delete your user status
- `/admin` - safe admin dashboard
- `/help` - help

## Admin Flow

Use `/admin` for the dashboard. Supported safe actions:

```text
/admin events
/admin db
/admin block <telegram_id>
/admin unblock <telegram_id>
/admin soft_delete <telegram_id>
/admin broadcast <message>
```

Admin actions record audit logs with safe metadata only. No admin command can decrypt vault data or generate another user's OTP code.

## User Flow

1. Send `/start`.
2. Accept terms and privacy notice.
3. Create and confirm a vault passphrase.
4. Unlock the vault when needed.
5. Add accounts using Base32 setup keys or `otpauth://totp/...` URIs.
6. View OTP codes from your own account list.

## Backup, Export, Import

Exports include only the current user's accounts. The backup payload is encrypted with an export password. Backup passwords are not stored or logged.

Imports decrypt the backup and insert only into the current user's vault. Duplicate accounts are skipped where possible.

## Data Deletion

Use `/delete_my_data` to soft-delete your account status and disable vault access. A hard-delete workflow can be added as a future operational command using the same user-scoped repository model.

## Troubleshooting

- Cannot connect to database: verify `SUPABASE_DB_URL`.
- Unlock fails: verify the vault passphrase.
- OTP codes fail: verify server clock and the setup key.
- Access denied to admin: verify `ADMIN_TELEGRAM_IDS`.
- Lost passphrase: encrypted secrets cannot be recovered.

## Security Checklist

- Keep `.env` private.
- Do not expose Supabase secret/service keys to clients.
- Use a strong vault passphrase.
- Enable Telegram 2FA.
- Keep recovery codes outside the bot.
- Avoid banking, crypto, and highly sensitive accounts during beta.
- Review logs before sharing; logging is designed to redact sensitive terms.
