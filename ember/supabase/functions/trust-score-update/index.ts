// PRD §9.1 — Trust Score. Service-role only; never called from the client.
// Invoked by verification webhooks (Persona/Stripe Identity) and report review.
import { admin, json } from "../_shared/supabase.ts";

const EVENTS: Record<string, number> = {
  identity_verified: 40,   // mandatory, one-time (starts at 50 base)
  voice_complete: 20,
  profile_complete: 20,
  substantiated_report: -10,
};

Deno.serve(async (req) => {
  // Shared-secret guard: only server-side callers (webhooks, other functions)
  if (req.headers.get("x-internal-secret") !== Deno.env.get("INTERNAL_SECRET")) {
    return json({ error: "Forbidden" }, 403);
  }
  const { user_id, event } = await req.json();
  const delta = EVENTS[event];
  if (delta === undefined) return json({ error: "Unknown event" }, 400);

  const { data: p } = await admin.from("profiles")
    .select("trust_score, verified").eq("id", user_id).single();
  if (!p) return json({ error: "Not found" }, 404);

  const updates: Record<string, unknown> = {
    trust_score: Math.max(0, Math.min(100, (p.verified ? p.trust_score : 50) + delta)),
  };
  if (event === "identity_verified") updates.verified = true;

  await admin.from("profiles").update(updates).eq("id", user_id);
  await admin.from("audit_log").insert({ user_id, action: `trust:${event}`, detail: updates });
  return json({ trust_score: updates.trust_score });
});
