---
name: goose-ads
slug: goose-ads
description: >
  GooseWorks ads skill — create, edit, AND analyze ad creative. Remix a static (image) ad
  template into a branded ad for the user's product, edit/re-roll an existing creative,
  research a brand for ads, OR analyze ad performance (Meta/Google campaign diagnostics,
  creative fatigue, CAC & lead quality, competitor ad intelligence, ad angles & hooks). Use
  when the user says "remix this ad", references a static ad template id/slug, asks to "make
  an ad", "edit this ad", "research my brand", or asks to analyze/diagnose ad campaigns.
  Generation runs through the GooseWorks backend's single cloud workflow (the same one the ads
  app uses) — credits are reserved and billed server-side. Analytics recipes are fetched from
  goose-skills on demand.
category: ads
version: 2.0.0
author: GooseWorks
tags: [gooseworks, ads, remix, static-ad, brand, creative, image, analytics, meta-ads, performance]
---

# GooseWorks Ads — create, edit & analyze

The GooseWorks ads skill. Two jobs:

1. **Create / edit ad creative** — a **thin wrapper** over the backend's single generation
   workflow. You pick the brand + template(s) and submit ONE batch; the **backend** runs the
   whole pipeline (compose → generate → persist → judge), reserves and bills credits, and
   stores the renders. You do NOT generate images, call FAL, manage render rows, or upload
   files — those are gone. This is the exact same workflow the GooseWorks ads app uses, so the
   skill and the app can never drift.
2. **Analyze ad performance** — fetch ad-analytics recipes from goose-skills on demand
   (these are unrelated to generation; see "Analyze / intelligence" below).

## Prerequisite — the GooseWorks MCP server is REQUIRED

Everything goes through the `mcp__gooseworks__*` tools. If they are not available, **stop and
tell the user to run `gooseworks install --claude --mcp`** (and restart Claude Code). There is
no HTTP/file fallback — the REST ad endpoints are session-cookie-only and reject your token.

## Identity & credits

- One agent-scoped token authenticates the `gooseworks` MCP tools. Never print it. The tools
  resolve your org automatically — you do NOT resolve an "Ads agent" or pass `target` for the
  generation tools.
- **Credits are handled entirely by the backend.** `submit_remix_batch` reserves the estimated
  cost up front (it errors with `insufficient_credits` if the wallet is short — relay the
  message and stop) and bills only the images that actually complete. Call
  `estimate_remix_batch` first to tell the user the cost; `gooseworks credits` shows balance.

## Defaults — match the app (priority: frontend, then backend)

When the user doesn't specify, submit with the **ads app's** defaults so skill output matches
what they'd get in the UI. **Pass these explicitly:**

- `variants`: **1** per template
- `ratios`: **["4:5"]** (Meta feed vertical)
- `engine`: **"gpt_image_2"**
- `quality`: **"medium"**
- `preserve_source_styling`: **true** (keep the template's own colours/fonts; only restyle to
  the brand palette if the user explicitly asks to "match my brand colours")

If the user asks for something the app exposes (more variants, a different ratio like 1:1 or
9:16, a faster engine, higher quality), pass that instead. Omitting a field lets backend policy
decide — fine, but prefer sending the app defaults for predictable parity.

## The generation tools (the new, single-workflow surface)

- `submit_remix_batch { brand_id, items, prompt?, product_name?, preserve_source_styling?,
  reference_image_urls?, allow_without_product_image?, engine?, quality? }` — **the one call
  that makes ads.** `items` is `[{ template_id, variants?, ratios? }]` (≤20 templates).
  Returns the batch with a `links` block (`brand_url` + per-creative `app_url`). If the brand's
  research isn't finished yet the batch comes back `status: "queued"` — it auto-runs the moment
  research completes; tell the user it'll appear shortly, don't error.
- `estimate_remix_batch { items, engine?, quality? }` — cost preview (images, credits_per_image,
  total_credits, available_credits). `template_id` accepts a uuid OR a slug. Reserves nothing. Use
  to quote the cost first. Check `unknown_template_ids` in the response — any token there didn't
  resolve (submit would 404 on it); don't quote a cost that silently dropped a bad id.
- `get_remix_batch { batch_id }` — poll status. Returns each creative with its renders and
  `completed`/`failed`/`pending` counts, plus `links`. A creative is done when its `pending` is 0
  — NOT when `current_render_url` is set (during a regenerate that field still points at the prior
  image). Each render carries `age_seconds` (since queued) and `elapsed_seconds` (time generating):
  use them to tell a slow-but-healthy render from a stuck one. A render only failed when its
  `status` is `"failed"` — never assume a stall and re-submit, that double-bills.
- `list_brand_creatives { brand_id, limit?, offset? }` — the brand's gallery feed (newest
  first) + `brand_url`. Alternative poll target; also use to show everything made for a brand.
- `regenerate_creative { project_id, mode?, prompt?, source_render_id?, ... }` — **edit / re-roll
  one existing creative** through the same pipeline. `mode: "variation"` (default) re-rolls from
  the template; `"edit"` makes a targeted change to a specific render (`prompt` + `source_render_id`
  required); `"exact"` runs `prompt` verbatim against that render's references. Returns a
  single-item batch — poll it with `get_remix_batch`.

## Reading the brand & picking inputs (still MCP, read-only)

- `get_brand_kit { brand_id }` — the CANONICAL brand context (name, description, audience,
  voice, brandType, valueProps, colors, typography, logoUrl, `products[]`, presigned
  `referenceImages[]`). Read this to choose `product_name` and any `reference_image_urls`.
