import { useCallback, useState } from "react";
import { FlatList, View, Text, Pressable, StyleSheet, Alert } from "react-native";
import { useFocusEffect } from "expo-router";
import { supabase, callFn } from "@/lib/supabase";
import { colors, spacing } from "@/theme";

type Proposal = {
  id: string; venue_name: string; why_it_fits: string | null; date_at: string;
  status: string; verified_at: string | null; checkin_a: boolean; checkin_b: boolean;
  proposer: string;
  conversations: { user_a: string; user_b: string };
};

export default function Dates() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [me, setMe] = useState("");

  const load = useCallback(async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    setMe(user.id);
    const { data } = await supabase.from("date_proposals")
      .select("*, conversations!inner(user_a, user_b)")
      .order("date_at", { ascending: false });
    setProposals((data ?? []) as Proposal[]);
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const respond = async (p: Proposal, status: "accepted" | "declined") => {
    await supabase.from("date_proposals").update({ status }).eq("id", p.id);
    if (status === "accepted") {
      await supabase.from("conversations")
        .update({ date_confirmed: true })
        .eq("user_a", p.conversations.user_a).eq("user_b", p.conversations.user_b);
    }
    load();
  };

  const checkIn = async (p: Proposal) => {
    try {
      const r = await callFn<{ verified: boolean; message: string }>("checkin-process", { proposal_id: p.id });
      Alert.alert(r.verified ? "Date verified 🔥" : "Checked in", r.message);
      load();
    } catch (e) {
      Alert.alert("Check-in failed", String((e as Error).message ?? e));
    }
  };

  const myCheckin = (p: Proposal) =>
    me === p.conversations.user_a ? p.checkin_a : p.checkin_b;

  return (
    <FlatList
      contentContainerStyle={{ padding: spacing.m, flexGrow: 1 }}
      data={proposals}
      keyExtractor={(p) => p.id}
      ListEmptyComponent={
        <View style={s.empty}>
          <Text style={s.emptyText}>No dates yet. The concierge in any chat can fix that. 📅</Text>
        </View>
      }
      renderItem={({ item }) => (
        <View style={s.card}>
          <Text style={s.venue}>{item.venue_name}</Text>
          {item.why_it_fits && <Text style={s.why}>{item.why_it_fits}</Text>}
          <Text style={s.when}>{new Date(item.date_at).toLocaleString()}</Text>
          <Text style={s.status}>
            {item.verified_at ? "✓ Verified date" : item.status}
          </Text>
          {item.status === "proposed" && item.proposer !== me && (
            <View style={s.row}>
              <Pressable style={[s.btn, s.decline]} onPress={() => respond(item, "declined")}>
                <Text style={s.declineText}>Decline</Text>
              </Pressable>
              <Pressable style={[s.btn, s.accept]} onPress={() => respond(item, "accepted")}>
                <Text style={s.acceptText}>Accept</Text>
              </Pressable>
            </View>
          )}
          {item.status === "accepted" && !item.verified_at && !myCheckin(item) && (
            <Pressable style={[s.btn, s.accept, { marginTop: spacing.s }]} onPress={() => checkIn(item)}>
              <Text style={s.acceptText}>Check in — how did it go?</Text>
            </Pressable>
          )}
        </View>
      )}
    />
  );
}

const s = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: 16, padding: spacing.m, marginBottom: spacing.m, borderWidth: 1, borderColor: colors.border },
  venue: { color: colors.text, fontSize: 18, fontWeight: "700" },
  why: { color: colors.textDim, marginTop: 4 },
  when: { color: colors.emberSoft, marginTop: spacing.s },
  status: { color: colors.success, marginTop: 4, textTransform: "capitalize" },
  row: { flexDirection: "row", gap: spacing.s, marginTop: spacing.m },
  btn: { flex: 1, borderRadius: 12, padding: 12, alignItems: "center" },
  accept: { backgroundColor: colors.ember },
  decline: { backgroundColor: colors.border },
  acceptText: { color: "#fff", fontWeight: "700" },
  declineText: { color: colors.textDim },
  empty: { flex: 1, justifyContent: "center", alignItems: "center" },
  emptyText: { color: colors.textDim, textAlign: "center" },
});
