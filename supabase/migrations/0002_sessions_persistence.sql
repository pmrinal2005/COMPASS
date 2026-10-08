-- COMPASS · migration 0002 — session persistence + metric-aware watches
-- Run AFTER 0001_compass_schema.sql (Supabase SQL editor or `supabase db push`). Idempotent.

-- 1) Snapshots: lets a session survive a Render free-tier restart / redeploy (rehydrated lazily on first request).
create table if not exists public.session_snapshots (
  id          text primary key,                 -- = session id
  session_id  text,
  snapshot    jsonb not null,                   -- {state, ranked, actions, credits, events}
  updated_at  double precision default extract(epoch from now()),
  created_at  double precision default extract(epoch from now())
);
create index if not exists session_snapshots_updated_idx on public.session_snapshots (updated_at desc);
alter table public.session_snapshots enable row level security;

-- 2) Watches can now track a rating (venues) or a rank position (SEO) in addition to a price.
alter table public.watches add column if not exists metric        text default 'price';   -- price | rating | position
alter table public.watches add column if not exists target_domain text;

-- 3) Housekeeping: drop snapshots older than 14 days (call from a cron, e.g. the GitHub Action or pg_cron).
create or replace function public.prune_session_snapshots(max_age_days int default 14)
returns int language plpgsql as $$
declare n int;
begin
  delete from public.session_snapshots where updated_at < extract(epoch from now() - make_interval(days => max_age_days));
  get diagnostics n = row_count;
  return n;
end $$;

-- 4) Documents: speed up per-category retrieval for the new entity categories (venue / serp / ai_citation / event / stay).
create index if not exists documents_engine_idx on public.documents (engine);
