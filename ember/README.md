# 🔥 Ember — Date with Intent

AI-native dating app MVP per **Ember PRD v1.0**. Replaces infinite swiping with
3 curated AI matches per day, mandatory identity verification, ghost
accountability, an AI conversation coach, a date concierge, and revenue tied to
**verified first dates**.

> "The app designed to put itself out of business."

## Stack

| Layer | Tech |
|---|---|
| App | Expo (React Native) + Expo Router, TypeScript |
| Backend | Supabase — Postgres, Auth (phone OTP), Realtime, Storage, Edge Functions |
| Vector search | pgvector (1024-dim profile embeddings, HNSW) |
| AI | Claude API (server-side only, via Edge Functions) |
| STT | Deepgram Nova-2 |
| Embeddings | Voyage AI (1024-dim) |
| Payments | Stripe (subscriptions + metered billing + Date Guarantee coupon) |
| Identity | Persona hosted flow → webhook → `trust-score-update` |

## Repo layout

```
ember/
  app/                    Expo Router screens
    (onboarding)/         phone → otp → verify-identity → voice → intent → review
    (tabs)/               Matches · Chat · Dates · Profile
    chat/[id].tsx         Realtime chat + openers + coach nudges + concierge
  src/                    lib (supabase client, types), components, theme
  supabase/
    migrations/           schema, RLS, match RPC, crons, storage
    functions/            8 Edge Functions (all AI server-side)
```

### Edge Functions (PRD §7.3)

| Function | Trigger | Does |
|---|---|---|
| `profile-extract` | onboarding | Deepgram STT → Claude personality JSON → Voyage embedding |
| `match-generate` | cron 1 AM UTC | pgvector retrieval → Claude reasoned scoring → top 3 matches |
| `opener-generate` | on Connect | 3 personalized openers |
| `coach-nudge` | cron 6h | nudge after 24h silence (1/conv/24h, opt-out) |
| `ghost-detect` | cron 6h | 7-day silence → ghost event, −8 reliability |
| `date-concierge` | in chat | 3 tailored date ideas (Claude + Places API) |
| `checkin-process` | check-in | mutual check-in → verified date → Glow metered billing |
| `trust-score-update` | webhooks | trust score events (internal-secret guarded) |

## Setup

```bash
# 1. Supabase
supabase init && supabase link --project-ref YOUR_REF
supabase db push                      # runs migrations (pgvector, RLS, crons)
supabase functions deploy             # deploys all 8 functions

# 2. Secrets (server-side only — never in the client)
supabase secrets set ANTHROPIC_API_KEY=... DEEPGRAM_API_KEY=... \
  VOYAGE_API_KEY=... STRIPE_SECRET_KEY=... GOOGLE_PLACES_API_KEY=... \
  INTERNAL_SECRET=$(openssl rand -hex 32)
# Optional: CLAUDE_MODEL=...  (verify current models at docs.claude.com — PRD OQ-08)

# 3. Schedule the function crons (Dashboard → Edge Functions → Schedules)
#    match-generate 0 1 * * * · coach-nudge 0 */6 * * * · ghost-detect 0 */6 * * *

# 4. App
cp .env.example .env   # fill EXPO_PUBLIC_SUPABASE_URL / ANON_KEY
npm install && npm run ios
```

## Key product rules encoded

- **3 matches/day max** (1 on free Spark tier), expire after 48h, no browsing.
- **No client-side AI**: zero API keys in the app; everything via Edge Functions.
- Reliability: ghost (7d silence, 3+ exchanges) = −8; +2/ghost-free week; <50 reliability or <60 trust excluded from the match pool.
- Anti-repetition: no rematch within 90 days; passed profiles excluded 30 days.
- Voice audio deleted after 30 days; transcripts retained (PRD §9.3).
- Scores shown to matches as tiers (Excellent/Good/Building), never raw numbers.

## Not in this MVP (v2 / launch checklist)

- Persona webhook endpoint + production hosted-flow URL
- Stripe Checkout for the Ember tier + Date Guarantee coupon automation cron
- NSFW photo scan, content moderation pass on messages
- Push scheduling at 9 AM user-local (currently fires at match generation)
- PostHog + Sentry wiring; App Store safety-review documentation
