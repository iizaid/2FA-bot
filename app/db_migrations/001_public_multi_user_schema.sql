-- Public multi-user Telegram TOTP Vault Bot schema for Supabase Postgres.
-- App-level authorization is mandatory. RLS is defense in depth because backend
-- service roles can bypass RLS.

create extension if not exists "pgcrypto";

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint unique not null,
  username text,
  first_name text,
  last_name text,
  language_code text,
  role text not null default 'user',
  status text not null default 'active',
  accepted_terms_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_seen_at timestamptz
);

create table if not exists vaults (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade unique,
  kdf_salt bytea not null,
  passphrase_hash text not null,
  encryption_scheme text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  locked_at timestamptz,
  last_unlocked_at timestamptz
);

create table if not exists vault_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  vault_id uuid references vaults(id) on delete cascade,
  service_name text not null,
  account_label text not null,
  issuer text,
  encrypted_secret bytea not null,
  encrypted_metadata jsonb,
  algorithm text not null default 'SHA1',
  digits integer not null default 6,
  period integer not null default 30,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_used_at timestamptz
);

create table if not exists vault_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  unlocked_until timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists security_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete set null,
  telegram_id bigint,
  event_type text not null,
  severity text not null default 'info',
  safe_metadata jsonb,
  created_at timestamptz not null default now()
);

create table if not exists admin_audit_logs (
  id uuid primary key default gen_random_uuid(),
  admin_user_id uuid references users(id) on delete set null,
  action text not null,
  target_user_id uuid references users(id) on delete set null,
  safe_metadata jsonb,
  created_at timestamptz not null default now()
);

create table if not exists encrypted_exports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  file_name text not null,
  export_hash text,
  created_at timestamptz not null default now()
);

create index if not exists idx_vault_accounts_user_id on vault_accounts(user_id);
create index if not exists idx_vault_sessions_user_id on vault_sessions(user_id);
create index if not exists idx_security_events_user_id on security_events(user_id);
