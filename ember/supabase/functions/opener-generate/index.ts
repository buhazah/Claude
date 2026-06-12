// PRD §6.3 — 3 personalized openers on Connect, shown to first mover only.
import { admin, json, requireUser } from "../_shared/supabase.ts";
import { claude, claudeJSON } from "../_shared/claude.ts";

const SYSTEM = `You write dating app conversation openers. Respond ONLY with valid JSON: {"openers":["...","...","..."]}.
Write 3 openers in User A's communication style, each referencing something specific from User B's profile. Warm, specific, never generic, never "hey". Max 140 chars each.`;

Deno.serve(async (req) => {
  try {
    const { user } = await requireUser(req);
    const { match_id } = await req.json();

    const { data: match } = await admin.from("daily_matches")
      .select("*").eq("id", match_id).single();
    if (!match || (match.user_a !== user.id && match.user_b !== user.id)) {
      return json({ error: "Not your match" }, 403);
    }
    const otherId = match.user_a === user.id ? match.user_b : match.user_a;
    const { data: me } = await admin.from("profiles")
      .select("personality, bio, intent_statement").eq("id", user.id).single();
    const { data: them } = await admin.from("profiles")
      .select("personality, bio, intent_statement, first_name").eq("id", otherId).single();

    const out = claudeJSON<{ openers: string[] }>(await claude(
      SYSTEM,
      `User A (sender): ${JSON.stringify(me)}\nUser B (${them!.first_name}): ${JSON.stringify(them)}\nCompatibility reasons: ${JSON.stringify(match.compat_reasons)}`,
    ));
    return json(out);
  } catch (e) {
    if (e instanceof Response) return e;
    return json({ error: String(e) }, 500);
  }
});
