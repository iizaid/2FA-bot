-- RLS defense-in-depth policies.
-- The Telegram bot backend must still enforce app-level authorization on every query.
-- Supabase service role keys can bypass RLS, so do not rely on these policies alone.

alter table users enable row level security;
alter table vaults enable row level security;
alter table vault_accounts enable row level security;
alter table vault_sessions enable row level security;
alter table security_events enable row level security;
alter table encrypted_exports enable row level security;
alter table admin_audit_logs enable row level security;

-- These policies expect an app user id to be placed into request.jwt.claims.user_id
-- when using a non-service PostgREST/JWT flow. The bot repository layer also filters
-- every operation by user_id.

do $$
begin
  create policy users_self_select on users
    for select using (id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id');
exception when duplicate_object then null;
end $$;

do $$
begin
  create policy vaults_self_all on vaults
    using (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id')
    with check (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id');
exception when duplicate_object then null;
end $$;

do $$
begin
  create policy vault_accounts_self_all on vault_accounts
    using (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id')
    with check (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id');
exception when duplicate_object then null;
end $$;

do $$
begin
  create policy vault_sessions_self_all on vault_sessions
    using (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id')
    with check (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id');
exception when duplicate_object then null;
end $$;

do $$
begin
  create policy security_events_self_insert on security_events
    for insert with check (
      user_id is null or user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id'
    );
exception when duplicate_object then null;
end $$;

do $$
begin
  create policy encrypted_exports_self_all on encrypted_exports
    using (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id')
    with check (user_id::text = nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_id');
exception when duplicate_object then null;
end $$;

-- Admin audit logs are backend/admin-only operational records. The bot's
-- require_admin() guard controls reads/actions at the app layer. This policy
-- permits backend inserts while RLS remains enabled as defense in depth.
do $$
begin
  create policy admin_audit_logs_backend_insert on admin_audit_logs
    for insert with check (true);
exception when duplicate_object then null;
end $$;
