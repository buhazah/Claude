import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// Service-role client: full access, used by crons and trusted server logic.
export const admin = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

// Client scoped to the calling user's JWT — respects RLS.
export function userClient(req: Request) {
  return createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: req.headers.get("Authorization")! } } },
  );
}

export async function requireUser(req: Request) {
  const supa = userClient(req);
  const { data, error } = await supa.auth.getUser();
  if (error || !data.user) throw new Response("Unauthorized", { status: 401 });
  return { supa, user: data.user };
}

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

export async function push(token: string | null, title: string, body: string) {
  if (!token) return;
  await fetch("https://exp.host/--/api/v2/push/send", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ to: token, title, body, sound: "default" }),
  }).catch(() => {});
}