- `list_ad_brands { query? }` / `get_ad_brand { brand_id }` — find/fetch a brand. Pass `query` to
  filter by name (case-insensitive) instead of listing every brand; rows are lean (no `brand_kit` —
  read `get_brand_kit` for the full kit).
- `get_static_ad_template { template_id }` — resolve a template (slug OR uuid; public catalog
  AND your org's private templates). Confirms it exists before you submit.
- `remix_community_ad { community_id }` — a **Community** ad id is an `ad_project` id, not a
  template id. Call this FIRST to snapshot it into a private template, then use the returned
  template `id` in `items`.
- `create_user_ad_template { workspace_path }` — "bring your own ad": upload the user's own
  image as a private template, then remix it like any other.
- `get_ad_project` / `append_project_message` — inspect a creative / leave a note on its thread.

## Workflow — make ads from a template

1. **Resolve the brand.** `list_ad_brands` by name/site → `get_brand_kit { brand_id }`. If the
   kit's `researchStatus` isn't `complete`, you can still submit (the batch queues and runs when
   research finishes) — just tell the user. Use the kit to pick `product_name` (a real entry from
   `products[]`, not a guess) and, if the user supplied product photos, `reference_image_urls`.
2. **Resolve the template(s).** `get_static_ad_template { template_id }` for each. For a Community
   ad, `remix_community_ad` first; for an uploaded image, `create_user_ad_template` first.
3. **(Optional) Craft the steering prompt.** The `prompt` is OPTIONAL — this is where the skill
   adds value: turn the user's intent into a concise steering note (e.g. tone, season, emphasis).
   Don't over-specify; the backend pipeline + brand kit handle palette, fonts, product swap.
4. **(Optional) Quote the cost.** `estimate_remix_batch { items, engine, quality }` → tell the user.
5. **Submit ONE batch.** `submit_remix_batch { brand_id, items, prompt?, product_name?, engine,
   quality, preserve_source_styling }` using the app defaults above. Keep the returned `batch_id`
   and `links`.
6. **Poll until done.** `get_remix_batch { batch_id }` (or `list_brand_creatives`) every ~20-30s
   until every creative's `pending` is 0. Most images finish in a few minutes; text-heavy templates
   and `quality: high` take longer. Read each render's `elapsed_seconds` rather than guessing — a
   render that's still `running` is healthy; do NOT re-submit thinking it stalled (that double-bills).
7. **Hand back the links** from the batch's `links` block — `brand_url` (gallery) and each
   creative's `app_url` — copied verbatim. Never end on just "done" or a file path.

## Workflow — edit an existing ad

User wants to tweak a creative they already made → `regenerate_creative`:
- "make another version / different take" → `mode: "variation"` (optionally new `prompt`,
  `product_name`, `ratios`).
- "change X in this exact image" → `mode: "edit"`, `source_render_id` = the render to edit,
  `prompt` = the change.
- "run exactly this prompt on the product" → `mode: "exact"`, `source_render_id` + `prompt`.
Then poll with `get_remix_batch` and hand back the links, same as above.

## Brand research

Research normally runs in the GooseWorks backend (on onboarding). Just read the result with
`get_brand_kit`. If a brand doesn't exist yet, you may `create_ad_brand` and let backend
research run; you don't need to research locally. (A standalone local recipe still exists via
`gooseworks fetch brand-research` if the user explicitly wants the agent to do it.)

## Analyze / intelligence (fetched recipes — NOT generation)

These are analysis recipes you fetch from goose-skills with `gooseworks fetch <slug>` and
follow; they do NOT touch the generation tools or credits-for-images. Pick the closest match;
if unsure, `gooseworks search "<what the user wants>"` first:
- **Campaign performance diagnosis** ("why is my Meta/Google campaign underperforming",
  creative fatigue, learning phase, pacing, auction overlap) → `gooseworks fetch meta-ads-analyzer`
  (or `ad-campaign-analyzer` for cross-platform).
- **Lead/CAC quality** ("are these ads driving qualified leads", true CAC vs vanity CPA,
  Scale/Keep/Investigate/Cut) → `gooseworks fetch ad-lead-quality-analyzer`.
- **Competitor ad intelligence** ("what ads are competitors running") →
  `gooseworks fetch competitor-ad-intelligence` (Meta Ad Library: `meta-ad-scraper`;
  Google: `google-ad-scraper`).
- **Creative ideation** (ad angles, winning hooks) → `gooseworks fetch ad-angle-miner` /
  `gooseworks fetch trending-ad-hook-spotter`.
- **Policy / landing-page checks** → `gooseworks fetch meta-ad-policy-checker` /
  `gooseworks fetch ad-to-landing-page-auditor`.

Save their scripts to `/tmp/gooseworks-scripts/<slug>/` and follow their instructions. These
run through the `gooseworks` CLI (`gooseworks fetch` / `gooseworks call`), like the GTM skills.

## Rules

- **MCP required** — if `mcp__gooseworks__*` is unavailable, stop and tell the user to run
  `gooseworks install --claude --mcp`.
- **One backend workflow** — generation is `submit_remix_batch` / `regenerate_creative` ONLY.
  Do NOT call FAL, the media proxy, `submit_render`, `update_render_status`, or upload render
  files yourself; do NOT `gooseworks fetch` a local remix recipe to generate. The backend owns it.
- **Always end a successful run with the links** from the batch's `links` block (`brand_url` +
  each creative's `app_url`), copied verbatim. Never end on just "done" or a file path.
- **Quote cost before generating** when it's non-trivial (use `estimate_remix_batch`), and
  relay `insufficient_credits` plainly if the submit is rejected — don't retry blindly.
- **Don't busy-loop** — poll `get_remix_batch` on a sensible interval (~20-30s); a `queued`
  batch is waiting on research and will start on its own.
