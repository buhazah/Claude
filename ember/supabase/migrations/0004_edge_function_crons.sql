-- Schedule the Edge Function crons (PRD §7.3) in SQL via pg_cron + pg_net,
-- so no manual Dashboard configuration is needed.
--   match-generate : 0 1 * * *   (nightly matches, PRD §6.2)
--   coach-nudge    : 0 */6 * * * (PRD §6.3)
--   ghost-detect   : 0 */6 * * * (PRD §6.4)
-- The functions are deployed with verify_jwt=false; the anon key is sent as
-- the standard Supabase gateway Authorization header (public by design).

create extension if not exists pg_net;

do $do$
declare
  base_url text := 'https://bauosctmdwumvuvyoemd.supabase.co/functions/v1/';
  anon_key text := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJhdW9zY3RtZHd1bXZ1dnlvZW1kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEyMzAyMTQsImV4cCI6MjA5NjgwNjIxNH0.UCtWxpIxF1VL1Ev-4WeUTc5zxphj_t448hQMhprSXO0';
  fn record;
begin
  for fn in
    select * from (values
      ('invoke-match-generate', 'match-generate', '0 1 * * *'),
      ('invoke-coach-nudge',    'coach-nudge',    '0 */6 * * *'),
      ('invoke-ghost-detect',   'ghost-detect',   '0 */6 * * *')
    ) as t(jobname, func, schedule)
  loop
    -- cron.schedule upserts by job name, so re-running is safe
    perform cron.schedule(
      fn.jobname,
      fn.schedule,
      format(
        $job$select net.http_post(
          url := %L,
          headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', %L
          ),
          body := '{}'::jsonb
        )$job$,
        base_url || fn.func,
        'Bearer ' || anon_key
      )
    );
  end loop;
end
$do$;
