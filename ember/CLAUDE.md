# Ember — Claude Code project guide

AI-native dating app MVP (Ember PRD v1.0): 3 curated AI matches/day, mandatory
identity verification, ghost accountability, AI conversation coach, date
concierge. Revenue tied to verified first dates. See README.md for setup.

## Stack

- **App**: Expo SDK 52 (React Native 0.76) + Expo Router v4, TypeScript strict.
- **Backend**: Supabase (project ref `bauosctmdwumvuvyoemd`) — Postgres +
  pgvector (1024-dim HNSW), phone-OTP auth, Realtime, Storage, Edge Functions.
- **AI**: Claude API + Deepgram STT + Voyage embeddings — **server-side only**,
  inside Edge Functions. Never put API keys or AI calls in the app.

## Commands

```bash
npm run typecheck   # tsc --noEmit — must pass; CI runs this on every PR
npm start           # expo start
```

## Layout

- `app/` — Expo Router screens: `(onboarding)/` phone→otp→verify-identity→
  voice→intent→review, `(tabs)/` Matches·Chat·Dates·Profile, `chat/[id].tsx`.
- `src/lib/` — supabase client + shared types; `src/theme/` — dark theme tokens;
  `src/components/` — shared UI.
- `supabase/migrations/` — 0001 schema+RLS, 0002 match RPC+crons, 0003
  auth+storage. Add new migrations as `NNNN_name.sql`; never edit applied ones.
- `supabase/functions/` — 8 Edge Functions (Deno); `_shared/` has Claude and
  Supabase helpers. Cron-triggered functions (`match-generate`, `coach-nudge`,
  `ghost-detect`, `trust-score-update`) run with `verify_jwt = false` and check
  `INTERNAL_SECRET`; user-invoked ones require JWT.

## CI/CD (root `.github/workflows/`)

- `ci.yml` — typecheck on every PR; EAS iOS build on main (needs `EXPO_TOKEN`).
- `eas-build.yml` — dispatchable; builds installable release APK on the runner
  and uploads the `ember-android-apk` artifact.
- `supabase-deploy.yml` — dispatchable; on main it pushes migrations, deploys
  all 8 functions, and sets function secrets (needs `SUPABASE_*` + AI keys as
  repo secrets).

## Product rules (do not regress)

- Max 3 matches/day (1 on free tier); matches expire after 48h; no browsing.
- No rematch within 90 days; passed profiles excluded 30 days.
- Ghost = 7-day silence after 3+ exchanges → −8 reliability; <50 reliability or
  <60 trust excluded from match pool.
- Scores shown to matches only as tiers (Excellent/Good/Building), never raw.
- Voice audio deleted after 30 days; transcripts retained.
- Bio ≤160 chars, intent statement ≤120 chars (DB check constraints).
