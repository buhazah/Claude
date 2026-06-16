import { useCallback, useState } from "react";
import { ScrollView, View, Text, Pressable, StyleSheet, Switch, Alert, Image } from "react-native";
import { useFocusEffect } from "expo-router";
import { supabase } from "@/lib/supabase";
import { colors, spacing, trustTier } from "@/theme";
import type { Profile } from "@/lib/types";

export default function ProfileTab() {
  const [p, setP] = useState<(Profile & { coach_nudges_enabled: boolean }) | null>(null);

  useFocusEffect(useCallback(() => {
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase.from("profiles").select("*").eq("id", user.id).single();
      setP(data);
    })();
  }, []));

  const toggleNudges = async (v: boolean) => {
    setP((prev) => prev && { ...prev, coach_nudges_enabled: v });
    await supabase.from("profiles").update({ coach_nudges_enabled: v }).eq("id", p!.id);
  };

  const deleteAccount = () => {
    Alert.alert(
      "Delete your account?",
      "If you found someone — congratulations. That's exactly what we built this for. All data is removed within 45 days.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete", style: "destructive",
          onPress: async () => {
            const { data: { user } } = await supabase.auth.getUser();
            await supabase.from("audit_log").insert({ user_id: user!.id, action: "account_deletion_requested" });
            await supabase.from("profiles").update({ active: false }).eq("id", user!.id);
            await supabase.auth.signOut();
          },
        },
      ],
    );
  };

  if (!p) return null;
  return (
    <ScrollView contentContainerStyle={s.wrap}>
      {p.photos?.[0] && <Image source={{ uri: p.photos[0] }} style={s.photo} />}
      <Text style={s.name}>{p.first_name}{p.age ? `, ${p.age}` : ""}</Text>
      {p.bio && <Text style={s.bio}>{p.bio}</Text>}
      {p.intent_statement && <Text style={s.intent}>"{p.intent_statement}"</Text>}

      <View style={s.scores}>
        <View style={s.scoreBox}>
          <Text style={s.scoreNum}>{p.trust_score}</Text>
          <Text style={s.scoreLabel}>Trust · {trustTier(p.trust_score)}</Text>
        </View>
        <View style={s.scoreBox}>
          <Text style={s.scoreNum}>{p.reliability_score}</Text>
          <Text style={s.scoreLabel}>Reliability</Text>
        </View>
      </View>
      <Text style={s.scoreHint}>Matches only ever see your tier, never the number.</Text>

      <View style={s.row}>
        <Text style={s.rowText}>AI coach nudges</Text>
        <Switch value={p.coach_nudges_enabled} onValueChange={toggleNudges} trackColor={{ true: colors.ember }} />
      </View>

      <Pressable style={s.signOut} onPress={() => supabase.auth.signOut()}>
        <Text style={s.signOutText}>Sign out</Text>
      </Pressable>
      <Pressable onPress={deleteAccount}>
        <Text style={s.delete}>Delete account</Text>
      </Pressable>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  wrap: { padding: spacing.l },
  photo: { width: 120, height: 120, borderRadius: 60, alignSelf: "center" },
  name: { color: colors.text, fontSize: 26, fontWeight: "700", textAlign: "center", marginTop: spacing.m },
  bio: { color: colors.textDim, textAlign: "center", marginTop: spacing.s },
  intent: { color: colors.emberSoft, fontStyle: "italic", textAlign: "center", marginTop: spacing.s },
  scores: { flexDirection: "row", gap: spacing.m, marginTop: spacing.l },
  scoreBox: { flex: 1, backgroundColor: colors.card, borderRadius: 16, padding: spacing.m, alignItems: "center", borderWidth: 1, borderColor: colors.border },
  scoreNum: { color: colors.ember, fontSize: 32, fontWeight: "800" },
  scoreLabel: { color: colors.textDim, marginTop: 4 },
  scoreHint: { color: colors.textDim, fontSize: 12, textAlign: "center", marginTop: spacing.s },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: spacing.xl, backgroundColor: colors.card, borderRadius: 14, padding: spacing.m, borderWidth: 1, borderColor: colors.border },
  rowText: { color: colors.text, fontSize: 16 },
  signOut: { marginTop: spacing.xl, alignItems: "center", padding: spacing.m, borderRadius: 14, borderWidth: 1, borderColor: colors.border },
  signOutText: { color: colors.text },
  delete: { color: "#D9534F", textAlign: "center", marginTop: spacing.l, marginBottom: spacing.xl },
});
