// PRD §6.2 — Nightly match job (cron 1:00 AM UTC).
// Stage 1: pgvector candidate retrieval → Stage 2: Claude reasoned scoring → top 3.
import { admin, json, push } from "../_shared/supabase.ts";
import { claude, claudeJSON } from "../_shared/claude.ts";

type Profile = {
  id: string; first_name: string; age: number; intent: string;
  intent_statement: string; personality: Record<string, unknown>;
  trust_score: number; reliability_score: number; expo_push_token: string | null;
};

const SCORING_SYSTEM = `You score dating compatibility. For each candidate, respond ONLY with valid JSON:
{"results":[{"candidate_id":"...","score":0-100,"reasons":["2-3 short human-readable reasons, e.g. 'You both value intentional Sundays'"],"conflict_flags":["internal only"]}]}
Consider values alignment, communication style match, lifestyle compatibility, and intent alignment. Penalize intent mismatch heavily.`;

const summarize = (p: Profile) =>
  `id=${p.id} intent=${p.intent} ("${p.intent_statement}") personality=${JSON.stringify(p.personality)}`;

Deno.serve(async () => {
  const today = new Date().toISOString().slice(0, 10);

  const { data: users } = await admin.from("profiles")
    .select("*, subscriptions(tier)")
    .eq("verified", true).eq("active", true).not("embedding", "is", null);
  if (!users) return json({ matched: 0 });

  let created = 0;
  for (const u of users) {
    const cap = u.subscriptions?.tier === "spark" ? 1 : 3;
    const { count } = await admin.from("daily_matches")
      .select("id", { count: "exact", head: true })
      .or(`user_a.eq.${u.id},user_b.eq.${u.id}`)
      .gte("delivered_at", `${today}T00:00:00Z`);
    if ((count ?? 0) >= cap) continue;

    // Stage 1 — pgvector retrieval with hard filters (RPC defined in migration 0002)
    const { data: candidates } = await admin.rpc("match_candidates", {
      p_user_id: u.id, p_limit: 20,
    });
    if (!candidates?.length) continue;

    // Stage 2 — Claude reasoned pass
    const prompt = `USER:\n${summarize(u)}\n\nCANDIDATES:\n` +
      candidates.map((c: Profile) => summarize(c)).join("\n");
    let scored: { candidate_id: string; score: number; reasons: string[] }[];
    try {
      scored = claudeJSON<{ results: typeof scored }>(
        await claude(SCORING_SYSTEM, prompt, 2048),
      ).results;
    } catch {
      continue; // skip user today rather than deliver unscored matches
    }

    const top = scored.sort((a, b) => b.score - a.score).slice(0, cap - (count ?? 0));
    for (const m of top) {
      const [a, b] = [u.id, m.candidate_id].sort();
      const { error } = await admin.from("daily_matches").insert({
        user_a: a, user_b: b, compat_score: m.score, compat_reasons: m.reasons,
      });
      if (!error) created++;
    }
    // Push is scheduled at 9 AM user-local by the push-dispatch cron; immediate
    // notification here only if local time is already past 9 AM.
    await push(u.expo_push_token, "Ember", "Your matches for today are ready. 🔥");
  }
  return json({ matched: created });
});
