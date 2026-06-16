import { View, Text, Image, Pressable, StyleSheet } from "react-native";
import { colors, spacing, trustTier } from "@/theme";
import type { DailyMatch } from "@/lib/types";

export function MatchCard({ match, onConnect, onPass }: {
  match: DailyMatch;
  onConnect: () => void;
  onPass: () => void;
}) {
  const p = match.other!;
  return (
    <View style={s.card}>
      {p.photos[0] ? (
        <Image source={{ uri: p.photos[0] }} style={s.photo} />
      ) : (
        <View style={[s.photo, s.photoEmpty]}><Text style={s.flame}>🔥</Text></View>
      )}
      <View style={s.body}>
        <View style={s.row}>
          <Text style={s.name}>{p.first_name}, {p.age}</Text>
          <View style={s.badge}>
            <Text style={s.badgeText}>✓ {trustTier(p.trust_score)}</Text>
          </View>
        </View>
        <Text style={s.meta}>{p.city}{p.occupation_category ? ` · ${p.occupation_category}` : ""}</Text>
        <Text style={s.compat}>{match.compat_score}% compatible</Text>
        {match.compat_reasons.map((r) => (
          <Text key={r} style={s.reason}>• {r}</Text>
        ))}
        {p.intent_statement && (
          <Text style={s.intent}>"{p.intent_statement}"</Text>
        )}
        <View style={s.actions}>
          <Pressable style={[s.btn, s.pass]} onPress={onPass}>
            <Text style={s.passText}>Pass</Text>
          </Pressable>
          <Pressable style={[s.btn, s.connect]} onPress={onConnect}>
            <Text style={s.connectText}>Connect</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: 20, overflow: "hidden", marginBottom: spacing.l, borderWidth: 1, borderColor: colors.border },
  photo: { width: "100%", height: 360 },
  photoEmpty: { alignItems: "center", justifyContent: "center", backgroundColor: colors.border },
  flame: { fontSize: 48 },
  body: { padding: spacing.m },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  name: { color: colors.text, fontSize: 24, fontWeight: "700" },
  badge: { backgroundColor: "#173324", borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4 },
  badgeText: { color: colors.success, fontSize: 12, fontWeight: "600" },
  meta: { color: colors.textDim, marginTop: 2 },
  compat: { color: colors.ember, fontSize: 18, fontWeight: "700", marginTop: spacing.s },
  reason: { color: colors.text, marginTop: 4 },
  intent: { color: colors.emberSoft, fontStyle: "italic", marginTop: spacing.s },
  actions: { flexDirection: "row", gap: spacing.m, marginTop: spacing.m },
  btn: { flex: 1, borderRadius: 14, paddingVertical: 14, alignItems: "center" },
  pass: { backgroundColor: colors.border },
  connect: { backgroundColor: colors.ember },
  passText: { color: colors.textDim, fontWeight: "600" },
  connectText: { color: "#fff", fontWeight: "700" },
});
