import { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, Alert, ActivityIndicator } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { callFn } from "@/lib/supabase";
import { colors, spacing } from "@/theme";
import type { Intent } from "@/lib/types";

const OPTIONS: { value: Intent; label: string }[] = [
  { value: "long_term", label: "Long-term relationship" },
  { value: "open_to_long_term", label: "Open to long-term (not sure yet)" },
  { value: "figuring_it_out", label: "Figuring it out" },
];

export default function IntentScreen() {
  const { audio_paths } = useLocalSearchParams<{ audio_paths: string }>();
  const [intent, setIntent] = useState<Intent | null>(null);
  const [statement, setStatement] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const submit = async () => {
    if (!intent || statement.trim().length < 10) {
      return Alert.alert("Almost there", "Pick an intent and write your statement — your matches will see it word for word.");
    }
    setBusy(true);
    try {
      const { bio } = await callFn<{ bio: string }>("profile-extract", {
        audio_paths: JSON.parse(audio_paths!),
        intent,
        intent_statement: statement.trim(),
      });
      router.push({ pathname: "/(onboarding)/review", params: { bio } });
    } catch (e) {
      Alert.alert("Something went wrong", String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={s.wrap}>
      <Text style={s.title}>What are you looking for?</Text>
      {OPTIONS.map((o) => (
        <Pressable key={o.value} style={[s.option, intent === o.value && s.optionActive]} onPress={() => setIntent(o.value)}>
          <Text style={[s.optionText, intent === o.value && s.optionTextActive]}>{o.label}</Text>
        </Pressable>
      ))}
      <Text style={s.label}>In your own words ({120 - statement.length} left)</Text>
      <TextInput
        style={s.input}
        multiline
        maxLength={120}
        placeholder="Shown on your profile, exactly as written."
        placeholderTextColor={colors.textDim}
        value={statement}
        onChangeText={setStatement}
      />
      <Pressable style={[s.btn, busy && { opacity: 0.6 }]} onPress={submit} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Build my profile</Text>}
      </Pressable>
      {busy && <Text style={s.busyHint}>Listening to your answers and writing your profile…</Text>}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: spacing.l, backgroundColor: colors.bg },
  title: { color: colors.text, fontSize: 26, fontWeight: "700", marginBottom: spacing.l },
  option: { backgroundColor: colors.card, borderRadius: 14, padding: spacing.m, marginBottom: spacing.s, borderWidth: 1, borderColor: colors.border },
  optionActive: { borderColor: colors.ember },
  optionText: { color: colors.textDim, fontSize: 16 },
  optionTextActive: { color: colors.text, fontWeight: "600" },
  label: { color: colors.textDim, marginTop: spacing.l, marginBottom: spacing.s },
  input: { backgroundColor: colors.card, color: colors.text, borderRadius: 14, padding: spacing.m, minHeight: 80, borderWidth: 1, borderColor: colors.border, textAlignVertical: "top" },
  btn: { backgroundColor: colors.ember, borderRadius: 14, padding: spacing.m, alignItems: "center", marginTop: spacing.l },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  busyHint: { color: colors.textDim, textAlign: "center", marginTop: spacing.m },
});
