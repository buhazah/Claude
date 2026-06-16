-- Candidate retrieval RPC (PRD §6.2 Stage 1) + scheduled jobs.

create or replace function match_candidates(p_user_id uuid, p_limit int default 20)
returns setof profiles language sql stable security definer as $$
  with me as (select * from profiles where id = p_user_id)
  select p.* from profiles p, me
  where p.id <> me.id
    and p.verified and p.active and p.embedding is not null
    and p.trust_score > 60 and p.reliability_score > 50
    and p.age between me.age_min and me.age_max
    and me.age between p.age_min and p.age_max
    and p.gender = any (me.seeking) and me.gender = any (p.seeking)
    -- intent compatibility: figuring_it_out never paired with long_term
    and not ((p.intent = 'figuring_it_out' and me.intent = 'long_term')
          or (me.intent = 'figuring_it_out' and p.intent = 'long_term'))
    -- 50mi default radius (~haversine approximation)
    and (me.lat is null or p.lat is null or
         2 * 3961 * asin(sqrt(
           sin(radians(p.lat - me.lat)/2)^2 +
           cos(radians(me.lat)) * cos(radians(p.lat)) * sin(radians(p.lng - me.lng)/2)^2
         )) <= me.radius_miles)
    -- blocks (either direction)
    and not exists (select 1 from blocks b where (b.blocker, b.blocked) in ((me.id, p.id), (p.id, me.id)))
    -- anti-repetition: no rematch within 90 days; passed profiles excluded 30 days
    and not exists (
      select 1 from daily_matches m
      where ((m.user_a, m.user_b) = (least(me.id, p.id), greatest(me.id, p.id)))
        and (m.delivered_at > now() - interval '90 days'
             or (m.status = 'passed' and m.delivered_at > now() - interval '30 days')))
  order by p.embedding <=> me.embedding
  limit p_limit;
$$;

-- Expire matches past their 48h window
create or replace function expire_matches() returns void language sql as $$
  update daily_matches set status = 'expired'
  where status = 'pending' and expires_at < now();
$$;

-- Weekly reliability recovery: +2 per 7 ghost-free days (PRD §6.4)
create or replace function reliability_recovery() returns void language sql as $$
  update profiles p set reliability_score = least(100, reliability_score + 2)
  where reliability_score < 100
    and not exists (select 1 from ghost_events g
                    where g.ghoster = p.id and g.detected_at > now() - interval '7 days');
$$;

-- Voice audio retention: delete clip references after 30 days (storage purge via lifecycle)
create or replace function purge_old_voice() returns void language sql as $$
  update profiles set voice_clips = '{}'
  where created_at < now() - interval '30 days' and voice_clips <> '{}';
$$;

-- Cron schedule (Edge Function crons configured in supabase/config.toml; SQL jobs here)
select cron.schedule('expire-matches', '0 * * * *', $$select expire_matches()$$);
select cron.schedule('reliability-recovery', '0 4 * * 1', $$select reliability_recovery()$$);
select cron.schedule('purge-voice', '0 5 * * *', $$select purge_old_voice()$$);
