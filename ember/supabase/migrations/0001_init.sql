-- Ember v1 schema (PRD §7.2)
create extension if not exists vector;
create extension if not exists pg_cron;

-- ── profiles ─────────────────────────────────────────────────────────
create type intent_type as enum ('long_term', 'open_to_long_term', 'figuring_it_out');
create type gender_type as enum ('woman', 'man', 'nonbinary');

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  phone text unique,
  first_name text,
  age int check (age >= 18),
  gender gender_type,
  seeking gender_type[],
  city text default 'Austin, TX',
  lat double precision,
  lng double precision,
  occupation_category text,
  photos text[] default '{}',            -- storage paths, first = card photo
  voice_clips text[] default '{}',       -- storage paths (deleted after 30d by cron)
  voice_transcripts jsonb,               -- [{question, transcript}]
  personality jsonb,                     -- Claude-extracted profile (PRD §6.1)
  embedding vector(1024),
  bio text check (char_length(bio) <= 160),
  intent intent_type,
  intent_statement text check (char_length(intent_statement) <= 120),
  verified boolean not null default false,
  trust_score int not null default 0 check (trust_score between 0 and 100),
  reliability_score int not null default 100 check (reliability_score between 0 and 100),
  coach_nudges_enabled boolean not null default true,
  age_min int default 24,
  age_max int default 34,
  radius_miles int default 50,
  expo_push_token text,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create index profiles_embedding_idx on profiles using hnsw (embedding vector_cosine_ops);

-- ── daily_matches ────────────────────────────────────────────────────
create type match_status as enum ('pending', 'connected', 'passed', 'expired');

create table daily_matches (
  id uuid primary key default gen_random_uuid(),
  user_a uuid not null references profiles(id) on delete cascade,
  user_b uuid not null references profiles(id) on delete cascade,
  compat_score int not null check (compat_score between 0 and 100),
  compat_reasons jsonb not null default '[]',
  a_action match_status not null default 'pending',
  b_action match_status not null default 'pending',
  status match_status not null default 'pending',
  delivered_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '48 hours',
  check (user_a < user_b)
);
-- index for fast per-user match lookups; anti-repetition enforced in match_candidates RPC
create index daily_matches_pair_idx on daily_matches (user_a, user_b, delivered_at desc);

-- ── conversations & messages ─────────────────────────────────────────
create type conv_status as enum ('active', 'stalling', 'ghost_detected', 'archived');

create table conversations (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null unique references daily_matches(id) on delete cascade,
  user_a uuid not null references profiles(id),
  user_b uuid not null references profiles(id),
  status conv_status not null default 'active',
  last_message_at timestamptz,
  last_sender uuid,
  message_count int not null default 0,
  last_nudge_at timestamptz,
  date_proposed boolean not null default false,
  date_confirmed boolean not null default false,
  date_verified boolean not null default false,
  created_at timestamptz not null default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  sender uuid references profiles(id),       -- null for system/coach messages
  body text not null,
  is_coach_nudge boolean not null default false,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
create index messages_conv_idx on messages (conversation_id, created_at);

create or replace function bump_conversation() returns trigger language plpgsql as $$
begin
  update conversations
     set last_message_at = new.created_at,
         last_sender = new.sender,
         message_count = message_count + 1,
         status = case when status = 'ghost_detected' then 'active' else status end
   where id = new.conversation_id and new.is_coach_nudge = false;
  return new;
end $$;
create trigger messages_bump after insert on messages for each row execute function bump_conversation();

-- ── ghost_events ─────────────────────────────────────────────────────
create table ghost_events (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id),
  ghoster uuid not null references profiles(id),
  ghosted uuid not null references profiles(id),
  detected_at timestamptz not null default now()
);

-- ── date_proposals ───────────────────────────────────────────────────
create type proposal_status as enum ('proposed', 'accepted', 'declined', 'countered');

create table date_proposals (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  proposer uuid not null references profiles(id),
  venue_name text not null,
  venue_type text,
  why_it_fits text,
  date_at timestamptz not null,
  status proposal_status not null default 'proposed',
  checkin_a boolean not null default false,
  checkin_b boolean not null default false,
  verified_at timestamptz,
  created_at timestamptz not null default now()
);

-- ── subscriptions ────────────────────────────────────────────────────
create type tier_type as enum ('spark', 'ember', 'glow');

create table subscriptions (
  user_id uuid primary key references profiles(id) on delete cascade,
  tier tier_type not null default 'spark',
  stripe_customer_id text,
  stripe_subscription_id text,
  current_period_start timestamptz,
  current_period_end timestamptz,
  guarantee_eligible boolean not null default false,
  created_at timestamptz not null default now()
);

-- ── reports / blocks / audit ─────────────────────────────────────────
create table blocks (
  blocker uuid not null references profiles(id) on delete cascade,
  blocked uuid not null references profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker, blocked)
);

create table reports (
  id uuid primary key default gen_random_uuid(),
  reporter uuid not null references profiles(id),
  reported uuid not null references profiles(id),
  category text not null check (category in ('fake_profile','harassment','inappropriate_content','other')),
  detail text,
  substantiated boolean,
  created_at timestamptz not null default now()
);

create table audit_log (
  id bigint generated always as identity primary key,
  user_id uuid,
  action text not null,
  detail jsonb,
  ip inet,
  created_at timestamptz not null default now()
);

-- ── RLS ──────────────────────────────────────────────────────────────
alter table profiles enable row level security;
alter table daily_matches enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;
alter table date_proposals enable row level security;
alter table subscriptions enable row level security;
alter table blocks enable row level security;
alter table reports enable row level security;
alter table ghost_events enable row level security;

create policy "own profile rw" on profiles
  for all using (id = auth.uid()) with check (id = auth.uid());
-- matched users may read each other's profile (limited columns enforced via view in app)
create policy "matched profiles readable" on profiles for select using (
  exists (select 1 from daily_matches m
          where (m.user_a = auth.uid() and m.user_b = profiles.id)
             or (m.user_b = auth.uid() and m.user_a = profiles.id))
);

create policy "own matches" on daily_matches for select
  using (user_a = auth.uid() or user_b = auth.uid());
create policy "act on own matches" on daily_matches for update
  using (user_a = auth.uid() or user_b = auth.uid());

create policy "own conversations" on conversations for select
  using (user_a = auth.uid() or user_b = auth.uid());

create policy "read own messages" on messages for select using (
  exists (select 1 from conversations c where c.id = conversation_id
          and (c.user_a = auth.uid() or c.user_b = auth.uid())));
create policy "send own messages" on messages for insert with check (
  sender = auth.uid() and exists (
    select 1 from conversations c where c.id = conversation_id
      and c.status <> 'archived'
      and (c.user_a = auth.uid() or c.user_b = auth.uid())));
create policy "delete own messages" on messages for delete using (sender = auth.uid());

create policy "own proposals" on date_proposals for all using (
  exists (select 1 from conversations c where c.id = conversation_id
          and (c.user_a = auth.uid() or c.user_b = auth.uid())));

create policy "own subscription" on subscriptions for select using (user_id = auth.uid());
create policy "own blocks" on blocks for all using (blocker = auth.uid()) with check (blocker = auth.uid());
create policy "file reports" on reports for insert with check (reporter = auth.uid());
create policy "own ghost view" on ghost_events for select using (ghosted = auth.uid() or ghoster = auth.uid());

-- trust_score / reliability_score / verified / embedding are written only by
-- service-role Edge Functions; client updates blocked via column privileges:
revoke update (trust_score, reliability_score, verified, embedding, personality) on profiles from authenticated;
