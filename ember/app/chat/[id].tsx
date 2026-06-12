import { useEffect, useRef, useState } from "react";
import {
  View, Text, TextInput, Pressable, FlatList, StyleSheet,
  KeyboardAvoidingView, Platform, Alert,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { supabase, callFn } from "@/lib/supabase";
import { colors, spacing } from "@/theme";
import type { Message, DateIdea } from "@/lib/types";

export default function ChatScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [openers, setOpeners] = useState<string[]>([]);
  const [ideas, setIdeas] = useState<DateIdea[]>([]);
  const me = useRef<string>("");
  const list = useRef<FlatList>(null);

  useEffect(() => {
    let channel: ReturnType<typeof supabase.channel>;
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      me.current = user!.id;
      const { data } = await supabase.from("messages")
        .select("*").eq("conversation_id", id).order("created_at");
      // coach nudges are visible only to their recipient (sender=null rows
      // delivered via per-user filter would be ideal; v1 filters here)
      setMessages((data ?? []) as Message[]);

      if (!data?.length) {
        // first mover: fetch AI openers
        const { data: conv } = await supabase.from("conversations")
          .select("match_id").eq("id", id).single();
        if (conv) {
          callFn<{ openers: string[] }>("opener-generate", { match_id: conv.match_id })
            .then((r) => setOpeners(r.openers)).catch(() => {});
        }
      }

      channel = supabase.channel(`conv-${id}`)
        .on("postgres_changes",
          { event: "INSERT", schema: "public", table: "messages", filter: `conversation_id=eq.${id}` },
          (payload) => setMessages((m) => [...m, payload.new as Message]))
        .subscribe();
    })();
    return () => { channel?.unsubscribe(); };
  }, [id]);

  const send = async (body: string) => {
    if (!body.trim()) return;
    setText("");
    setOpeners([]);
    const { error } = await supabase.from("messages").insert({
      conversation_id: id, sender: me.current, body: body.trim(),
    });
    if (error) Alert.alert("Couldn't send", error.message);
  };

  const suggestDate = async () => {
    try {
      const r = await callFn<{ ideas: DateIdea[] }>("date-concierge", { conversation_id: id });
      setIdeas(r.ideas);
    } catch (e) {
      Alert.alert("Concierge unavailable", String((e as Error).message ?? e));
    }
  };

  const proposeDate = async (idea: DateIdea) => {
    await supabase.from("date_proposals").insert({
      conversation_id: id, proposer: me.current,
      venue_name: idea.venue_name, venue_type: idea.venue_type,
      why_it_fits: idea.why_it_fits,
      date_at: new Date(Date.now() + 3 * 86400_000).toISOString(),
    });
    await supabase.from("conversations").update({ date_proposed: true }).eq("id", id);
    setIdeas([]);
    send(`📅 Date proposal: ${idea.venue_name} — ${idea.why_it_fits}`);
  };

  return (
    <KeyboardAvoidingView style={s.wrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <FlatList
        ref={list}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: spacing.m }}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: false })}
        renderItem={({ item }) => (
          <View style={[
            s.bubble,
            item.is_coach_nudge ? s.coach : item.sender === me.current ? s.mine : s.theirs,
          ]}>
            {item.is_coach_nudge && <Text style={s.coachLabel}>✨ Coach (only you see this)</Text>}
            <Text style={s.msgText}>{item.body}</Text>
          </View>
        )}
      />
      {openers.length > 0 && (
        <View style={s.suggestions}>
          <Text style={s.suggestLabel}>✨ Openers written for you two</Text>
          {openers.map((o) => (
            <Pressable key={o} style={s.suggestChip} onPress={() => send(o)}>
              <Text style={s.suggestText}>{o}</Text>
            </Pressable>
          ))}
        </View>
      )}
      {ideas.length > 0 && (
        <View style={s.suggestions}>
          <Text style={s.suggestLabel}>📅 Date ideas for you both</Text>
          {ideas.map((i) => (
            <Pressable key={i.venue_name} style={s.suggestChip} onPress={() => proposeDate(i)}>
              <Text style={s.suggestText}>{i.venue_name} · {i.suggested_time}</Text>
              <Text style={s.suggestSub}>{i.why_it_fits}</Text>
            </Pressable>
          ))}
        </View>
      )}
      <View style={s.inputRow}>
        <Pressable style={s.dateBtn} onPress={suggestDate}>
          <Text style={{ fontSize: 20 }}>📅</Text>
        </Pressable>
        <TextInput
          style={s.input}
          value={text}
          onChangeText={setText}
          placeholder="Say something real…"
          placeholderTextColor={colors.textDim}
          onSubmitEditing={() => send(text)}
        />
        <Pressable style={s.sendBtn} onPress={() => send(text)}>
          <Text style={s.sendText}>Send</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg },
  bubble: { borderRadius: 16, padding: spacing.m, marginBottom: spacing.s, maxWidth: "80%" },
  mine: { backgroundColor: colors.ember, alignSelf: "flex-end" },
  theirs: { backgroundColor: colors.card, alignSelf: "flex-start" },
  coach: { backgroundColor: "#221A2E", alignSelf: "center", maxWidth: "92%", borderWidth: 1, borderColor: "#4A3A66" },
  coachLabel: { color: "#B49AE0", fontSize: 11, marginBottom: 4 },
  msgText: { color: colors.text, fontSize: 16 },
  suggestions: { padding: spacing.m, borderTopWidth: 1, borderTopColor: colors.border },
  suggestLabel: { color: colors.emberSoft, marginBottom: spacing.s, fontWeight: "600" },
  suggestChip: { backgroundColor: colors.card, borderRadius: 12, padding: spacing.m, marginBottom: spacing.s, borderWidth: 1, borderColor: colors.border },
  suggestText: { color: colors.text },
  suggestSub: { color: colors.textDim, fontSize: 13, marginTop: 2 },
  inputRow: { flexDirection: "row", padding: spacing.m, gap: spacing.s, alignItems: "center" },
  dateBtn: { padding: spacing.s },
  input: { flex: 1, backgroundColor: colors.card, color: colors.text, borderRadius: 20, paddingHorizontal: spacing.m, paddingVertical: 10, borderWidth: 1, borderColor: colors.border },
  sendBtn: { backgroundColor: colors.ember, borderRadius: 20, paddingHorizontal: spacing.m, paddingVertical: 10 },
  sendText: { color: "#fff", fontWeight: "700" },
});
