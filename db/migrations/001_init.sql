create extension if not exists pgcrypto;

create table if not exists sources (
  id uuid primary key default gen_random_uuid(),
  source_type text not null,
  source_name text not null unique,
  base_url text,
  reliability_weight numeric not null default 0.75,
  enabled boolean not null default true,
  rate_limit_policy jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists raw_items (
  id uuid primary key default gen_random_uuid(),
  source_type text not null,
  source_name text not null,
  external_id text,
  title text not null,
  abstract_or_description text,
  authors jsonb not null default '[]'::jsonb,
  institutions jsonb not null default '[]'::jsonb,
  url text,
  published_at timestamptz,
  fetched_at timestamptz not null default now(),
  raw_json jsonb not null default '{}'::jsonb,
  content_hash text not null,
  dedupe_key text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_raw_items_published_at on raw_items (published_at desc);
create index if not exists idx_raw_items_source on raw_items (source_name, source_type);

create table if not exists topics (
  id uuid primary key default gen_random_uuid(),
  canonical_name text not null unique,
  aliases jsonb not null default '[]'::jsonb,
  category text,
  priority_weight numeric not null default 1.0,
  watchlist_level text,
  enabled boolean not null default true
);

create table if not exists item_topic_matches (
  id uuid primary key default gen_random_uuid(),
  item_id uuid references raw_items(id) on delete cascade,
  topic_id uuid references topics(id) on delete cascade,
  match_score numeric not null default 0,
  matched_keywords jsonb not null default '[]'::jsonb,
  matched_methods jsonb not null default '[]'::jsonb,
  matched_datasets jsonb not null default '[]'::jsonb,
  matched_models jsonb not null default '[]'::jsonb,
  matched_tasks jsonb not null default '[]'::jsonb,
  unique (item_id, topic_id)
);

create table if not exists hourly_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_hour timestamptz not null,
  topic_id uuid references topics(id) on delete cascade,
  paper_count integer not null default 0,
  repo_count integer not null default 0,
  github_star_delta integer not null default 0,
  method_mentions integer not null default 0,
  dataset_mentions integer not null default 0,
  institution_mentions integer not null default 0,
  burst_score numeric not null default 0,
  magnitude numeric not null default 0,
  severity_label text not null,
  evidence_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  unique (snapshot_hour, topic_id)
);

create index if not exists idx_hourly_snapshots_hour on hourly_snapshots (snapshot_hour desc);
create index if not exists idx_hourly_snapshots_topic_hour on hourly_snapshots (topic_id, snapshot_hour desc);

create table if not exists daily_reports (
  id uuid primary key default gen_random_uuid(),
  report_date date not null unique,
  report_json_path text not null,
  report_md_path text not null,
  total_papers_scanned integer not null default 0,
  total_repos_scanned integer not null default 0,
  total_topics_tracked integer not null default 0,
  max_magnitude numeric not null default 0,
  status text not null default 'generated',
  generated_at timestamptz not null default now(),
  run_id text not null
);

create table if not exists repo_snapshots (
  id uuid primary key default gen_random_uuid(),
  repo_full_name text not null,
  url text,
  stars integer not null default 0,
  forks integer not null default 0,
  watchers integer not null default 0,
  open_issues integer not null default 0,
  pushed_at timestamptz,
  snapshot_at timestamptz not null default now(),
  topics jsonb not null default '[]'::jsonb,
  language text,
  description text,
  unique (repo_full_name, snapshot_at)
);

create index if not exists idx_repo_snapshots_repo_time on repo_snapshots (repo_full_name, snapshot_at desc);

create table if not exists institutions (
  id uuid primary key default gen_random_uuid(),
  canonical_name text not null unique,
  aliases jsonb not null default '[]'::jsonb,
  country_or_region text,
  institution_type text,
  weight numeric not null default 0.75
);

create table if not exists institution_topic_stats (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid references institutions(id) on delete cascade,
  topic_id uuid references topics(id) on delete cascade,
  window_start timestamptz not null,
  window_end timestamptz not null,
  paper_count integer not null default 0,
  repo_count integer not null default 0,
  concentration_score numeric not null default 0,
  unique (institution_id, topic_id, window_start, window_end)
);

create table if not exists watchlists (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  topic_id uuid references topics(id) on delete cascade,
  keywords jsonb not null default '[]'::jsonb,
  threshold_magnitude numeric not null default 3.5,
  threshold_growth_rate numeric not null default 1.0,
  push_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (name, topic_id)
);

create table if not exists push_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  topic_id uuid references topics(id) on delete set null,
  magnitude numeric not null default 0,
  severity_label text,
  payload_json jsonb not null default '{}'::jsonb,
  pushed_channels jsonb not null default '[]'::jsonb,
  pushed_at timestamptz not null default now(),
  dedupe_key text not null unique
);

create or replace view v_top_anomalous_topics as
select
  t.canonical_name,
  h.snapshot_hour,
  h.paper_count,
  h.repo_count,
  h.github_star_delta,
  h.magnitude,
  h.severity_label,
  h.evidence_json
from hourly_snapshots h
join topics t on t.id = h.topic_id
order by h.magnitude desc, h.snapshot_hour desc;
