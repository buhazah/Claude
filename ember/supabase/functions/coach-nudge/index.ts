// PRD §4.3.2 / §6.3 — Conversation coach cron (every 6h).
// 24h silence in an active conversation → 1 personalized nudge to the non-replier.
import { admin, json, push } from "../_shared/supabase.ts";
import { claude } from "../_shared/claude.ts";

const SYSTEM = `You are a warm, low-pressure dating conversation coach. Write ONE short nudge (max 200 chars) suggesting how the user might re-engage their match, referencing their shared interests or conversation context. Plain text only, no quotes.`;

Deno.serve(async () => {
  const { data: convs } = await admin.from("conversations")
    .select("*").eq("status", "active")
    .gte("message_count", 3)
    .lt("last_message_at", new Date(Date.now() - 24 * 3600_000).toISOString())
    .gt("last_message_at", new Date(Date.now() - 7 * 24 * 3600_000).toISOString());

  let sent = 0;
  for (const c of convs ?? []) {
    // recipient = the one who hasn't replied
    const recipient = c.last_sender === c.user_a ? c.user_b : c.user_a;
    // hard limit: 1 nudge / conversation / 24h
    if (c.last_nudge_at && Date.now() - Date.parse(c.last_nudge_at) < 24 * 3600_000) continue;

    const { data: r } = await admin.from("profiles")
      .select("personality, coach_nudges_enabled, expo_push_token").eq("id", recipient).single();
    if (!r?.coach_nudges_enabled) continue;
    const other = recipient === c.user_a ? c.user_b : c.user_a;
    const { data: o } = await admin.from("profiles")
      .select("first_name, personality").eq("id", other).single();
    const { data: msgs } = await admin.from("messages")
      .select("sender, body").eq("conversation_id", c.id)
      .order("created_at", { ascending: false }).limit(6);

    try {
      const nudge = await claude(SYSTEM,
        `Recipient profile: ${JSON.stringify(r.personality)}\nMatch (${o!.first_name}): ${JSON.stringify(o!.personality)}\nRecent messages (newest first): ${JSON.stringify(msgs)}`,
        300);
      // Nudge visible only to recipient: stored flagged, filtered client-side by sender=null+flag
      await admin.from("messages").insert({
        conversation_id: c.id, sender: null, body: nudge, is_coach_nudge: true,
      });
      await admin.from("conversations").update({ last_nudge_at: new Date().toISOString() }).eq("id", c.id);
      await push(r.expo_push_token, "Ember Coach", "A little momentum goes a long way — open your chat for a tip.");
      sent++;
    } catch { /* skip on AI failure */ }
  }
  return json({ nudges: sent });
});
