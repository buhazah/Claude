// PRD §4.3.3 / §6.4 — Ghost accountability cron (every 6h).
import { admin, json, push } from "../_shared/supabase.ts";

const GHOST_DAYS = 7;

Deno.serve(async () => {
  const cutoff = new Date(Date.now() - GHOST_DAYS * 24 * 3600_000).toISOString();
  const { data: convs } = await admin.from("conversations")
    .select("*").eq("status", "active")
    .gte("message_count", 3)
    .lt("last_message_at", cutoff)
    .not("last_sender", "is", null);

  let detected = 0;
  for (const c of convs ?? []) {
    const ghoster = c.last_sender === c.user_a ? c.user_b : c.user_a;
    const ghosted = c.last_sender;

    await admin.from("ghost_events").insert({
      conversation_id: c.id, ghoster, ghosted,
    });
    // -8 reliability, floor 0
    const { data: g } = await admin.from("profiles")
      .select("reliability_score").eq("id", ghoster).single();
    await admin.from("profiles")
      .update({ reliability_score: Math.max(0, (g?.reliability_score ?? 100) - 8) })
      .eq("id", ghoster);
    await admin.from("conversations").update({ status: "ghost_detected" }).eq("id", c.id);

    const { data: victim } = await admin.from("profiles")
      .select("expo_push_token").eq("id", ghosted).single();
    await push(victim?.expo_push_token ?? null, "Ember",
      "This conversation has gone quiet. You've done everything right.");
    detected++;
  }
  return json({ ghost_events: detected });
});
