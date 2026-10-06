-- COMPASS · Supabase schema (Postgres + pgvector + full-text hybrid retrieval)
-- Run in Supabase SQL editor (or `supabase db push`). Embedding dim = 768
-- (Gemini gemini-embedding-001 with outputDimensionality=768).

create extension if not exists vector;
create extension if not exists pg_trgm;

-- ---------------------------------------------------------------- documents
create table if not exists public.documents (
  id          text primary key,
  session_id  text,
  engine      text,
  category    text,
  title       text,
  content     text,
  url         text,
  price       double precision,
  embedding   vector(768),
  metadata    jsonb default '{}'::jsonb,
  fts         tsvector generated always as (
                 setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                 setweight(to_tsvector('english', coalesce(content, '')), 'B')) stored,
  created_at  timestamptz default now()
);
create index if not exists documents_embedding_idx on public.documents using hnsw (embedding vector_cosine_ops);
create index if not exists documents_fts_idx on public.documents using gin (fts);
create index if not exists documents_session_idx on public.documents (session_id);
create index if not exists documents_category_idx on public.documents (category);

-- Hybrid search: dense cosine rank + full-text rank fused with Reciprocal Rank Fusion
create or replace function public.hybrid_search(
  query_text       text,
  query_embedding  vector(768),
  match_count      int default 12,
  filter_session   text default null,
  filter_category  text default null,
  rrf_k            int default 50,
  full_text_weight float default 1.0,
  semantic_weight  float default 1.0
) returns table (
  id text, session_id text, engine text, category text, title text, content text, url text,
  price double precision, metadata jsonb, similarity float, dense_rank int, keyword_rank int, rrf_score float
) language sql stable as $$
  with pool as (
    select * from public.documents d
    where (filter_session is null or d.session_id = filter_session)
      and (filter_category is null or d.category = filter_category)
  ),
  full_text as (
    select p.id, row_number() over (order by ts_rank_cd(p.fts, websearch_to_tsquery('english', query_text)) desc) as rank_ix
    from pool p
    where p.fts @@ websearch_to_tsquery('english', query_text)
       or p.fts @@ plainto_tsquery('english', query_text)
    order by rank_ix
    limit least(match_count, 30) * 3
  ),
  semantic as (
    select p.id, row_number() over (order by p.embedding <=> query_embedding) as rank_ix
    from pool p
    where p.embedding is not null
    order by rank_ix
    limit least(match_count, 30) * 3
  )
  select d.id, d.session_id, d.engine, d.category, d.title, d.content, d.url, d.price, d.metadata,
         1 - (d.embedding <=> query_embedding) as similarity,
         semantic.rank_ix::int as dense_rank,
         full_text.rank_ix::int as keyword_rank,
         coalesce(1.0 / (rrf_k + full_text.rank_ix), 0.0) * full_text_weight +
         coalesce(1.0 / (rrf_k + semantic.rank_ix), 0.0) * semantic_weight as rrf_score
  from full_text
  full outer join semantic on full_text.id = semantic.id
  join public.documents d on d.id = coalesce(full_text.id, semantic.id)
  order by rrf_score desc
  limit least(match_count, 30);
$$;

-- ---------------------------------------------------------------- playbooks
create table if not exists public.playbooks (
  id          text primary key,
  name        text not null,
  lens        text,
  spec        jsonb not null,
  embedding   vector(768),
  created_at  timestamptz default now()
);

create or replace function public.match_playbooks(query_embedding vector(768), match_count int default 3)
returns table (id text, name text, similarity float) language sql stable as $$
  select id, name, 1 - (embedding <=> query_embedding) as similarity
  from public.playbooks where embedding is not null
  order by embedding <=> query_embedding limit match_count;
$$;

-- ---------------------------------------------------------------- sessions
create table if not exists public.sessions (
  id           text primary key,
  prompt       text,
  lens         text,
  status       text,
  playbook_id  text,
  confidence   double precision,
  replans      int default 0,
  summary      jsonb,
  created_at   double precision default extract(epoch from now())
);

-- ---------------------------------------------------------------- actions (HITL)
create table if not exists public.actions (
  id                 text primary key,
  session_id         text references public.sessions(id) on delete cascade,
  type               text,
  title              text,
  description        text,
  payload            jsonb,
  risk               text,
  requires_approval  boolean default true,
  status             text default 'pending',
  receipt            jsonb,
  created_at         double precision default extract(epoch from now())
);
create index if not exists actions_session_idx on public.actions (session_id);

-- ---------------------------------------------------------------- watches
create table if not exists public.watches (
  id               text primary key,
  session_id       text,
  label            text,
  engine           text,
  params           jsonb,
  target_title     text,
  baseline_price   double precision,
  last_price       double precision,
  threshold_pct    double precision default 8,
  cadence_minutes  int default 30,
  active           boolean default true,
  last_checked     double precision,
  history          jsonb default '[]'::jsonb,
  alerts           int default 0,
  created_at       double precision default extract(epoch from now())
);

-- ---------------------------------------------------------------- price history (anomaly baselines)
create table if not exists public.price_history (
  id           bigserial primary key,
  item_key     text not null,
  price        double precision not null,
  observed_at  timestamptz default now()
);
create index if not exists price_history_item_idx on public.price_history (item_key, observed_at desc);

-- ---------------------------------------------------------------- RLS
-- The backend uses the service-role key (bypasses RLS). Lock tables down for anon clients.
alter table public.documents     enable row level security;
alter table public.playbooks     enable row level security;
alter table public.sessions      enable row level security;
alter table public.actions       enable row level security;
alter table public.watches       enable row level security;
alter table public.price_history enable row level security;
