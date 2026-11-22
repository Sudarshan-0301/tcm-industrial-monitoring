create extension if not exists pgcrypto;
create table if not exists public.tools (
 id uuid primary key default gen_random_uuid(), tool_id text unique not null,
 tool_type text not null, diameter_mm numeric not null check(diameter_mm>0),
 installed_on date not null, initial_condition text not null,
 status text not null default 'ACTIVE' check(status in ('ACTIVE','REPLACED')),
 replaced_at timestamptz, created_at timestamptz default now()
);
create table if not exists public.machining_sessions (
 id uuid primary key default gen_random_uuid(), tool_id uuid not null references public.tools(id),
 status text not null check(status in ('RUNNING','PAUSED','STOPPED')),
 segment_started_at timestamptz, elapsed_seconds bigint not null default 0,
 started_at timestamptz not null default now(), paused_at timestamptz, stopped_at timestamptz
);
create unique index if not exists one_open_session on public.machining_sessions((true)) where status in ('RUNNING','PAUSED');
create table if not exists public.sensor_recordings (
 id uuid primary key default gen_random_uuid(), filename text not null, sha256 text unique not null,
 row_count bigint, columns text[], tool_id uuid references public.tools(id),
 session_id uuid references public.machining_sessions(id), created_at timestamptz default now()
);
create table if not exists public.tool_inspections (
 id uuid primary key default gen_random_uuid(), tool_id uuid not null references public.tools(id),
 condition text not null check(condition in ('New','Old/Worn')), notes text, inspected_at timestamptz default now()
);
create table if not exists public.tool_lifecycle (
 id uuid primary key default gen_random_uuid(), tool_id uuid not null references public.tools(id),
 total_cutting_seconds bigint not null, closed_at timestamptz default now()
);
