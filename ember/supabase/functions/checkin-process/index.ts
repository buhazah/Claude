// PRD §4.3.5 / §8.2 — Verified date check-in: mutual check-in verifies the date,
// triggers Glow metered billing, and satisfies the Date Guarantee.
import { admin, json, requireUser } from "../_shared/supabase.ts";

const STRIPE_KEY = Deno.env.get("STRIPE_SECRET_KEY");

Deno.serve(async (req) => {
  try {
    const { user } = await requireUser(req);
    const { proposal_id } = await req.json();

    const { data: p } = await admin.from("date_proposals")
      .select("*, conversations!inner(user_a, user_b)").eq("id", proposal_id).single();
    if (!p) return json({ error: "Not found" }, 404);
    const conv = p.conversations;
    if (conv.user_a !== user.id && conv.user_b !== user.id) return json({ error: "Forbidden" }, 403);
    if (p.status !== "accepted") return json({ error: "Date not confirmed" }, 400);
    // 24h check-in window after date day
    if (Date.now() > Date.parse(p.date_at) + 48 * 3600_000) {
      return json({ error: "Check-in window closed" }, 400);
    }

    const field = user.id === conv.user_a ? "checkin_a" : "checkin_b";
    await admin.from("date_proposals").update({ [field]: true }).eq("id", p.id);

    const other = field === "checkin_a" ? p.checkin_b : p.checkin_a;
    if (!other) return json({ verified: false, message: "Checked in — waiting on your date." });

    // Mutual check-in → verified
    await admin.from("date_proposals")
      .update({ verified_at: new Date().toISOString() }).eq("id", p.id);
    await admin.from("conversations").update({ date_verified: true }).eq("id", p.conversation_id);
    await admin.from("audit_log").insert({ user_id: user.id, action: "date_verified", detail: { proposal_id } });

    // Glow tier metered billing ($9 per verified date)
    if (STRIPE_KEY) {
      for (const uid of [conv.user_a, conv.user_b]) {
        const { data: sub } = await admin.from("subscriptions")
          .select("tier, stripe_customer_id").eq("user_id", uid).single();
        if (sub?.tier === "glow" && sub.stripe_customer_id) {
          await fetch("https://api.stripe.com/v1/billing/meter_events", {
            method: "POST",
            headers: {
              Authorization: `Bearer ${STRIPE_KEY}`,
              "content-type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
              event_name: "verified_date",
              "payload[stripe_customer_id]": sub.stripe_customer_id,
              "payload[value]": "1",
            }),
          }).catch(() => {});
        }
      }
    }
    return json({ verified: true, message: "Date verified. 🔥" });
  } catch (e) {
    if (e instanceof Response) return e;
    return json({ error: String(e) }, 500);
  }
});
