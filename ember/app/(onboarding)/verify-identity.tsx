import { View, Text, Pressable, StyleSheet, Linking } from "react-native";
import { useRouter } from "expo-router";
import { colors, spacing } from "@/theme";

// Identity verification is mandatory (PRD §4.1.2). v1 hands off to a Persona
// hosted flow; the Persona webhook calls trust-score-update server-side, which
// flips profiles.verified. The app polls verified status on return.
export default function VerifyIdentity() {
  const router = useRouter();
  const startVerification = async () => {
    await Linking.openURL(process.env.EXPO_PUBLIC_PERSONA_FLOW_URL ?? "https://withpersona.com");
    router.push("/(onboarding)/voice");
  };

  return (
    <View style={s.wrap}>
      <Text style={s.emoji}>🪪</Text>
      <Text style={s.title}>Everyone on Ember is real</Text>
      <Text style={s.body}>
        A quick video selfie verifies you're you. Every profile you'll ever see
        has passed the same check. No exceptions, no catfish.
      </Text>
      <Pressable style={s.btn} onPress={startVerification}>
        <Text style={s.btnText}>Verify my identity</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: spacing.l, backgroundColor: colors.bg },
  emoji: { fontSize: 56, textAlign: "center" },
  title: { color: colors.text, fontSize: 26, fontWeight: "700", textAlign: "center", marginTop: spacing.m },
  body: { color: colors.textDim, textAlign: "center", marginTop: spacing.m, lineHeight: 22 },
  btn: { backgroundColor: colors.ember, borderRadius: 14, padding: spacing.m, alignItems: "center", marginTop: spacing.xl },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
