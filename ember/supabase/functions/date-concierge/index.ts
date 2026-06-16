// PRD §4.3.4 / §6.5 — 3 tailored date ideas for a conversation.
import { admin, json, requireUser } from "../_shared/supabase.ts";
import { claude, claudeJSON } from "../_shared/claude.ts";

const PLACES_KEY = Deno.env.get("GOOGLE_PLACES_API_KEY");

const SYSTEM = `You are a date concierge for Austin, TX. Respond ONLY with valid JSON:
{"ideas":[{"venue_name":"real specific venue","venue_type":"string","why_it_fits":"one specific sentence about why it fits BOTH people","suggested_time":"e.g. Sunday 10am","difficulty":"easy|medium|adventurous"}]}
Return exactly 3 ideas, varied in difficulty. Use the venue list if provided; otherwise use well-known real Austin venues.`;

Deno.serve(async (req) => {
  try {
    const { user } = await requireUser(req);
    const { conversation_id } = await req.json();

    const { data: c } = await admin.from("conversations")
      .select("*").eq("id", conversation_id).single();
    if (!c || (c.user_a !== user.id && c.user_b !== user.id)) {
      return json({ error: "Not your conversation" }, 403);
    }
    // Gate: 5+ days of active chat OR explicit tap — explicit tap is this call,
    // so only require the conversation to be active with some history.
    if (c.message_count < 3) return json({ error: "Chat a little more first" }, 400);

    const [{ data: a }, { data: b }, { data: msgs }] = await Promise.all([
      admin.from("profiles").select("personality, lat, lng, city").eq("id", c.user_a).single(),
      admin.from("profiles").select("personality, lat, lng, city").eq("id", c.user_b).single(),
      admin.from("messages").select("sender, body").eq("conversation_id", c.id)
        .eq("is_coach_nudge", false).order("created_at", { ascending: false }).limit(10),
    ]);

    let venues = "";
    if (PLACES_KEY && a?.lat && a?.lng) {
      const res = await fetch(
        `https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=${a.lat},${a.lng}&radius=8000&type=cafe&key=${PLACES_KEY}`,
      ).then((r) => r.json()).catch(() => null);
      venues = (res?.results ?? []).slice(0, 10)
        .map((v: { name: string; vicinity: string }) => `${v.name} (${v.vicinity})`).join("; ");
    }

    const out = claudeJSON<{ ideas: unknown[] }>(await claude(
      SYSTEM,
      `Person A: ${JSON.stringify(a?.personality)}\nPerson B: ${JSON.stringify(b?.personality)}\nRecent conversation: ${JSON.stringify(msgs)}\nToday: ${new Date().toDateString()}\nNearby venues: ${venues || "none — use known Austin spots"}`,
      1024,
    ));
    return json(out);
  } catch (e) {
    if (e instanceof Response) return e;
    return json({ error: String(e) }, 500);
  }
});
