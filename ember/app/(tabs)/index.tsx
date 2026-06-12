import { useCallback, useState } from "react";
import { FlatList, Text, View, StyleSheet, RefreshControl } from "react-native";
import { useFocusEffect } from "expo-router";
import { supabase } from "@/lib/supabase";
import { MatchCard } from "@/components/MatchCard";
import { colors, spacing } from "@/theme";
import type { DailyMatch, Profile } from "@/lib/types";

export default function Matches() {
  const [matches, setMatches] = useState<DailyMatch[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return setLoading(false);
    const { data } = await supabase.from("daily_matches")
      .select("*")
      .or(`user_a.eq.${user.id},user_b.eq.${user.id}`)
      .eq("status", "pending")
      .gt("expires_at", new Date().toISOString())
      .order("delivered_at", { ascending: false });
    const withProfiles = await Promise.all((data ?? []).map(async (m) => {
      const otherId = m.user_a === user.id ? m.user_b : m.user_a;
      const { data: other } = await supabase.from("profiles")
        .select("id, first_name, age, city, occupation_category, photos, bio, intent, intent_statement, verified, trust_score, reliability_score, voice_clips")
        .eq("id", otherId).single();
      return { ...m, other: other as Profile };
    }));
    setMatches(withProfiles.filter((m) => m.other));
    setLoading(false);
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const act = async (match: DailyMatch, action: "connected" | "passed") => {
    const { data: { user } } = await supabase.auth.getUser();
    const field = match.user_a === user!.id ? "a_action" : "b_action";
    await supabase.from("daily_matches").update({ [field]: action }).eq("id", match.id);
    if (action === "connected") {
      // mutual connect → conversation (the other side may already have connected)
      const otherField = field === "a_action" ? "b_action" : "a_action";
      const { data: m } = await supabase.from("daily_matches").select("*").eq("id", match.id).single();
      if (m?.[otherField] === "connected") {
        await supabase.from("daily_matches").update({ status: "connected" }).eq("id", match.id);
        await supabase.from("conversations").insert({
          match_id: match.id, user_a: match.user_a, user_b: match.user_b,
        });
      }
    } else {
      await supabase.from("daily_matches").update({ status: "passed" }).eq("id", match.id);
    }
    setMatches((ms) => ms.filter((m) => m.id !== match.id));
  };

  return (
    <FlatList
      contentContainerStyle={s.list}
      data={matches}
      keyExtractor={(m) => m.id}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.ember} />}
      ListEmptyComponent={
        <View style={s.empty}>
          <Text style={s.emptyTitle}>No matches right now</Text>
          <Text style={s.emptyBody}>
            Your next 3 curated matches arrive at 9 AM. Quality over quantity — always.
          </Text>
        </View>
      }
      renderItem={({ item }) => (
        <MatchCard match={item} onConnect={() => act(item, "connected")} onPass={() => act(item, "passed")} />
      )}
    />
  );
}

const s = StyleSheet.create({
  list: { padding: spacing.m, flexGrow: 1 },
  empty: { flex: 1, justifyContent: "center", alignItems: "center", padding: spacing.xl },
  emptyTitle: { color: colors.text, fontSize: 20, fontWeight: "700" },
  emptyBody: { color: colors.textDim, textAlign: "center", marginTop: spacing.s, lineHeight: 22 },
});
