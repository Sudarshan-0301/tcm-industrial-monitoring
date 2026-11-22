create extension if not exists pgcrypto;

create table if not exists public.tools (
  id uuid primary key default gen_random_uuid(),
  tool_id text unique not null,
  tool_type text,
  diameter_mm numeric,
  installed_on date not null,
  initial_condition text not null check (initial_condition in ('New','Previously used')),
  status text not null default 'active' check (status in ('active','replaced')),
  replaced_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.machining_sessions (
  id uuid primary key default gen_random_uuid(),
  tool_id uuid not null references public.tools(id),
  status text not null default 'running' check (status in ('running','paused','stopped')),
  started_at timestamptz not null default now(),
  segment_started_at timestamptz not null default now(),
  paused_at timestamptz,
  stopped_at timestamptz,
  elapsed_seconds bigint not null default 0 check (elapsed_seconds >= 0),
  created_at timestamptz not null default now()
);

-- Enforce at most one open session across BOTH running and paused states.
create unique index if not exists one_open_machining_session
on public.machining_sessions ((true))
where status in ('running','paused');

create table if not exists public.sensor_recordings (
  id uuid primary key default gen_random_uuid(),
  filename text not null,
  sha256 text not null unique,
  row_count bigint,
  columns text[],
  tool_id uuid references public.tools(id),
  session_id uuid references public.machining_sessions(id),
  created_at timestamptz not null default now()
);

create table if not exists public.tool_inspections (
  id uuid primary key default gen_random_uuid(),
  tool_id uuid not null references public.tools(id),
  condition text not null check (condition in ('New','Old/Worn')),
  inspected_at timestamptz not null default now(),
  notes text
);

create table if not exists public.tool_lifecycle (
  id uuid primary key default gen_random_uuid(),
  tool_id uuid not null references public.tools(id),
  total_cutting_seconds bigint not null default 0,
  closed_at timestamptz not null default now()
);

create or replace function public.pause_machining_session(p_session_id uuid)
returns void language plpgsql security definer as $$
declare s public.machining_sessions%rowtype;
begin
  select * into s from public.machining_sessions where id=p_session_id for update;
  if not found or s.status <> 'running' then raise exception 'Session is not running'; end if;
  update public.machining_sessions
  set elapsed_seconds = elapsed_seconds + greatest(0, extract(epoch from (now()-segment_started_at))::bigint),
      status='paused', paused_at=now()
  where id=p_session_id;
end $$;

create or replace function public.resume_machining_session(p_session_id uuid)
returns void language plpgsql security definer as $$
begin
  update public.machining_sessions
  set status='running', segment_started_at=now(), paused_at=null
  where id=p_session_id and status='paused';
  if not found then raise exception 'Session is not paused'; end if;
end $$;

create or replace function public.stop_machining_session(p_session_id uuid)
returns void language plpgsql security definer as $$
declare s public.machining_sessions%rowtype;
begin
  select * into s from public.machining_sessions where id=p_session_id for update;
  if not found or s.status='stopped' then raise exception 'Session not found or already stopped'; end if;
  if s.status='running' then
    update public.machining_sessions
    set elapsed_seconds = elapsed_seconds + greatest(0, extract(epoch from (now()-segment_started_at))::bigint),
        status='stopped', stopped_at=now()
    where id=p_session_id;
  else
    update public.machining_sessions set status='stopped', stopped_at=now() where id=p_session_id;
  end if;
end $$;

create or replace function public.replace_tool_lifecycle(p_tool_id uuid)
returns void language plpgsql security definer as $$
declare total_seconds bigint;
begin
  if exists (select 1 from public.machining_sessions where tool_id=p_tool_id and status in ('running','paused')) then
    raise exception 'Stop the active session before replacing this tool';
  end if;
  select coalesce(sum(elapsed_seconds),0) into total_seconds
  from public.machining_sessions where tool_id=p_tool_id and status='stopped';
  update public.tools set status='replaced', replaced_at=now()
  where id=p_tool_id and status='active';
  if not found then raise exception 'Tool not found or already replaced'; end if;
  insert into public.tool_lifecycle(tool_id,total_cutting_seconds) values(p_tool_id,total_seconds);
end $$;
