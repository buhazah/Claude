// PRD §6.1 — Voice → Personality. Audio paths in, personality JSON + embedding out.
import { admin, json, requireUser } from "../_shared/supabase.ts";
import { claude, claudeJSON } from "../_shared/claude.ts";

const DEEPGRAM_KEY = Deno.env.get("DEEPGRAM_API_KEY")!;
// 1024-dim embeddings via Voyage AI (Anthropic's recommended embedding partner).
const VOYAGE_KEY = Deno.env.get("VOYAGE_API_KEY")!;

const QUESTIONS = [
  "What does a perfect Sunday look like for you?",
  "Describe someone you genuinely admire and why.",
  "What are you hoping to find here that you haven't found on other apps?",
];

const SYSTEM = `You analyze dating profile voice transcripts and extract a structured JSON personality profile. Respond ONLY with valid JSON — no preamble, no markdown, no explanation.
Extract: { "values": ["3-5 core values"], "communication_style": "string", "humor_style": "string", "lifestyle_signals": ["strings"], "attachment_signals": "string (internal only)", "curiosity_areas": ["strings"], "compatibility_tags": ["5-8 short tags"], "generated_bio": "first-person 2-sentence bio, max 160 chars", "intent_consistency_score": 0.0, "red_flags": ["internal only"] }`;

async function transcribe(audioPath: string): Promise<string> {
  const { data: signed } = await admin.storage.from("voice")
    .createSignedUrl(audioPath, 300);
  const res = await fetch(
    "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true",
    {
      method: "POST",
      headers: { Authorization: `Token ${DEEPGRAM_KEY}`, "content-type": "application/json" },
      body: JSON.stringify({ url: signed!.signedUrl }),
    },
  );
  const dg = await res.json();
  return dg.results?.channels?.[0]?.alternatives?.[0]?.transcript ?? "";
}

async function embed(input: string): Promise<number[]> {
  const res = await fetch("https://api.voyageai.com/v1/embeddings", {
    method: "POST",
    headers: { Authorization: `Bearer ${VOYAGE_KEY}`, "content-type": "application/json" },
    body: JSON.stringify({ model: "voyage-3-large", input, output_dimension: 1024 }),
  });
  const data = await res.json();
  return data.data[0].embedding;
}

Deno.serve(async (req) => {
  try {
    const { user } = await requireUser(req);
    const { audio_paths, intent, intent_statement } = await req.json();
    if (!Array.isArray(audio_paths) || audio_paths.length !== 3) {
      return json({ error: "Exactly 3 voice answers required" }, 400);
    }

    const transcripts = await Promise.all(audio_paths.map(transcribe));
    const voice_transcripts = transcripts.map((t, i) => ({ question: QUESTIONS[i], transcript: t }));

    const prompt = `Declared intent: ${intent} — "${intent_statement}"\n\n` +
      voice_transcripts.map((v) => `Q: ${v.question}\nA: ${v.transcript}`).join("\n\n");
    const personality = claudeJSON<Record<string, unknown>>(await claude(SYSTEM, prompt));

    const embInput = [
      transcripts.join(" "),
      (personality.values as string[]).join(", "),
      (personality.compatibility_tags as string[]).join(", "),
    ].join("\n");
    const embedding = await embed(embInput);

    const { error } = await admin.from("profiles").update({
      voice_clips: audio_paths,
      voice_transcripts,
      personality,
      embedding,
      bio: personality.generated_bio,
      intent,
      intent_statement,
    }).eq("id", user.id);
    if (error) throw error;

    return json({ bio: personality.generated_bio });
  } catch (e) {
    if (e instanceof Response) return e;
    return json({ error: String(e) }, 500);
  }
});
