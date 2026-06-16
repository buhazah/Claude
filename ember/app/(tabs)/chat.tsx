import { useCallback, useState } from "react";
import { FlatList, Text, Pressable, StyleSheet, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { colors, spacing } from "@/theme";
import type { Conversation, Profile } from "@/lib/types";

export default function ChatList() {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const router = useRouter();

  useFocusEffect(useCallback(() => {
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase.from("conversations")
        .select("*")
        .or(`user_a.eq.${user.id},user_b.eq.${user.id}`)
        .neq("status", "archived")
        .order("last_message_at", { ascending: false, nullsFirst: false });
      const withProfiles = await Promise.all((data ?? []).map(async (c) => {
        const otherId = c.user_a === user.id ? c.user_b : c.user_a;
        const { data: other } = await supabase.from("profiles")
          .select("id, first_name, age, photos").eq("id", otherId).single();
        return { ...c, other: other as Profile };
      }));
      setConvs(withProfiles);
    })();
  }, []));

  return (
    <FlatList
      contentContainerStyle={{ padding: spacing.m, flexGrow: 1 }}
      data={convs}
      keyExtractor={(c) => c.id}
      ListEmptyComponent={
        <View style={s.empty}>
          <Text style={s.emptyText}>Connect with a match to start a conversation.</Text>
        </View>
      }
      renderItem={({ item }) => (
        <Pressable style={s.row} onPress={() => router.push(`/chat/${item.id}`)}>
          <Text style={s.name}>{item.other?.first_name}</Text>
          <Text style={s.status}>
            {item.date_verified ? "✓ Verified date" : item.status === "ghost_detected" ? "Gone quiet" : ""}
          </Text>
        </Pressable>
      )}
    />
  );
}

const s = StyleSheet.create({
  row: { backgroundColor: colors.card, borderRadius: 14, padding: spacing.m, marginBottom: spacing.s, flexDirection: "row", justifyContent: "space-between", borderWidth: 1, borderColor: colors.border },
  name: { color: colors.text, fontSize: 17, fontWeight: "600" },
  status: { color: colors.success, fontSize: 13 },
  empty: { flex: 1, justifyContent: "center", alignItems: "center" },
  emptyText: { color: colors.textDim, textAlign: "center" },
});
